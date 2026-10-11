"""Marked lines (path:+START-END, path:-N), --changed REV and --summary.

Layer 1 is the list syntax: marks are a bar in the margin, -N says lines were removed after
line N. Layer 2, --changed REV, builds such a list from `git diff REV`; with --list-files it
prints it, to edit and pass back to --files-from (or to code2txt).
"""

import os
import re
import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import changes  # noqa: E402
import dir_to_pdf  # noqa: E402
from tests.test_line_ranges import CODE2PDF, CODE2TXT, needs_pdftotext, needs_render, pdf_text  # noqa: E402


def run(tool, args, cwd, stdin=None):
    env = dict(os.environ, CODE2PDF_QUIET="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run([str(tool), *args], cwd=cwd, input=stdin, capture_output=True, text=True,
                          timeout=180, env=env)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True)


PY = """import os


def load(path):
    if path:
        return open(path)
    return None


def save(path, data):
    with open(path, "w") as f:
        f.write(data)
    return len(data)
"""


@pytest.fixture
def repo(temp_dir):
    """A git repository with one commit, then: an edited function, a new file, a deleted file,
    a renamed file, a binary file, and an untracked file."""
    root = temp_dir / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "app.py").write_text(PY)
    (root / "pkg" / "util.py").write_text("".join(f"x{n} = {n}  # line {n}\n" for n in range(1, 41)))
    (root / "old.py").write_text("gone = True\n")
    (root / "name.py").write_text("same = 1\n")
    (root / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    (root / "app.py").write_text(PY.replace("        return open(path)\n", "        return open(path, encoding=\"utf-8\")\n"))
    util = (root / "pkg" / "util.py").read_text().split("\n")
    del util[19:22]  # lines 20-22 removed
    util[29] = "x_changed = 0  # an edit"
    (root / "pkg" / "util.py").write_text("\n".join(util))
    (root / "new.py").write_text("def fresh():\n    return 1\n")
    (root / "old.py").unlink()
    git(root, "mv", "name.py", "renamed.py")
    (root / "logo.png").write_bytes(b"\x89PNG\x00\x02")
    (root / "scratch.py").write_text("untracked = 1\n")
    git(root, "add", "new.py")
    return root


# --- layer 1: the list syntax --------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("a.py:10-20,+12-14,-16", ("a.py", ((10, 20),), ((12, 14),), (16,))),
    ("a.py:+3-5", ("a.py", (), ((3, 5),), ())),
    ("a.py:+7,-0", ("a.py", (), ((7, 7),), (0,))),
    ("a.py:10-20", ("a.py", ((10, 20),), (), ())),
    ("a.py", ("a.py", (), (), ())),
    ("a.py:+x", ("a.py:+x", (), (), ())),
])
def test_parse_spec(text, expected):
    assert dir_to_pdf.parse_spec(text) == expected


def test_resolve_spec():
    # marked lines are always shown; with no plain range the whole file is
    assert dir_to_pdf.resolve_spec(((1, 3),), ((10, 12),), (5,), 20) == (((1, 3), (10, 12)), ((10, 12),), (5,), None)
    assert dir_to_pdf.resolve_spec((), ((10, 12),), (), 20) == ((), ((10, 12),), (), None)
    with pytest.raises(ValueError, match="after the end"):
        dir_to_pdf.resolve_spec((), (), (21,), 20)
    with pytest.raises(ValueError, match="starts after the end"):
        dir_to_pdf.resolve_spec((), ((25, 26),), (), 20)


def test_list_round_trips(repo):
    result = run(CODE2PDF, ["--files-from", "-", "--list-files"], repo, stdin="app.py:1-8,+5,-6\npkg/util.py:+2-3\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["app.py:1-8,+5-5,-6", "pkg/util.py:+2-3"]
    assert "stops inside" not in result.stderr  # pieces with marks are cut on purpose


def test_long_range_lists_get_a_short_label():
    assert dir_to_pdf.excerpt_label(((1, 2), (5, 6)), 40) == "lines 1–2, 5–6 of 40"  # as before
    assert dir_to_pdf.excerpt_label(tuple((n, n + 1) for n in range(1, 30, 5)), 40) == "6 parts, 12 of 40 lines"


def test_mark_html():
    code = '<pre>' + "".join(f'<span id="f0-L-{n}">line {n}\n</span>' for n in range(1, 6)) + '</pre>'
    marked = dir_to_pdf.mark_html(code, 0, ((2, 3),), (3, 0))
    assert marked.count('class="marked"') == 2 and '<span id="f0-L-2" class="marked">' in marked
    # removed after line 3: between lines 3 and 4; after line 0: before line 1
    assert re.search(r'line 3\n</span><span class="removed">lines removed</span><span id="f0-L-4"', marked)
    assert marked.startswith('<pre><span class="removed">')
    # an excerpt keeps a marker with the line it follows, and drops one before an unshown line 1
    excerpt = dir_to_pdf.excerpt_html(marked, 0, ((3, 4),), 5)
    assert excerpt.count("lines removed") == 1 and "line 1" not in excerpt


@needs_render
@needs_pdftotext
def test_marks_in_the_pdf(repo, temp_dir):
    out = temp_dir / "m.pdf"
    result = run(CODE2PDF, ["--files-from", "-", "-o", str(out)], repo, stdin="pkg/util.py:10-14,+11-12,-12\n")
    assert result.returncode == 0, result.stderr
    text = pdf_text(out)
    printed = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r"^\s*(\d+)\s+x(\d+) = ", text, re.M)}
    assert printed == {n: n for n in range(10, 15)}  # the file's own numbers, marks or not
    assert "lines removed" in text
    assert "lines 10–14 of 37, 2 lines marked" in text  # the fixture removed 3 of 40
    assert "util.py (lines 10–14, 2 lines marked)" in text


