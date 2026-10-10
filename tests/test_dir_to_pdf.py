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


@needs_render
class TestRendering:

    @needs_pdftotext
    def test_toc_first_with_correct_page_numbers(self, tree):
        result = run_script(tree)
        assert result.returncode == 0, result.stderr
        pdf = tree / "merged.pdf"
        first_page = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"],
                                    capture_output=True, text=True).stdout
        assert "Table of Contents" in first_page
        entries = dict(re.findall(r"(\S+?)\s*\.{3,}\s*(\d+)", first_page))
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

    def test_no_matching_files_is_an_error(self, tree):
        result = run_script(tree, include_types="nothing")
        assert result.returncode != 0
        assert "no matching files" in result.stderr.lower()
        assert not (tree / "merged.pdf").exists()
