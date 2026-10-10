"""Test suite for code2pdf tool."""

from tests.conftest import run_command


class TestCode2pdf:
    """Test cases for code2pdf functionality."""
    
    def test_help_option(self, code2pdf_path):
        """Test that --help option works."""
        returncode, stdout, stderr = run_command([str(code2pdf_path), "--help"])
        assert returncode == 0
        assert "Usage: code2pdf" in stdout
        assert "Options:" in stdout
        assert "-s, --single" in stdout
        assert "-a, --all" in stdout
    
    
    
    
    def test_invalid_option(self, code2pdf_path):
        """Test behavior with invalid option."""
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "--invalid-option"]
        )
        
        assert returncode != 0
        assert "help" in stdout.lower() or "usage" in stdout.lower()
    
    def test_no_arguments(self, code2pdf_path):
        """Test behavior when no arguments provided."""
        returncode, stdout, stderr = run_command([str(code2pdf_path)])
        
        assert returncode != 0
        assert "Usage" in stdout or "help" in stdout.lower()
    
    def test_single_file_nonexistent(self, code2pdf_path):
        """Test single file conversion with nonexistent file."""
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "-s", "/nonexistent/file.py"]
        )
        
        assert returncode != 0
        assert "not found" in stderr.lower() or "no such file" in stderr.lower()
    
    def test_directory_nonexistent(self, code2pdf_path):
        """Test directory conversion with nonexistent directory."""
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "-a", "/nonexistent/directory"]
        )
        
        # Should fail gracefully
        assert returncode != 0

    def test_dev_flag_is_accepted(self, code2pdf_path):
        """--dev is a no-op kept for compatibility (the launcher always uses its own install)."""
        returncode, stdout, stderr = run_command([str(code2pdf_path), "--dev", "--help"])
        assert returncode == 0
        assert "Usage: code2pdf" in stdout