# --- layer 2: --changed ----------------------------------------------------------------------

def test_changed_lists_the_changes(repo):
    result = run(CODE2PDF, ["--changed", "HEAD", "--list-files"], repo)
    assert result.returncode == 0, result.stderr
    listed = dict(line.split(":", 1) for line in result.stdout.split())
    assert set(listed) == {"app.py", "new.py", "pkg/util.py"}
    assert listed["app.py"] == "4-7,+6-6"  # the edit, grown to its 4-line function
    assert listed["new.py"] == "+1-2"   # a new file: whole, every line marked
    util = listed["pkg/util.py"]
    assert "-19" in util.split(",")     # lines 20-22 were removed after (new) line 19
    assert "+30-30" in util.split(",")  # the edit: line 30 once 20-22 are gone
    assert util.split(",")[0] == "16-33"  # both, with context, close enough to be one piece
    notes = result.stderr
    assert "1 deleted file, not printed: old.py" in notes
    assert "1 file renamed without changes, not printed: name.py → renamed.py" in notes
    assert "1 untracked file not included" in notes and "scratch.py" in notes
    assert "Skipped 1 binary file: logo.png" in notes


def test_changed_list_feeds_files_from_and_code2txt(repo, temp_dir):
    listing = run(CODE2PDF, ["--changed", "HEAD", "--list-files"], repo).stdout
    again = run(CODE2PDF, ["--files-from", "-", "--list-files"], repo, stdin=listing)
    assert again.returncode == 0 and again.stdout == listing
    out = temp_dir / "c.md"
    txt = run(CODE2TXT, ["--files-from", "-", "-o", str(out), "--summary", "Changes since HEAD."], repo, stdin=listing)
    assert txt.returncode == 0, txt.stdout + txt.stderr
    text = out.read_text()
    assert text.startswith("# Summary\n\nChanges since HEAD.\n\n# Table of Contents")
    assert "- new.py (marked 1-2)" in text
    section = text.split("## pkg/util.py (", 1)[1].split("\n```\n", 1)[0]
    assert "lines removed after 19" in section.split("\n")[0]
    assert "x19 = 19  # line 19\n... (lines removed here)\nx23 = 23  # line 23" in section


def test_pieces_grow_to_small_blocks_and_stop_at_big_ones():
    small = "def a():\n" + "".join(f"    s{n} = {n}\n" for n in range(10)) + "\n\ndef b():\n    return 2\n"
    assert changes.pieces(small, ((5, 5),), ()) == ((1, 11),)  # the enclosing function
    assert changes.pieces(small, ((5, 5), (14, 14)), ()) == ()  # most of the file: all of it
    big = "x = 0\n\n\ndef long():\n" + "".join(f"    v{n} = {n}\n" for n in range(100)) + "\n\ndef after():\n    pass\n"
    [(lo, hi)] = changes.pieces(big, ((50, 50),), ())
    assert (lo, hi) == (47, 53)  # the function has 101 lines: 3 lines of context each side
    two = changes.pieces(big, ((50, 50), (55, 55)), ())
    assert two == ((47, 58),)    # close pieces join
    # a decorator and comment above a small block come with it; context stops at a blank line
    deco = "import x\n\n\n# helper\n@cache\ndef f():\n    return 1\n" + "".join(f"y{n} = {n}\n" for n in range(40))
    assert changes.pieces(deco, ((7, 7),), ()) == ((4, 7),)


def test_changed_errors(repo, temp_dir):
    plain = temp_dir / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("x = 1\n")
    assert "needs a git repository" in run(CODE2PDF, ["-a", str(plain), "--changed", "HEAD", "--list-files"], temp_dir).stderr
    assert "unknown revision" in run(CODE2PDF, ["--changed", "nope", "--list-files"], repo).stderr
    assert "is a range" in run(CODE2PDF, ["--changed", "HEAD~1..HEAD", "--list-files"], repo).stderr
    both = run(CODE2PDF, ["--changed", "HEAD", "--files-from", "-", "--list-files"], repo, stdin="app.py\n")
    assert both.returncode != 0 and "not both" in both.stderr
    assert "--include has no effect with --changed" in run(CODE2PDF, ["--changed", "HEAD", "--include", "*.md"], repo).stderr
    assert "work with -a DIR" in run(CODE2PDF, ["-s", "app.py", "--changed", "HEAD"], repo).stderr
    assert "--summary needs a value" in run(CODE2PDF, ["-a", ".", "--summary"], repo).stderr
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "all")
    nothing = run(CODE2PDF, ["--changed", "HEAD", "-o", str(temp_dir / "n.pdf")], repo)
    assert nothing.returncode != 0 and "no file changed since HEAD" in nothing.stderr


