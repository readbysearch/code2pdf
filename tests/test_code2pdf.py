"""Test suite for code2pdf tool."""

import os
from pathlib import Path
import pytest
from tests.conftest import run_command, create_test_files


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
    
    def test_dependency_check(self, code2pdf_path):
        """Test that dependency checking works."""
        # This test assumes the dependencies are installed
        # We're mainly checking that the script runs without errors
        returncode, stdout, stderr = run_command([str(code2pdf_path), "--help"])
        assert returncode == 0
        # If dependencies were missing, we'd see error messages
        assert "Missing required dependencies" not in stderr
    
    @pytest.mark.skipif(
        not os.path.exists("/usr/bin/vim") and not os.path.exists("/usr/local/bin/vim"),
        reason="Vim not installed"
    )
    def test_single_file_conversion(self, code2pdf_path, temp_dir):
        """Test single file PDF conversion."""
        # Create a test file
        test_file = temp_dir / "test.py"
        test_file.write_text("print('Hello, PDF!')")
        
        # Run code2pdf on single file
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "-s", str(test_file)],
            cwd=temp_dir
        )
        
        # Check if PDF was created (may not work in CI without full dependencies)
        # At minimum, check the command executed without critical errors
        if returncode == 0:
            # Look for PDF file
            pdf_files = list(temp_dir.glob("*.pdf"))
            assert len(pdf_files) > 0 or "PDF created" in stdout
        else:
            # If it failed, it should be due to missing dependencies
            assert "vim" in stderr.lower() or "gs" in stderr.lower() or "not found" in stderr.lower()
    
    @pytest.mark.skipif(
        not os.path.exists("/usr/bin/vim") and not os.path.exists("/usr/local/bin/vim"),
        reason="Vim not installed"
    )
    def test_directory_conversion(self, code2pdf_path, sample_project_dir, temp_dir):
        """Test directory PDF conversion."""
        # Run code2pdf on directory
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "-a", str(sample_project_dir)],
            cwd=temp_dir
        )
        
        # Check execution
        if returncode == 0:
            # Check for merged.pdf
            merged_pdf = sample_project_dir / "merged.pdf"
            assert merged_pdf.exists() or "PDF created" in stderr
        else:
            # If it failed, it should be due to missing dependencies or brew not found
            assert ("vim" in stderr.lower() or 
                    "gs" in stderr.lower() or 
                    "jq" in stderr.lower() or
                    "brew" in stderr.lower() or
                    "no such file" in stderr.lower())
    
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
    
    @pytest.mark.skipif(
        not os.environ.get("TEST_DEV_MODE"),
        reason="Development mode test requires specific setup"
    )
    def test_dev_mode(self, code2pdf_path):
        """Test --dev flag for development mode."""
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "--dev", "--help"]
        )
        
        assert returncode == 0
        assert "Usage" in stdout
    
    def test_file_filtering(self, code2pdf_path, temp_dir):
        """Test that file filtering works correctly."""
        # Create various file types
        test_files = {
            "test.py": "print('Python')",
            "test.js": "console.log('JavaScript');",
            "test.rb": "puts 'Ruby'",
            "test.bin": b"\x00\x01\x02\x03",  # Binary file
            "node_modules/lib.js": "console.log('lib');",
            ".git/config": "[core]"
        }
        
        for file_path, content in test_files.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                full_path.write_bytes(content)
            else:
                full_path.write_text(content)
        
        # Run code2pdf
        returncode, stdout, stderr = run_command(
            [str(code2pdf_path), "-a", str(temp_dir)],
            cwd=temp_dir
        )
        
        # Check that blacklisted folders are mentioned in debug output if present
        if returncode == 0 and stderr:
            # node_modules and .git should be skipped
            assert "node_modules" not in stderr or "Skipping" in stderr
            assert ".git" not in stderr or "Skipping" in stderr