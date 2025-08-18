"""Pytest configuration and shared fixtures for testing code2pdf and code2txt."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, Tuple
import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


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
def empty_dir(project_root) -> Path:
    """Get the empty directory."""
    return project_root / "tests" / "fixtures" / "empty_dir"


@pytest.fixture
def code2txt_path(project_root) -> Path:
    """Get the path to code2txt script."""
    return project_root / "bin" / "code2txt"


@pytest.fixture
def code2pdf_path(project_root) -> Path:
    """Get the path to code2pdf script."""
    return project_root / "bin" / "code2pdf"


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


def count_files_in_output(output_content: str) -> int:
    """Count the number of files in the output based on ## headers."""
    return output_content.count("\n## ")


def has_table_of_contents(output_content: str) -> bool:
    """Check if the output has a table of contents."""
    return "# Table of Contents" in output_content


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


@pytest.fixture
def create_symlink(temp_dir) -> Tuple[Path, Path]:
    """Create a symbolic link for testing."""
    target = temp_dir / "target.txt"
    target.write_text("This is the target file")
    
    link = temp_dir / "link.txt"
    link.symlink_to(target)
    
    return target, link


# Helper class for assertions
class OutputAssertions:
    """Helper class for common output assertions."""
    
    @staticmethod
    def assert_file_included(output: str, filename: str):
        """Assert that a file is included in the output."""
        assert f"## {filename}" in output or f"- {filename}" in output, \
            f"File {filename} not found in output"
    
    @staticmethod
    def assert_file_not_included(output: str, filename: str):
        """Assert that a file is not included in the output."""
        assert f"## {filename}" not in output, \
            f"File {filename} should not be in output"
    
    @staticmethod
    def assert_has_toc(output: str):
        """Assert that the output has a table of contents."""
        assert "# Table of Contents" in output, \
            "Table of contents not found in output"
    
    @staticmethod
    def assert_no_toc(output: str):
        """Assert that the output has no table of contents."""
        assert "# Table of Contents" not in output, \
            "Table of contents should not be in output"
    
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