def test_changed_without_git(repo, temp_dir):
    import shutil
    tools = temp_dir / "no-git-bin"  # what the launchers need, and no git
    tools.mkdir()
    for name in ("bash", "dirname", "readlink", "head", "tr", "wc", "cat"):
        found = shutil.which(name, path="/bin:/usr/bin")
        if found:
            (tools / name).symlink_to(found)
    # A checkout uses .venv; an install without one (CI, the .deb) needs python3 on PATH
    (tools / "python3").symlink_to(shutil.which("python3", path="/usr/bin:/bin") or sys.executable)
    env = {"HOME": os.environ["HOME"], "PATH": str(tools), "CODE2PDF_QUIET": "1"}
    result = subprocess.run([str(CODE2PDF), "--changed", "HEAD", "--list-files"], cwd=repo, env=env,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "needs git" in result.stderr and "Traceback" not in result.stderr


def test_changed_in_a_subfolder_and_with_exclude(repo):
    sub = run(CODE2PDF, ["-a", "pkg", "--changed", "HEAD", "--list-files"], repo)
    assert sub.returncode == 0, sub.stderr
    assert [line.split(":")[0] for line in sub.stdout.split()] == ["util.py"]  # relative to pkg/
    excluded = run(CODE2PDF, ["--changed", "HEAD", "--exclude", "pkg", "--list-files"], repo)
    assert [line.split(":")[0] for line in excluded.stdout.split()] == ["app.py", "new.py"]


@needs_render
@needs_pdftotext
def test_changed_pdf(repo, temp_dir):
    out = temp_dir / "change.pdf"
    result = run(CODE2PDF, ["--changed", "HEAD", "-o", str(out), "--summary", "The encoding fix."], repo)
    assert result.returncode == 0, result.stderr
    text = pdf_text(out)
    assert "The encoding fix." in text.split("app.py")[0]  # under the title, before the contents
    assert re.search(r"bars in the margin mark the \d+ lines changed\s+since HEAD \(\w+\)", text)
    assert "new.py (all 2 lines changed)" in text and "2 lines, all changed" in text
    assert "lines removed" in text
    import pypdf
    reader = pypdf.PdfReader(out)
    assert reader.metadata.subject == "The encoding fix."
    assert [item.title for item in reader.outline] == ["app.py", "new.py", "pkg/util.py"]


@needs_render
@needs_pdftotext
def test_parts_mode_prints_the_same_marks(repo, temp_dir):
    for i in range(10):
        (repo / f"m{i}.py").write_text("".join(f"def f{n}():\n    return {n}\n\n" for n in range(60)))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "more")
    for i in range(10):
        path = repo / f"m{i}.py"
        path.write_text(path.read_text().replace("return 30", "return -30").replace("def f50", "def g50"))
    single, parts = temp_dir / "single.pdf", temp_dir / "parts.pdf"
    args = ["--changed", "HEAD", "--summary", "Ten files."]
    assert run(CODE2PDF, [*args, "-o", str(single)], repo).returncode == 0
    env_parts = dict(CODE2PDF_PART_PAGES="1", CODE2PDF_JOBS="2")
    result = subprocess.run([str(CODE2PDF), *args, "-o", str(parts)], cwd=repo, capture_output=True, text=True,
                            timeout=180, env=dict(os.environ, CODE2PDF_QUIET="1", **env_parts))
    assert result.returncode == 0, result.stderr
    assert pdf_text(single) == pdf_text(parts)
    import pypdf
    assert pypdf.PdfReader(parts).metadata.subject == "Ten files."


# --- --summary -------------------------------------------------------------------------------

@needs_render
@needs_pdftotext
def test_summary_for_a_single_file(repo, temp_dir):
    out = temp_dir / "one.pdf"
    result = run(CODE2PDF, ["-s", "app.py:+5-6", "-o", str(out), "--summary", "Where files are opened."], repo)
    assert result.returncode == 0, result.stdout + result.stderr
    text = pdf_text(out)
    assert "Where files are opened." in text and "2 lines marked" in text
    import pypdf
    assert pypdf.PdfReader(out).metadata.subject == "Where files are opened."


@needs_render
def test_no_summary_no_subject(repo, temp_dir):
    out = temp_dir / "plain.pdf"
    assert run(CODE2PDF, ["-a", ".", "-o", str(out)], repo).returncode == 0
    import pypdf
    assert pypdf.PdfReader(out).metadata.subject is None
