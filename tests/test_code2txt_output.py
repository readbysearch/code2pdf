"""code2txt must never read its own output file."""

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_output_inside_target_dir_is_skipped(temp_dir):
    """Writing e.g. notes.md into the scanned folder used to make code2txt append it to itself forever."""
    (temp_dir / "a.py").write_text("print('a')\n")
    result = subprocess.run(
        [str(PROJECT_ROOT / "bin" / "code2txt"), "-o", "notes.md", "."],
        cwd=temp_dir, capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = (temp_dir / "notes.md").read_text()
    assert "## a.py" in output
    assert "## notes.md" not in output
    assert len(output) < 10_000
