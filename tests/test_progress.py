"""Progress reporting for long conversions."""

import io
import os
import re
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable


def has_render_deps() -> bool:
    return subprocess.run([PYTHON, "-c", "import pygments, weasyprint"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not has_render_deps(), reason="pygments/weasyprint not available")


@pytest.fixture(scope="module")
def progress():
    sys.path.insert(0, str(SCRIPTS))
    import progress
    return progress


class TtyStream(io.StringIO):
    def isatty(self):
        return True


def test_page_estimate_counts_wrapped_lines(progress):
    short = "x = 1\n" * 590                       # about 10 pages of short lines
    long_lines = ("y" * 200 + "\n") * 295         # 295 lines, each wraps to 3 rows: ~885 rows
    assert 9 <= progress.estimate_pages([short]) <= 12
    assert 14 <= progress.estimate_pages([long_lines]) <= 18
    # every file starts on a new page, plus the contents page
    assert progress.estimate_pages(["a\n", "b\n", "c\n"], contents=True) == 4


def test_terminal_output_updates_one_line(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=3, lines=120, estimated_pages=10)
    for page in range(1, 11):
        p.page(page)
    p.writing()
    p.done(pages=10, output="/tmp/out.pdf")
    out = stream.getvalue()
    assert out.startswith("code2pdf: 3 files, 120 lines (~10 pages)")
    assert "\r" in out and "[2/3] Laying out page 10 of ~10" in out
    assert "[3/3] Writing PDF" in out
    assert re.search(r"Done: 10 pages in \d+:\d\d", out)


def test_estimate_grows_when_exceeded(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=5)
    p.page(7)
    assert "page 7 of ~" in stream.getvalue()
    assert "of ~5" not in stream.getvalue().split("\r")[-1]


def test_log_output_prints_every_ten_percent(progress):
    stream = io.StringIO()  # not a terminal
    p = progress.Progress(stream, files=2, lines=50, estimated_pages=100)
    for page in range(1, 101):
        p.page(page)
    p.done(pages=100, output="out.pdf")
    lines = stream.getvalue().splitlines()
    assert "\r" not in stream.getvalue()
    assert 9 <= sum("Laying out page" in l for l in lines) <= 11


def test_quiet_prints_nothing(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=2, lines=50, estimated_pages=10, quiet=True)
    p.page(1)
    p.done(pages=1, output="out.pdf")
    assert stream.getvalue() == ""


def test_conversion_reports_progress(temp_dir):
    for i in range(3):
        (temp_dir / f"f{i}.py").write_text("x = 1\n" * 200)
    cmd = [PYTHON, str(SCRIPTS / "dir_to_pdf.py"), str(temp_dir), str(temp_dir / "merged.pdf"),
           "[]", "env*", '["py"]', "[]", "true", "", "", "", ""]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "code2pdf: 3 files, 600 lines" in result.stderr
    assert "Laying out page" in result.stderr
    assert re.search(r"Done: \d+ pages in \d+:\d\d", result.stderr)


def test_silent_stages_keep_ticking_in_a_terminal(progress):
    import time
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=5, tick=0.05)
    p.preparing()
    time.sleep(0.3)
    p.page(1)
    p.writing()
    time.sleep(0.3)
    p.done(pages=5, output="out.pdf")
    out = stream.getvalue()
    assert out.count("[1/3] Preparing") >= 3
    assert out.count("[3/3] Writing PDF") >= 3
    after_done = out.split("Done:")[1]
    time.sleep(0.2)
    assert stream.getvalue().split("Done:")[1] == after_done  # ticker stopped


def test_time_left_includes_writing(progress, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: clock[0])
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=100, tick=None)
    p.page(1)
    clock[0] += 10.0  # 10 s for 50 pages: ~10 s more layout, ~10 s of writing (0.5 x 20 s)
    p.page(50)
    assert "~0:20 left" in stream.getvalue().split("\r")[-1]


from tests.conftest import CODE2PDF, posix_only  # noqa: E402


def _code2pdf(args, cwd, umask=None):
    env = {k: v for k, v in os.environ.items() if k != "CODE2PDF_QUIET"}
    return subprocess.run([str(CODE2PDF), *args], cwd=cwd, capture_output=True, text=True, timeout=180, env=env,
                          preexec_fn=(lambda: os.umask(umask)) if umask is not None else None)


def test_single_file_reports_progress(temp_dir):
    """-s used to say nothing while it worked: a 500-page file looked stuck for a minute."""
    (temp_dir / "a.py").write_text("x = 1\n" * 200)
    result = _code2pdf(["-s", "a.py", "-o", "a.pdf"], temp_dir)
    assert result.returncode == 0, result.stderr
    assert "code2pdf: 1 file, 200 lines" in result.stderr
    assert "Laying out page" in result.stderr
    assert re.search(r"Done: \d+ pages? in \d+:\d\d", result.stderr)
    assert "PDF created at a.pdf" in result.stdout  # as before, for scripts that read it

    quiet = _code2pdf(["-q", "-s", "a.py", "-o", "b.pdf"], temp_dir)
    assert quiet.returncode == 0, quiet.stderr
    assert "code2pdf:" not in quiet.stderr and "Done:" not in quiet.stderr


@pytest.mark.parametrize("umask", [0o022, 0o027])
@posix_only
def test_pdfs_get_normal_permissions(temp_dir, umask):
    """The PDF is written to a temporary file first, which mkstemp makes private (0600)."""
    (temp_dir / "src").mkdir()
    for i in range(3):
        (temp_dir / "src" / f"f{i}.py").write_text("x = 1\n" * 300)
    runs = {"single": ["-s", "src/f0.py", "-o", "single.pdf"], "folder": ["-a", "src", "-o", "folder.pdf"]}
    for name, args in runs.items():
        result = _code2pdf(args, temp_dir, umask)
        assert result.returncode == 0, result.stderr
        assert (temp_dir / f"{name}.pdf").stat().st_mode & 0o777 == 0o666 & ~umask, name
    env_parts = dict(os.environ, CODE2PDF_PART_PAGES="2", CODE2PDF_QUIET="1")
    parts = subprocess.run([str(CODE2PDF), "-a", "src", "-o", "parts.pdf"], cwd=temp_dir, capture_output=True,
                           text=True, timeout=180, env=env_parts, preexec_fn=lambda: os.umask(umask))
    assert parts.returncode == 0, parts.stderr
    assert (temp_dir / "parts.pdf").stat().st_mode & 0o777 == 0o666 & ~umask
    assert "leaked" not in parts.stderr  # exiting without the usual cleanup leaves nothing behind
