"""Pytest configuration and shared fixtures for testing code2pdf and code2txt."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Generator, Tuple
import pytest

#: Tests that run shell scripts, symlinks or umask: not on Windows
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX shell, symlinks or umask")

#: The code2pdf the tests run: bin/code2pdf, or $CODE2PDF_EXE (the Windows build's code2pdf.exe)
CODE2PDF = os.environ.get("CODE2PDF_EXE") or str(Path(__file__).parent.parent / "bin" / "code2pdf")

# The bash launchers, install.sh and code2txt aren't part of the Windows build, and it stops differently (no
# process groups or SIGINT there)
POSIX_ONLY = {"test_launcher.py", "test_install_sh.py", "test_print_all_tmp.py", "test_interrupt.py", "test_code2txt.py",
              "test_code2txt_output.py", "test_code2txt_files_from.py"}


def pytest_collection_modifyitems(config, items):
    if sys.platform == "win32":
        skip = pytest.mark.skip(reason="not part of the Windows build")
        for item in items:
            if item.path.name in POSIX_ONLY:
                item.add_marker(skip)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup; on Windows, git makes its object files read-only
    def writable(function, path, *_):
        os.chmod(path, 0o700)
        function(path)
    if temp_path.exists():
        shutil.rmtree(temp_path, onerror=writable)


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_project_dir(project_root) -> Path:
    """Get the sample project directory."""
    return project_root / "tests" / "fixtures" / "sample_project"


@pytest.fixture
def edge_cases_dir(project_root) -> Path:
    """Get the edge cases directory."""
    return project_root / "tests" / "fixtures" / "edge_cases"


@pytest.fixture
def empty_dir(temp_dir) -> Path:
    """A real, empty directory."""
    path = temp_dir / "empty"
    path.mkdir()
    return path


@pytest.fixture
def code2txt_path(project_root) -> Path:
    """Get the path to code2txt script."""
    return project_root / "bin" / "code2txt"


@pytest.fixture
def code2pdf_path(project_root) -> Path:
    """The code2pdf to test (CODE2PDF)."""
    return Path(CODE2PDF)


def run_command(cmd: list, cwd: Path = None, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Run a shell command and return the result.
    
    Args:
        cmd: Command to run as a list of strings
        cwd: Working directory for the command
        timeout: Timeout in seconds
    
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def create_test_files(directory: Path, files: dict) -> None:
    """
    Create test files in a directory.
    
    Args:
        directory: Directory to create files in
        files: Dictionary mapping file paths to content
    """
    for file_path, content in files.items():
        full_path = directory / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)


def read_output_file(file_path: Path) -> str:
    """Read and return the content of an output file."""
    if not file_path.exists():
        return ""
    return file_path.read_text()


def get_language_from_output(output_content: str, filename: str) -> str:
    """Extract the language identifier used for a file in the output."""
    file_section = f"## {filename}"
    if file_section not in output_content:
        return ""
    
    start_idx = output_content.find(file_section)
    if start_idx == -1:
        return ""
    
    # Look for the code block start after the file header
    code_block_start = output_content.find("```", start_idx)
    if code_block_start == -1:
        return ""
    
    # Extract the language identifier
    code_block_line_end = output_content.find("\n", code_block_start)
    if code_block_line_end == -1:
        return ""
    
    language = output_content[code_block_start + 3:code_block_line_end].strip()
    return language


@pytest.fixture
def create_large_file(temp_dir) -> Path:
    """Create a large file for testing size limits."""
    large_file = temp_dir / "large_file.txt"
    # Create a 2MB file
    content = "x" * (2 * 1024 * 1024)
    large_file.write_text(content)
    return large_file


# Helper class for assertions
class OutputAssertions:
    """Helper class for common output assertions."""
    
    
    
    
    
    @staticmethod
    def assert_language(output: str, filename: str, expected_language: str):
        """Assert that a file has the expected language in code block."""
        language = get_language_from_output(output, filename)
        assert language == expected_language, \
            f"Expected language '{expected_language}' for {filename}, got '{language}'"


@pytest.fixture
def assertions():
    """Provide assertion helpers."""
    return OutputAssertions()