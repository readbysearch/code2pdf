"""Tests for scripts/dir_to_pdf.py: one-pass directory → PDF rendering."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "dir_to_pdf.py"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable

BLACKLIST = '["node_modules", ".git", "dist", "out"]'
PATTERN = "env*"
EXTENSIONS = '["rb", "sh", "md", "js", "py", "ts", "java", "cpp", "h", "c", "html"]'
NAMES = '["README", "LICENSE", "Makefile", "launch.json"]'

# Same tree and expectations as recorded from the v3.2 bash implementation (print_all.sh)
TREE = ["a.py", "b.md", "notes.txt", "Makefile", "LICENSE", "Dockerfile", "node_modules/x.js",
        "envfoo/y.py", ".hidden/z.py", "sub/c.js", "sub/deep/d.ts", "sub/deep/e.go", "dist/f.js",
        "tests/t.py", "package-lock.json", ".dotfile"]


def has_render_deps() -> bool:
    return subprocess.run([PYTHON, "-c", "import pygments, weasyprint"],
                          capture_output=True).returncode == 0


needs_render = pytest.mark.skipif(not has_render_deps(), reason="pygments/weasyprint not available")
needs_pdftotext = pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext not installed")


@pytest.fixture
def tree(temp_dir):
    root = temp_dir / "tree"
    for rel in TREE:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content of {rel}\n")
    return root


def run_script(root, *extra, ignore_files="", ignore_types="", ignore_folders="", include_types="",
               output=None, env=None):
    output = output or (Path(root) / "merged.pdf")
    cmd = [PYTHON, str(SCRIPT), str(root), str(output), BLACKLIST, PATTERN, EXTENSIONS, NAMES, "true",
           ignore_files, ignore_types, ignore_folders, include_types, *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)


def listed(root, **filters):
    result = run_script(root, "--list-files", **filters)
    assert result.returncode == 0, result.stderr
    return sorted(result.stdout.split())


class TestFiltering:
    """--list-files must select exactly what the old bash implementation selected."""

    def test_default(self, tree):
        assert listed(tree) == sorted(["a.py", "b.md", "Dockerfile", "LICENSE", "Makefile",
                                       "sub/c.js", "sub/deep/d.ts", "tests/t.py"])

    def test_ignore_files(self, tree):
        assert listed(tree, ignore_files="a.py,c.js") == sorted(
            ["b.md", "Dockerfile", "LICENSE", "Makefile", "sub/deep/d.ts", "tests/t.py"])

    def test_ignore_types(self, tree):
        assert listed(tree, ignore_types="md,ts") == sorted(
            ["a.py", "Dockerfile", "LICENSE", "Makefile", "sub/c.js", "tests/t.py"])

    def test_ignore_folders(self, tree):
        assert listed(tree, ignore_folders="sub") == sorted(
            ["a.py", "b.md", "Dockerfile", "LICENSE", "Makefile", "tests/t.py"])

    def test_include_types(self, tree):
        assert listed(tree, include_types="py,go") == sorted(["a.py", "sub/deep/e.go", "tests/t.py"])

    def test_listing_order_is_depth_first_by_name(self, tree):
        result = run_script(tree, "--list-files")
        assert result.stdout.split() == ["Dockerfile", "LICENSE", "Makefile", "a.py", "b.md",
                                         "sub/c.js", "sub/deep/d.ts", "tests/t.py"]

    def test_output_file_is_never_included(self, tree):
        (tree / "merged.pdf").write_bytes(b"%PDF-old")
        assert "merged.pdf" not in listed(tree, include_types="pdf,py")

    def test_symlink_loop_is_not_followed_forever(self, tree):
        (tree / "sub" / "loop").symlink_to(tree, target_is_directory=True)
        files = listed(tree)
        assert files.count("a.py") == 1


def listed_in_order(root, *extra, stdin=None):
    cmd = [PYTHON, str(SCRIPT), str(root), str(Path(root) / "merged.pdf"), BLACKLIST, PATTERN,
           EXTENSIONS, NAMES, "true", "", "", "", "", "--list-files", *extra]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=stdin)
    return result.stdout.split(), result


class TestGlobs:
    """--include adds to the default rules, --exclude wins over everything."""

    def test_exclude_by_path_keeps_same_name_elsewhere(self, tree):
        (tree / "lib" / "deep").mkdir(parents=True)
        (tree / "lib" / "deep" / "d.ts").write_text("x\n")
        files, _ = listed_in_order(tree, "--exclude", "sub/deep")
        assert "sub/deep/d.ts" not in files and "lib/deep/d.ts" in files

    def test_exclude_glob_at_any_depth(self, tree):
        (tree / "sub" / "c_test.js").write_text("x\n")
        files, _ = listed_in_order(tree, "--exclude", "*_test.js", "--exclude", "*.md")
        assert "sub/c_test.js" not in files and "b.md" not in files and "sub/c.js" in files

    def test_include_adds_to_the_defaults(self, tree):
        files, _ = listed_in_order(tree, "--include", "*.json", "--include", "notes.txt")
        assert {"package-lock.json", "notes.txt", "a.py", "sub/c.js"} <= set(files)

    def test_include_names_hidden_and_skipped_folders(self, tree):
        files, _ = listed_in_order(tree, "--include", ".hidden", "--include", "node_modules/*.js",
                                   "--include", ".dotfile")
        assert {".hidden/z.py", "node_modules/x.js", ".dotfile"} <= set(files)
        assert "dist/f.js" not in files

    def test_wildcards_never_reach_into_skipped_folders_or_dotfiles(self, tree):
        files, _ = listed_in_order(tree, "--include", "*", "--include", "**/*.js")
        assert "notes.txt" in files  # * does include other types
        for skipped in ("node_modules/x.js", "dist/f.js", "envfoo/y.py", ".hidden/z.py", ".dotfile"):
            assert skipped not in files

    def test_exclude_wins_over_include(self, tree):
        files, _ = listed_in_order(tree, "--include", "sub", "--exclude", "sub/deep/*.ts")
        assert "sub/c.js" in files and "sub/deep/d.ts" not in files

    def test_include_of_a_folder_covers_every_file_in_it(self, tree):
        (tree / "sub" / "data.csv").write_text("a,b\n")
        files, _ = listed_in_order(tree, "--include", "sub")
        assert "sub/data.csv" in files and "sub/deep/e.go" in files

    def test_absolute_and_dot_slash_patterns(self, tree):
        files, _ = listed_in_order(tree, "--exclude", str(tree / "sub"), "--exclude", "./tests/")
        assert not any(f.startswith(("sub/", "tests/")) for f in files) and "a.py" in files

    def test_pattern_that_matches_nothing_is_reported(self, tree):
        files, result = listed_in_order(tree, "--exclude", "src/legacy", "--include", "*.nope")
        assert result.returncode == 0
        assert "--exclude 'src/legacy' matched nothing" in result.stderr
        assert "--include '*.nope' matched nothing" in result.stderr

    def test_binary_files_are_skipped(self, tree):
        (tree / "sub" / "blob.js").write_bytes(b"\x00\x01binary")
        files, result = listed_in_order(tree, "--include", "sub")
        assert "sub/blob.js" not in files
        assert "Skipped 1 binary file: sub/blob.js" in result.stderr

    def test_many_binary_files_are_reported_in_one_line(self, tree):
        for i in range(30):
            (tree / "sub" / f"img{i:02d}.js").write_bytes(b"\x00png")
        _, result = listed_in_order(tree, "--include", "sub")
        assert result.stderr.count("\n") == 1, result.stderr
        assert "Skipped 30 binary files: sub/img00.js, sub/img01.js, sub/img02.js, …" in result.stderr


class TestFilesFrom:

    def test_exact_list_in_given_order(self, tree):
        files, result = listed_in_order(tree, "--files-from", "-",
                                        stdin="tests/t.py\nnotes.txt\n\na.py\ntests/t.py\n")
        assert result.returncode == 0, result.stderr
        assert files == ["tests/t.py", "notes.txt", "a.py"]  # no default filter, duplicates dropped

    def test_absolute_paths_and_exclusions(self, tree, temp_dir):
        listing = temp_dir / "list.txt"
        listing.write_text(f"{tree / 'a.py'}\nb.md\nsub/c.js\n")
        files, result = listed_in_order(tree, "--files-from", str(listing), "--exclude", "*.md")
        assert files == ["a.py", "sub/c.js"], result.stderr

    def test_missing_or_outside_files_are_errors(self, tree, temp_dir):
        (temp_dir / "outside.py").write_text("x\n")
        files, result = listed_in_order(tree, "--files-from", "-",
                                        stdin=f"a.py\nnope.py\n{temp_dir / 'outside.py'}\nsub\n")
        assert result.returncode != 0
        assert "not a file: nope.py" in result.stderr
        assert "outside" in result.stderr and "not a file: sub" in result.stderr

    def test_include_is_rejected(self, tree):
        _, result = listed_in_order(tree, "--files-from", "-", "--include", "*.txt", stdin="a.py\n")
        assert result.returncode != 0 and "--include has no effect" in result.stderr


def test_contents_groups_follow_page_order():
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import dir_to_pdf
    groups = dir_to_pdf.group_by_folder(["a.py", "sub/c.js", "sub/d.js", "z.py", "sub/e.js"])
    assert groups == [("", [(0, "a.py")]), ("sub", [(1, "c.js"), (2, "d.js")]),
                      ("", [(3, "z.py")]), ("sub", [(4, "e.js")])]

@needs_render
class TestRendering:

    @needs_pdftotext
    def test_toc_first_with_correct_page_numbers(self, tree):
        result = run_script(tree)
        assert result.returncode == 0, result.stderr
        pdf = tree / "merged.pdf"
        first_page = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", "1", str(pdf), "-"],
                                    capture_output=True, text=True).stdout
        # Contents are grouped by folder: a heading "sub/deep/" then entries "d.ts . . . 7"
        entries, folder = {}, ""
        for line in first_page.splitlines():
            line = line.strip()
            entry = re.match(r"(\S+?)\s*(?:\.\s*){3,}(\d+)$", line)
            if entry:
                entries[(folder + entry.group(1)).lstrip("/")] = entry.group(2)
            elif line.endswith("/"):
                folder = "" if line == f"{tree.name}/" else line
        assert set(entries) == {"Dockerfile", "LICENSE", "Makefile", "a.py", "b.md",
                                "sub/c.js", "sub/deep/d.ts", "tests/t.py"}
        for path, page in entries.items():
            text = subprocess.run(["pdftotext", "-f", page, "-l", page, str(pdf), "-"],
                                  capture_output=True, text=True).stdout
            assert f"content of {path}" in text, f"{path} not on page {page}"

    @needs_pdftotext
    def test_headers_use_relative_paths(self, tree):
        result = run_script(tree)
        assert result.returncode == 0, result.stderr
        text = subprocess.run(["pdftotext", str(tree / "merged.pdf"), "-"],
                              capture_output=True, text=True).stdout
        assert str(tree) not in text
        assert "sub/deep/d.ts" in text

    def test_cjk_and_no_ghostscript_needed(self, tree, temp_dir):
        (tree / "cjk.py").write_text("# 你好，世界 — こんにちは — 안녕하세요\n")
        env = dict(os.environ, PATH="/usr/bin:/bin")  # no gs, no jq
        result = run_script(tree, env=env)
        assert result.returncode == 0, result.stderr
        assert (tree / "merged.pdf").read_bytes().startswith(b"%PDF-")

    @needs_pdftotext
    def test_files_from_order_and_output_option(self, tree, temp_dir):
        out = temp_dir / "out" / "picked.pdf"
        cmd = [PYTHON, str(SCRIPT), str(tree), "", BLACKLIST, PATTERN, EXTENSIONS, NAMES, "true",
               "", "", "", "", "--files-from", "-", "--output", str(out), "--quiet"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                input="sub/c.js\na.py\nsub/deep/d.ts\n")
        assert result.returncode == 0, result.stderr
        text = subprocess.run(["pdftotext", "-layout", str(out), "-"], capture_output=True, text=True).stdout
        body = text.split("\f")[1:]
        assert [p for p in ("content of sub/c.js", "content of a.py", "content of sub/deep/d.ts")
                if any(p in page for page in body)] == ["content of sub/c.js", "content of a.py",
                                                        "content of sub/deep/d.ts"]
        assert body[0].count("content of") == 1 and "content of sub/c.js" in body[0]
        assert not (tree / "merged.pdf").exists()

    def test_no_matching_files_is_an_error(self, tree):
        result = run_script(tree, include_types="nothing")
        assert result.returncode != 0
        assert "no matching files" in result.stderr.lower()
        assert not (tree / "merged.pdf").exists()
