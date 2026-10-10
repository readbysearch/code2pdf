"""Launchers must find their scripts relative to themselves, not via Homebrew."""

import os
import shutil
import subprocess
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"


def repo_venv_has_deps() -> bool:
    if not REPO_VENV_PYTHON.exists():
        return False
    return subprocess.run([str(REPO_VENV_PYTHON), "-c", "import pygments, weasyprint"],
                          capture_output=True).returncode == 0


def isolated_path(tmp: Path) -> str:
    """A PATH with gs and jq but no brew and no python carrying pygments/weasyprint."""
    tools = tmp / "tools"
    tools.mkdir(exist_ok=True)
    for tool in ("gs", "jq"):
        found = shutil.which(tool)
        if found and not (tools / tool).exists():
            (tools / tool).symlink_to(found)
    return f"{tools}:/usr/bin:/bin"


def run(cmd, cwd, env_extra=None):
    env = {"HOME": os.environ["HOME"], "PATH": isolated_path(cwd)}
    env.update(env_extra or {})
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


@pytest.fixture
def linked_bin(temp_dir):
    """bin/ dir of symlinks to the repo launchers, as install.sh and `ln -s` create."""
    link_dir = temp_dir / "linkbin"
    link_dir.mkdir()
    for name in ("code2pdf", "code2txt"):
        (link_dir / name).symlink_to(PROJECT_ROOT / "bin" / name)
    return link_dir


def test_code2pdf_help_needs_no_dependencies(linked_bin, temp_dir):
    result = run([str(linked_bin / "code2pdf"), "--help"], temp_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Usage: code2pdf" in result.stdout


def test_code2txt_works_through_symlink(linked_bin, temp_dir):
    project = temp_dir / "proj"
    project.mkdir()
    (project / "a.py").write_text("print('hi')\n")
    result = run([str(linked_bin / "code2txt"), "-o", "out.md", str(project)], temp_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "print('hi')" in (temp_dir / "out.md").read_text()


@pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")
def test_code2pdf_symlink_uses_repo_scripts_and_venv(linked_bin, temp_dir):
    (temp_dir / "hello.py").write_text("# 你好\nprint('hi')\n")
    result = run([str(linked_bin / "code2pdf"), "-s", "hello.py"], temp_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (temp_dir / "hello.pdf").read_bytes().startswith(b"%PDF-")


def test_code2pdf_home_override(temp_dir):
    """CODE2PDF_HOME points the launcher at another install (used by the Homebrew formula)."""
    home = temp_dir / "fakehome"
    (home / "scripts").mkdir(parents=True)
    (home / "config").mkdir()
    marker = home / "scripts" / "print_single_file_to_pdf.sh"
    marker.write_text('#!/bin/bash\necho "FAKE HOME USED for $1"\n')
    marker.chmod(0o755)
    (home / "scripts" / "print_all.sh").write_text("#!/bin/bash\n")
    venv_bin = home / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake_python = venv_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 0\n")  # satisfies the import checks
    fake_python.chmod(0o755)
    (temp_dir / "x.py").write_text("x = 1\n")
    result = run([str(PROJECT_ROOT / "bin" / "code2pdf"), "-s", "x.py"], temp_dir,
                 {"CODE2PDF_HOME": str(home)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAKE HOME USED for x.py" in result.stdout


def test_code2pdf_reports_missing_scripts(temp_dir):
    result = run([str(PROJECT_ROOT / "bin" / "code2pdf"), "-s", "x.py"], temp_dir,
                 {"CODE2PDF_HOME": str(temp_dir / "nowhere")})
    assert result.returncode != 0
    assert "scripts" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")
def test_list_themes(linked_bin, temp_dir):
    result = run([str(linked_bin / "code2pdf"), "--list-themes"], temp_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    names = result.stdout.split()
    assert names[:2] == ["paper", "mono"] and "monokai" in names


@pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")
def test_theme_option_for_both_modes(linked_bin, temp_dir):
    (temp_dir / "proj").mkdir()
    (temp_dir / "proj" / "a.py").write_text("x = 1\n")
    single = run([str(linked_bin / "code2pdf"), "--theme", "mono", "-s", "proj/a.py"], temp_dir)
    assert single.returncode == 0, single.stdout + single.stderr
    assert (temp_dir / "a.pdf").exists()
    whole = run([str(linked_bin / "code2pdf"), "-a", "proj", "--theme", "solarized-light"], temp_dir)
    assert whole.returncode == 0, whole.stdout + whole.stderr
    assert (temp_dir / "proj" / "merged.pdf").exists()


@pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")
def test_unknown_theme_is_reported(linked_bin, temp_dir):
    (temp_dir / "a.py").write_text("x = 1\n")
    result = run([str(linked_bin / "code2pdf"), "--theme", "nope", "-s", "a.py"], temp_dir)
    assert result.returncode != 0
    assert "unknown theme" in (result.stdout + result.stderr).lower()


def test_default_selection_covers_common_languages_and_skips_build_output(linked_bin, temp_dir):
    """Defaults used to skip Swift/Go/Rust/... and include build/, so e.g. a Swift app printed
    mostly SwiftPM checkouts from build/ and none of its own sources."""
    project = temp_dir / "app"
    sources = ["App/Main.swift", "App/Bridge.m", "cmd/main.go", "src/lib.rs", "android/Main.kt",
               "web/App.tsx", "web/app.css", "config.yaml", "pyproject.toml", "README.md"]
    skipped = ["build/SourcePackages/checkouts/Lib/Lib.swift", "DerivedData/x.swift", "target/debug/x.rs",
               "vendor/lib.go", "Pods/A/A.m", "__pycache__/x.py", "venv/lib/site.py",
               "package-lock.json"]
    for rel in sources + skipped:
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
    result = run([str(linked_bin / "code2pdf"), "-a", str(project), "--list-files"], temp_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(result.stdout.split()) == sorted(sources)


@pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")
def test_jobs_option_renders_in_parts(linked_bin, temp_dir):
    project = temp_dir / "big"
    project.mkdir()
    for i in range(4):
        (project / f"m{i}.py").write_text("x = 1\n" * 80)
    result = run([str(linked_bin / "code2pdf"), "-a", str(project), "-j", "2"], temp_dir,
                 {"CODE2PDF_PART_PAGES": "2"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 at a time" in result.stderr
    assert (project / "merged.pdf").exists()
