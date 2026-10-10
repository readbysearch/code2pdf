"""Printing part of a file: `path:START-END` in --files-from (and -s), with the real path and
the real line numbers.

The agent eval's topic requests ("print the methods that render JSON") showed agents cutting
excerpts into new files with made-up names when they couldn't do this.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import dir_to_pdf  # noqa: E402

CODE2PDF = PROJECT_ROOT / "bin" / "code2pdf"
CODE2TXT = PROJECT_ROOT / "bin" / "code2txt"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"


def has_render_deps():
    python = REPO_VENV_PYTHON if REPO_VENV_PYTHON.exists() else Path(sys.executable)
    return subprocess.run([str(python), "-c", "import pygments, weasyprint"],
                          capture_output=True).returncode == 0


needs_render = pytest.mark.skipif(not has_render_deps(), reason="pygments/weasyprint not available")
needs_pdftotext = pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext not installed")


@pytest.fixture
def project(temp_dir):
    root = temp_dir / "proj"
    (root / "sub").mkdir(parents=True)
    (root / "a.py").write_text("".join(f"value_{n} = {n}  # line {n} of a.py\n" for n in range(1, 21)))
    (root / "sub" / "c.js").write_text("".join(f"const c{n} = {n}; // line {n} of c.js\n" for n in range(1, 6)))
    return root


def code2pdf(args, cwd, stdin=None, env_extra=None):
    env = dict(os.environ, CODE2PDF_QUIET="1", **(env_extra or {}))
    return subprocess.run([str(CODE2PDF), *args], cwd=cwd, input=stdin, capture_output=True,
                          text=True, timeout=180, env=env)


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def numbered(text, name):
    """{line number: content} for code lines of NAME as printed (number, then the code)."""
    found = {}
    for line in text.splitlines():
        m = re.match(rf"\s*(\d+)\s+(.*line (\d+) of {re.escape(name)})", line)
        if m:
            found[int(m.group(1))] = int(m.group(3))
    return found


# --- parsing -------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("a.py", ("a.py", ())),
    ("src/a.py:10-20", ("src/a.py", ((10, 20),))),
    ("a.py:7", ("a.py", ((7, 7),))),
    ("a.py:40-", ("a.py", ((40, None),))),
    ("a.py:1-2,8-9", ("a.py", ((1, 2), (8, 9)))),
    ("C:/odd:name.py", ("C:/odd:name.py", ())),     # a colon without a range is part of the name
    ("a.py:x-2", ("a.py:x-2", ())),
])
def test_split_ranges(text, expected):
    assert dir_to_pdf.split_ranges(text) == expected


def test_resolve_ranges_sorts_merges_and_clamps():
    assert dir_to_pdf.resolve_ranges(((8, 9), (1, 3), (2, 5)), 20) == (((1, 5), (8, 9)), None)
    assert dir_to_pdf.resolve_ranges(((15, None),), 20) == (((15, 20),), None)
    ranges, note = dir_to_pdf.resolve_ranges(((15, 30),), 20)
    assert ranges == ((15, 20),) and "20 lines" in note
    with pytest.raises(ValueError, match="starts after the end"):
        dir_to_pdf.resolve_ranges(((25, 30),), 20)
    with pytest.raises(ValueError, match="ends before it starts"):
        dir_to_pdf.resolve_ranges(((9, 3),), 20)
    with pytest.raises(ValueError, match="line numbers start at 1"):
        dir_to_pdf.resolve_ranges(((0, 3),), 20)


# --- code2pdf --------------------------------------------------------------------------------

def test_list_files_shows_the_ranges(project):
    result = code2pdf(["--files-from", "-", "--list-files"], project, stdin="a.py:12-14\nsub/c.js\na.py:2\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["a.py:12-14", "sub/c.js", "a.py:2-2"]


def test_range_errors_name_the_file(project):
    result = code2pdf(["--files-from", "-", "--list-files"], project, stdin="sub/c.js:9-12\n")
    assert result.returncode != 0
    assert "sub/c.js:9-12" in result.stderr and "starts after the end" in result.stderr


def test_a_file_whose_name_looks_like_a_range_is_a_file(project):
    (project / "notes:1-2").write_text("odd name\n")
    result = code2pdf(["--files-from", "-", "--list-files"], project, stdin="notes:1-2\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["notes:1-2"]  # printed whole: it is a file
    assert "lines" not in result.stderr


@needs_render
@needs_pdftotext
def test_excerpt_keeps_real_path_and_line_numbers(project, temp_dir):
    out = temp_dir / "x.pdf"
    result = code2pdf(["--files-from", "-", "-o", str(out)], project, stdin="a.py:12-14,18-19\nsub/c.js:2-3\n")
    assert result.returncode == 0, result.stderr
    text = pdf_text(out)
    assert numbered(text, "a.py") == {12: 12, 13: 13, 14: 14, 18: 18, 19: 19}
    assert numbered(text, "c.js") == {2: 2, 3: 3}
    assert "lines 12–14, 18–19 of 20" in text
    assert "lines 1–11 not shown" in text and "lines 15–17 not shown" in text and "line 20 not shown" in text
    assert "c.js (lines 2–3)" in text  # contents page
    import pypdf
    titles = [item.title for item in pypdf.PdfReader(out).outline]
    assert titles == ["a.py", "sub/c.js"]  # bookmarks keep the real paths


@needs_render
@needs_pdftotext
def test_parts_mode_prints_the_same_excerpts(project, temp_dir):
    big = "".join(f"{n}\n" for n in range(1, 41))
    stdin = "a.py:3-8\n" + "".join(f"m{i}.py:5-30\n" for i in range(12)) + "sub/c.js:4-\n"
    for i in range(12):
        (project / f"m{i}.py").write_text("".join(f"x{n} = {n}  # line {n} of m{i}.py\n" for n in range(1, 61)))
    single, parts = temp_dir / "single.pdf", temp_dir / "parts.pdf"
    assert code2pdf(["--files-from", "-", "-o", str(single)], project, stdin=stdin).returncode == 0
    result = code2pdf(["--files-from", "-", "-o", str(parts)], project, stdin=stdin,
                      env_extra={"CODE2PDF_PART_PAGES": "2", "CODE2PDF_JOBS": "2"})
    assert result.returncode == 0, result.stderr
    assert pdf_text(single) == pdf_text(parts)
    assert numbered(pdf_text(parts), "m3.py") == {n: n for n in range(5, 31)}
    del big


@needs_render
@needs_pdftotext
def test_single_file_mode_takes_a_range(project, temp_dir):
    result = code2pdf(["-s", "a.py:5-6", "-o", str(temp_dir / "one.pdf")], project)
    assert result.returncode == 0, result.stdout + result.stderr
    text = pdf_text(temp_dir / "one.pdf")
    assert numbered(text, "a.py") == {5: 5, 6: 6}
    assert "lines 5–6 of 20" in text


# --- code2txt --------------------------------------------------------------------------------

def test_code2txt_prints_the_ranges(project, temp_dir):
    out = temp_dir / "out.md"
    result = subprocess.run([str(CODE2TXT), "--files-from", "-", "-o", str(out)], cwd=project,
                            input="a.py:12-13,19\nsub/c.js\n", capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    text = out.read_text()
    assert "- a.py (lines 12-13, 19)" in text and "- sub/c.js\n" in text
    section = text.split("## a.py (lines 12-13, 19)\n", 1)[1].split("\n```\n", 1)[0]
    assert section.splitlines() == ["```python", "value_12 = 12  # line 12 of a.py",
                                    "value_13 = 13  # line 13 of a.py", "... (lines 14-18 not shown)",
                                    "value_19 = 19  # line 19 of a.py"]


def test_code2txt_range_errors(project, temp_dir):
    result = subprocess.run([str(CODE2TXT), "--files-from", "-", "-o", str(temp_dir / "o.md")], cwd=project,
                            input="sub/c.js:9-12\n", capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "sub/c.js:9-12" in result.stderr and "starts after the end" in result.stderr
