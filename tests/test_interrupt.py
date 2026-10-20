"""A killed conversion must not leave temp files or orphaned renderers behind.

Coding agents run code2pdf under a command timeout (Claude Code's Bash tool stops commands
after 2 minutes by default). Before v3.9.1 a SIGTERM to `code2pdf` left Python and its parts
workers running, and a SIGTERM to the whole group left .code2pdf-*.pdf and
.code2pdf-parts-* in the project.
"""

import os
import signal
import subprocess
import time
from pathlib import Path
import pytest

from tests.test_launcher import PROJECT_ROOT, repo_venv_has_deps, isolated_path
from tests.conftest import CODE2PDF  # noqa: E402

pytestmark = pytest.mark.skipif(not repo_venv_has_deps(), reason="repo .venv lacks pygments/weasyprint")


def big_project(root: Path) -> Path:
    project = root / "big"
    for i in range(40):
        path = project / f"pkg{i % 4}" / f"module_{i:02d}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"def f{n}(x):\n    return x * {n}  # line {n}\n" for n in range(400)))
    return project


def start(project: Path, new_session=False):
    env = {"HOME": os.environ["HOME"], "PATH": isolated_path(project), "CODE2PDF_QUIET": "1",
           "CODE2PDF_PART_PAGES": "20", "CODE2PDF_JOBS": "2"}
    return subprocess.Popen([CODE2PDF, "-a", str(project)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=new_session)


def wait_for_parts(project: Path, proc, timeout=60):
    """Until the parts workers have started (their temp folder exists)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(p.name.startswith(".code2pdf-parts-") for p in project.iterdir()):
            time.sleep(1.5)  # let the workers get going
            return
        assert proc.poll() is None, proc.communicate()
        time.sleep(0.1)
    pytest.fail("parts mode never started")


def descendants(pid):
    """Every process below PID (recorded while the conversion runs, before any signal)."""
    table = {}
    for line in subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout.splitlines():
        child, parent = map(int, line.split())
        table.setdefault(parent, []).append(child)
    found, todo = [], [pid]
    while todo:
        for child in table.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def alive(pids):
    """PIDS still running. A zombie has exited: in a container whose init doesn't reap (GitHub
    Actions runs `tail -f /dev/null` as PID 1), Python 3.12's resource tracker, which exits just
    after its parent, stays one."""
    out = []
    for pid in pids:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                               text=True).stdout.strip()
        if state and not state.startswith("Z"):
            out.append(pid)
    return out


def assert_clean(project: Path, tree, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        leftovers = [p.name for p in project.iterdir() if p.name.startswith(".code2pdf-")]
        running = alive(tree)
        if not leftovers and not running:
            break
        time.sleep(0.2)
    for pid in running:  # don't leave them running if the test fails
        os.kill(pid, signal.SIGKILL)
    assert not leftovers, leftovers
    assert not running, running
    assert not (project / "merged.pdf").exists()


@pytest.mark.parametrize("how", ["launcher", "group"])
def test_sigterm_stops_everything_and_cleans_up(temp_dir, how):
    project = big_project(temp_dir)
    proc = start(project, new_session=(how == "group"))
    tree = []
    try:
        wait_for_parts(project, proc)
        tree = descendants(proc.pid)
        assert len(tree) >= 3, tree  # python and its workers
        if how == "launcher":
            proc.send_signal(signal.SIGTERM)  # a timeout that only signals the command itself
        else:
            os.killpg(proc.pid, signal.SIGTERM)  # a timeout that signals the process group
        proc.wait(timeout=20)
        assert proc.returncode != 0
        stderr = proc.stderr.read().decode()
        assert "code2pdf: stopped" in stderr and "Traceback" not in stderr, stderr
        assert_clean(project, tree)
    finally:
        if proc.poll() is None:
            proc.kill()
        for pid in alive(tree):
            os.kill(pid, signal.SIGKILL)


def test_ctrl_c_cleans_up(temp_dir):
    project = big_project(temp_dir)
    proc = start(project, new_session=True)
    tree = []
    try:
        wait_for_parts(project, proc)
        tree = descendants(proc.pid)
        os.killpg(proc.pid, signal.SIGINT)  # Ctrl-C reaches the whole foreground group
        proc.wait(timeout=20)
        assert proc.returncode != 0
        stderr = proc.stderr.read().decode()
        assert "code2pdf: stopped" in stderr and "Traceback" not in stderr, stderr
        assert_clean(project, tree)
    finally:
        if proc.poll() is None:
            proc.kill()
        for pid in alive(tree):
            os.kill(pid, signal.SIGKILL)
