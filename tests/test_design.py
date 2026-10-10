"""Tests for the PDF design: themes, fonts, dates, language detection, contents page."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable
FIXED_EPOCH = "1767225600"  # 2026-01-01 00:00 UTC


def has_render_deps() -> bool:
    return subprocess.run([PYTHON, "-c", "import pygments, weasyprint"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not has_render_deps(), reason="pygments/weasyprint not available")
needs_poppler = pytest.mark.skipif(not (shutil.which("pdftotext") and shutil.which("pdffonts")),
                                   reason="poppler (pdftotext/pdffonts) not installed")


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(SCRIPTS))
    import dir_to_pdf
    import theme
    return dir_to_pdf, theme


def git(cwd, *args, date="2020-01-02T03:04:05"):
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


@pytest.fixture
def project(temp_dir):
    root = temp_dir / "demo"
    (root / "bin").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "bin" / "tool").write_text("#!/usr/bin/env bash\necho \"hello\"  # greet\n")
    (root / "src" / "app.py").write_text("# 你好\ndef main():\n    return 42\n")
    (root / "README.md").write_text("# Demo\n")
    return root


def pdf_text(pdf, first=None, last=None):
    cmd = ["pdftotext"]
    if first:
        cmd += ["-f", str(first), "-l", str(last or first)]
    return subprocess.run(cmd + [str(pdf), "-"], capture_output=True, text=True).stdout


def run_dir(root, *extra, env_extra=None):
    env = dict(os.environ, SOURCE_DATE_EPOCH=FIXED_EPOCH, TZ="UTC", **(env_extra or {}))
    cmd = [PYTHON, str(SCRIPTS / "dir_to_pdf.py"), str(root), str(root / "merged.pdf"),
           '["node_modules", ".git"]', "env*", '["py", "md", "sh"]', '["README"]', "true",
           "", "", "", "", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)


class TestThemes:

    def test_builtin_themes_and_pygments_styles_are_listed(self, mod):
        _, theme = mod
        names = theme.list_themes()
        assert names[:2] == ["paper", "mono"]
        assert "monokai" in names and "solarized-light" in names

    def test_unknown_theme_is_rejected(self, mod):
        _, theme = mod
        with pytest.raises(ValueError, match="unknown theme"):
            theme.resolve_theme("no-such-theme")

    @pytest.mark.parametrize("name", ["paper", "mono", "monokai"])
    def test_each_kind_of_theme_renders(self, project, name):
        result = run_dir(project, "--theme", name)
        assert result.returncode == 0, result.stderr
        assert (project / "merged.pdf").read_bytes().startswith(b"%PDF-")

    def test_unknown_theme_fails_cleanly(self, project):
        result = run_dir(project, "--theme", "no-such-theme")
        assert result.returncode != 0
        assert "unknown theme" in result.stderr.lower()
        assert "--list-themes" in result.stderr


class TestFonts:

    @needs_poppler
    def test_bundled_plex_fonts_are_embedded(self, project):
        assert run_dir(project).returncode == 0
        fonts = subprocess.run(["pdffonts", str(project / "merged.pdf")], capture_output=True, text=True).stdout
        assert "c2p-Code" in fonts and "c2p-Text" in fonts
        assert "Courier" not in fonts and "Verdana" not in fonts

    def test_font_files_ship_with_the_scripts(self, mod):
        _, theme = mod
        for path in theme.font_files():
            assert Path(path).is_file(), path


class TestLanguageDetection:

    def test_shebang_script_without_extension_is_highlighted(self, mod):
        from code_to_pdf import lexer_for
        assert lexer_for("bin/tool", "#!/usr/bin/env bash\necho hi\n").name == "Bash"
        assert lexer_for("bin/tool", "#!/usr/bin/env python3\nprint(1)\n").name == "Python"

    def test_plain_files_without_shebang_stay_plain_text(self, mod):
        from code_to_pdf import lexer_for
        assert lexer_for("LICENSE", "MIT License\n\nPermission is hereby granted").name == "Text only"


class TestDates:

    def test_git_repo_shows_commit_and_last_change(self, mod, project):
        dir_to_pdf, _ = mod
        git(project, "init", "-q", "-b", "main")
        git(project, "add", ".")
        git(project, "commit", "-q", "-m", "first", date="2020-01-02T03:04:05")
        (project / "README.md").write_text("# Demo v2\n")
        git(project, "commit", "-q", "-am", "second", date="2021-05-06T07:08:09")
        info = dir_to_pdf.source_info(str(project), ["README.md", "src/app.py"])
        assert info.files["src/app.py"] == "last changed 2020-01-02"
        assert info.files["README.md"] == "last changed 2021-05-06"
        assert re.fullmatch(r"from commit [0-9a-f]{7,} \(main\)", info.summary)

    def test_uncommitted_files_are_marked(self, mod, project):
        dir_to_pdf, _ = mod
        git(project, "init", "-q", "-b", "main")
        git(project, "add", ".")
        git(project, "commit", "-q", "-m", "first")
        (project / "src" / "app.py").write_text("# changed\n")
        (project / "src" / "new.py").write_text("x = 1\n")
        info = dir_to_pdf.source_info(str(project), ["src/app.py", "src/new.py", "README.md"])
        assert info.files["src/app.py"] == "uncommitted changes"
        assert info.files["src/new.py"] == "uncommitted changes"
        assert info.files["README.md"] == "last changed 2020-01-02"
        assert info.summary.endswith("with uncommitted changes")

    def test_outside_git_falls_back_to_modified_date(self, mod, project):
        dir_to_pdf, _ = mod
        os.utime(project / "README.md", (1600000000, 1600000000))  # 2020-09-13 UTC
        info = dir_to_pdf.source_info(str(project), ["README.md"])
        assert info.summary == ""
        assert re.fullmatch(r"modified 2020-09-1[23]", info.files["README.md"])

    @needs_poppler
    def test_printed_date_and_file_dates_appear_in_pdf(self, project):
        git(project, "init", "-q", "-b", "main")
        git(project, "add", ".")
        git(project, "commit", "-q", "-m", "first", date="2020-01-02T03:04:05")
        result = run_dir(project)
        assert result.returncode == 0, result.stderr
        first = pdf_text(project / "merged.pdf", 1)
        assert re.search(r"Printed 2026-01-01 from commit [0-9a-f]{7,} \(main\)", first)
        everything = pdf_text(project / "merged.pdf")
        assert "last changed 2020-01-02" in everything
        assert "demo, 2026-01-01" in pdf_text(project / "merged.pdf", 2)
        info = subprocess.run(["pdfinfo", "-isodates", str(project / "merged.pdf")],
                              capture_output=True, text=True).stdout
        assert re.search(r"CreationDate:\s+2026-01-01T00:00:00", info)


class TestContentsPage:

    @needs_poppler
    def test_contents_grouped_by_folder_with_counts(self, project):
        result = run_dir(project)
        assert result.returncode == 0, result.stderr
        first = pdf_text(project / "merged.pdf", 1)
        assert "3 files, 6 lines" in first
        lines = [l.strip() for l in first.splitlines() if l.strip()]
        assert lines.index("bin/") < lines.index("src/")
        assert any(l.startswith("tool") for l in lines) and any(l.startswith("app.py") for l in lines)

    @needs_poppler
    def test_file_titles_show_language_and_lines(self, project):
        assert run_dir(project).returncode == 0
        everything = pdf_text(project / "merged.pdf")
        assert re.search(r"Bash, 2 lines", everything)
        assert re.search(r"Python, 3 lines", everything)


class TestSingleFile:

    @needs_poppler
    def test_single_file_uses_the_same_design_without_contents(self, project, temp_dir):
        out = temp_dir / "app.pdf"
        env = dict(os.environ, SOURCE_DATE_EPOCH=FIXED_EPOCH, TZ="UTC")
        result = subprocess.run([PYTHON, str(SCRIPTS / "code_to_pdf.py"), str(project / "src" / "app.py"),
                                 str(out), "src/app.py", "--theme", "mono"],
                                capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        text = pdf_text(out)
        assert "Python, 3 lines" in text
        assert "Contents" not in text
        fonts = subprocess.run(["pdffonts", str(out)], capture_output=True, text=True).stdout
        assert "c2p-Code" in fonts
