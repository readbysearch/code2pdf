"""code2txt --files-from: exactly the listed files, in the given order (as in code2pdf).

The agent-selection eval showed agents doing this by hand without it: copying files into
staging folders and writing the table of contents themselves.
"""

import subprocess
from pathlib import Path
import pytest

CODE2TXT = Path(__file__).parent.parent / "bin" / "code2txt"


@pytest.fixture
def project(temp_dir):
    root = temp_dir / "proj"
    for rel in ["a.py", "b.md", "sub/c.js", "sub/deep/d.ts", ".github/ci.yml", "notes.txt"]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content of {rel}\n")
    (root / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    return root


def run(args, cwd, stdin=None):
    return subprocess.run([str(CODE2TXT), *args], cwd=cwd, input=stdin, capture_output=True,
                          text=True, timeout=60)


def sections(path: Path):
    lines = path.read_text().split("\n")
    return [lines[i][3:] for i in range(len(lines) - 1)
            if lines[i].startswith("## ") and lines[i + 1].startswith("```")]


def toc(path: Path):
    text = path.read_text()
    head = text.split("---", 1)[0]
    return [line[2:] for line in head.split("\n") if line.startswith("- ")]


def test_list_from_stdin_keeps_order_and_drops_duplicates(project, temp_dir):
    out = temp_dir / "out.md"
    result = run(["--files-from", "-", "-o", str(out)], project,
                 stdin="sub/deep/d.ts\nnotes.txt\n\na.py\n.github/ci.yml\nsub/deep/d.ts\n")
    assert result.returncode == 0, result.stdout + result.stderr
    expected = ["sub/deep/d.ts", "notes.txt", "a.py", ".github/ci.yml"]
    assert sections(out) == expected  # .txt and hidden files too: the list is used as given
    assert toc(out) == expected


def test_list_file_with_directory_and_absolute_paths(project, temp_dir):
    listing = temp_dir / "list.txt"
    listing.write_text(f"deep/d.ts\n{project / 'sub' / 'c.js'}\n")
    out = temp_dir / "out.md"
    result = run(["--files-from", str(listing), "-o", str(out), "sub"], project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sections(out) == ["deep/d.ts", "c.js"]  # relative to the directory, like the walk


def test_binary_files_are_skipped_with_one_line(project, temp_dir):
    out = temp_dir / "out.md"
    result = run(["--files-from", "-", "-o", str(out)], project, stdin="a.py\nlogo.png\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sections(out) == ["a.py"]
    assert "Skipped 1 binary file: logo.png" in result.stderr


def test_missing_and_outside_files_are_errors(project, temp_dir):
    (temp_dir / "outside.py").write_text("x\n")
    out = temp_dir / "out.md"
    result = run(["--files-from", "-", "-o", str(out)], project,
                 stdin=f"a.py\nnope.py\n{temp_dir / 'outside.py'}\nsub\n")
    assert result.returncode != 0
    assert "not a file: nope.py" in result.stderr
    assert "outside" in result.stderr and "not a file: sub" in result.stderr


def test_option_without_value_is_an_error(project):
    result = run(["--files-from"], project)
    assert result.returncode != 0
    assert "--files-from needs a value" in result.stdout + result.stderr
