"""Test suite for code2txt tool."""

import os
from pathlib import Path
import pytest
from tests.conftest import run_command, create_test_files, read_output_file


class TestCode2txt:
    """Test cases for code2txt functionality."""
    
    def test_help_option(self, code2txt_path):
        """Test that --help option works."""
        returncode, stdout, stderr = run_command([str(code2txt_path), "--help"])
        assert returncode == 0
        assert "Usage: code2txt" in stdout
        assert "Options:" in stdout
        assert "--output" in stdout
    
    def test_default_behavior(self, code2txt_path, sample_project_dir, temp_dir):
        """Test default behavior with sample project."""
        output_file = temp_dir / "combined.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(sample_project_dir)]
        )
        
        assert returncode == 0
        assert output_file.exists()
        assert "Successfully created" in stdout
        
        content = read_output_file(output_file)
        assert "# Table of Contents" in content
        assert "main.py" in content
        assert "utils.js" in content
        assert "app.java" in content
    
    def test_output_file_option(self, code2txt_path, sample_project_dir, temp_dir):
        """Test custom output file option."""
        custom_output = temp_dir / "custom_output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(custom_output), str(sample_project_dir)]
        )
        
        assert returncode == 0
        assert custom_output.exists()
        assert str(custom_output.name) in stdout
    
    def test_include_types(self, code2txt_path, sample_project_dir, temp_dir):
        """Test --include-types option."""
        output_file = temp_dir / "python_only.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), 
             "--include-types", "py",
             "-o", str(output_file),
             str(sample_project_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "main.py" in content
        assert "test_main.py" in content
        assert "utils.js" not in content
        assert "app.java" not in content
    
    def test_ignore_types(self, code2txt_path, temp_dir):
        """Test --ignore-types option."""
        # Create test files
        test_files = {
            "test.py": "print('Python')",
            "test.js": "console.log('JavaScript');",
            "test.txt": "Text file",
            "test.md": "# Markdown"
        }
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--ignore-types", "txt,md",
             "-o", str(output_file),
             str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "test.py" in content
        assert "test.js" in content
        assert "test.txt" not in content
        assert "test.md" not in content
    
    def test_ignore_folders(self, code2txt_path, temp_dir):
        """Test --ignore-folders option."""
        # Create test directory structure
        test_files = {
            "src/main.py": "print('main')",
            "tests/test.py": "print('test')",
            "node_modules/lib.js": "console.log('lib');",
            "dist/bundle.js": "console.log('bundle');"
        }
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--ignore-folders", "node_modules,dist",
             "-o", str(output_file),
             str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "src/main.py" in content
        assert "tests/test.py" in content
        assert "node_modules" not in content
        assert "dist" not in content
    
    def test_max_file_size(self, code2txt_path, temp_dir, create_large_file):
        """Test --max-file-size option."""
        # Create a small file
        small_file = temp_dir / "small.py"
        small_file.write_text("print('small')")
        
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--max-file-size", "1K",
             "-o", str(output_file),
             str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "small.py" in content
        assert "large_file.txt" not in content
    
    def test_no_toc_option(self, code2txt_path, sample_project_dir, temp_dir):
        """Test --no-toc option."""
        output_file = temp_dir / "no_toc.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--no-toc",
             "-o", str(output_file),
             str(sample_project_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "# Table of Contents" not in content
        assert "## " in content  # Files should still be included
    
    def test_verbose_option(self, code2txt_path, sample_project_dir, temp_dir):
        """Test --verbose option."""
        output_file = temp_dir / "verbose.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--verbose",
             "-o", str(output_file),
             str(sample_project_dir)]
        )
        
        assert returncode == 0
        assert "Configuration:" in stdout or "Processing:" in stderr
    
    def test_empty_directory(self, code2txt_path, empty_dir, temp_dir):
        """Test behavior with empty directory."""
        output_file = temp_dir / "empty.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "-o", str(output_file),
             str(empty_dir)]
        )
        
        # Should handle empty directory gracefully
        assert returncode == 1 or "No files were processed" in stderr
    
    def test_invalid_directory(self, code2txt_path, temp_dir):
        """Test behavior with invalid directory."""
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "-o", str(output_file),
             "/nonexistent/directory"]
        )
        
        assert returncode != 0
        assert "does not exist" in stderr or "Error" in stderr or "does not exist" in stdout or "Error" in stdout
    
    def test_language_detection(self, code2txt_path, temp_dir, assertions):
        """Test language detection for various file types."""
        test_files = {
            "test.py": "print('Python')",
            "test.js": "console.log('JavaScript');",
            "test.java": "public class Test {}",
            "test.cpp": "#include <iostream>",
            "test.sh": "#!/bin/bash",
            "test.md": "# Markdown",
            "Dockerfile": "FROM ubuntu",
            "Makefile": "all:"
        }
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "-o", str(output_file),
             str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # Check language detection
        assertions.assert_language(content, "test.py", "python")
        assertions.assert_language(content, "test.js", "javascript")
        assertions.assert_language(content, "test.java", "java")
        assertions.assert_language(content, "test.cpp", "cpp")
        assertions.assert_language(content, "test.sh", "bash")
        assertions.assert_language(content, "test.md", "markdown")
        assertions.assert_language(content, "Dockerfile", "dockerfile")
        assertions.assert_language(content, "Makefile", "makefile")
    
    def test_special_characters(self, code2txt_path, edge_cases_dir, temp_dir):
        """Test handling of files with special characters."""
        output_file = temp_dir / "special.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--include-types", "sh",
             "-o", str(output_file),
             str(edge_cases_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "special_chars_file.sh" in content
        # Check that special characters are preserved
        assert "$@" in content or "Unicode" in content
    
    def test_current_directory(self, code2txt_path, temp_dir):
        """Test running code2txt without specifying directory (use current)."""
        # Create test files in temp directory
        test_files = {
            "test.py": "print('test')",
            "test.js": "console.log('test');"
        }
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file)],
            cwd=temp_dir
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "test.py" in content
        assert "test.js" in content
    
    def test_multiple_include_types(self, code2txt_path, sample_project_dir, temp_dir):
        """Test --include-types with multiple extensions."""
        output_file = temp_dir / "multi_types.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "--include-types", "py,js",
             "-o", str(output_file),
             str(sample_project_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        assert "main.py" in content
        assert "utils.js" in content
        assert "app.java" not in content
        assert "settings.json" not in content
    
    def test_file_ordering(self, code2txt_path, temp_dir):
        """Test that files are sorted alphabetically in output."""
        test_files = {
            "zebra.py": "print('z')",
            "apple.py": "print('a')",
            "banana.py": "print('b')",
            "cat/dog.py": "print('d')"
        }
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "sorted.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path),
             "-o", str(output_file),
             str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # Check files appear in alphabetical order
        apple_pos = content.find("apple.py")
        banana_pos = content.find("banana.py")
        cat_dog_pos = content.find("cat/dog.py")
        zebra_pos = content.find("zebra.py")
        
        assert apple_pos < banana_pos < cat_dog_pos < zebra_pos