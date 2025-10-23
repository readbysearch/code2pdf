"""Integration tests for code2pdf and code2txt tools."""

import os
from pathlib import Path
import time
import pytest
from tests.conftest import run_command, create_test_files, read_output_file


class TestIntegration:
    """Integration test cases for both tools."""
    
    def test_both_tools_same_directory(self, code2txt_path, code2pdf_path, sample_project_dir, temp_dir):
        """Test running both tools on the same directory."""
        # Run code2txt
        txt_output = temp_dir / "output.txt"
        txt_returncode, txt_stdout, txt_stderr = run_command(
            [str(code2txt_path), "-o", str(txt_output), str(sample_project_dir)]
        )
        
        assert txt_returncode == 0
        assert txt_output.exists()
        
        # Run code2pdf (may fail without dependencies)
        pdf_returncode, pdf_stdout, pdf_stderr = run_command(
            [str(code2pdf_path), "-a", str(sample_project_dir)],
            timeout=60
        )
        
        # Both should at least run without crashing
        assert txt_output.exists()
        
        # Check that text output contains expected files
        txt_content = read_output_file(txt_output)
        assert "main.py" in txt_content
        assert "utils.js" in txt_content
    
    def test_large_repository_simulation(self, code2txt_path, temp_dir):
        """Test with a simulated large repository structure."""
        # Create a multi-level directory structure
        files = {}
        for i in range(5):  # 5 top-level directories
            for j in range(3):  # 3 subdirectories each
                for k in range(2):  # 2 files in each subdirectory
                    path = f"dir{i}/subdir{j}/file{k}.py"
                    files[path] = f"# File {i}-{j}-{k}\nprint('test')"
        
        create_test_files(temp_dir, files)
        
        output_file = temp_dir / "large_output.txt"
        start_time = time.time()
        
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)],
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        assert returncode == 0
        assert output_file.exists()
        
        content = read_output_file(output_file)
        # Should contain all 30 files (5 * 3 * 2)
        file_count = content.count("\n## ")
        assert file_count == 30
        
        # Performance check - should complete reasonably quickly
        assert elapsed_time < 30  # Should finish within 30 seconds
    
    def test_mixed_content_types(self, code2txt_path, temp_dir):
        """Test with various content types mixed together."""
        test_files = {
            # Code files
            "src/backend/server.py": "from flask import Flask\napp = Flask(__name__)",
            "src/frontend/app.js": "const express = require('express');",
            "src/styles/main.css": "body { margin: 0; padding: 0; }",
            
            # Config files
            "config/database.yml": "database:\n  host: localhost",
            "package.json": '{"name": "test", "version": "1.0.0"}',
            ".env.example": "API_KEY=your_key_here",
            
            # Documentation
            "README.md": "# Mixed Content Project",
            "docs/API.md": "## API Documentation",
            
            # Build files
            "Dockerfile": "FROM node:14",
            "Makefile": "build:\n\techo 'Building...'",
            
            # Should be ignored
            "dist/bundle.js": "minified code",
            "node_modules/lib/index.js": "library code",
            ".git/HEAD": "ref: refs/heads/main",
            "image.jpg": "binary_content",
            "data.pdf": "pdf_content"
        }
        
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "mixed_output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # Check included files
        assert "server.py" in content
        assert "app.js" in content
        assert "main.css" in content
        assert "database.yml" in content
        assert "package.json" in content
        assert "README.md" in content
        assert "Dockerfile" in content
        assert "Makefile" in content
        
        # Check excluded files
        assert "dist/bundle.js" not in content
        assert "node_modules" not in content
        assert ".git" not in content
        assert "image.jpg" not in content
        assert "data.pdf" not in content
    
    def test_unicode_and_special_chars(self, code2txt_path, temp_dir):
        """Test handling of unicode and special characters."""
        test_files = {
            "unicode.py": "# -*- coding: utf-8 -*-\nprint('你好世界 🌍')",
            "special.sh": "echo 'Special: $HOME `date` \\ \" \\n'",
            "emoji.js": "const emoji = '😀🎉🚀';",
            "math.tex": "\\begin{equation} E = mc^2 \\end{equation}"
        }
        
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "unicode_output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # Check that unicode is preserved
        assert "你好世界" in content
        assert "🌍" in content
        assert "😀" in content
        
        # Check that special characters are preserved
        assert "$HOME" in content
        assert "\\begin{equation}" in content
    
    def test_empty_files_handling(self, code2txt_path, temp_dir):
        """Test handling of empty files."""
        test_files = {
            "empty.py": "",
            "normal.py": "print('not empty')",
            "empty.js": "",
            "normal.js": "console.log('not empty');"
        }
        
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "empty_files.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # All files should be included, even empty ones
        assert "empty.py" in content
        assert "normal.py" in content
        assert "empty.js" in content
        assert "normal.js" in content
    
    def test_deep_nesting(self, code2txt_path, temp_dir):
        """Test with deeply nested directory structure."""
        # Create a very deep directory structure
        deep_path = "level1/level2/level3/level4/level5/level6/level7/level8"
        test_files = {
            f"{deep_path}/deep_file.py": "print('Deep file')",
            "shallow.py": "print('Shallow file')"
        }
        
        create_test_files(temp_dir, test_files)
        
        output_file = temp_dir / "deep_output.txt"
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)]
        )
        
        assert returncode == 0
        content = read_output_file(output_file)
        
        # Both files should be found
        assert "deep_file.py" in content
        assert "shallow.py" in content
        assert "Deep file" in content
    
    def test_performance_many_small_files(self, code2txt_path, temp_dir):
        """Test performance with many small files."""
        # Create 100 small files
        files = {}
        for i in range(100):
            files[f"file_{i:03d}.py"] = f"# File {i}\nprint({i})"
        
        create_test_files(temp_dir, files)
        
        output_file = temp_dir / "many_files.txt"
        start_time = time.time()
        
        returncode, stdout, stderr = run_command(
            [str(code2txt_path), "-o", str(output_file), str(temp_dir)],
            timeout=30
        )
        
        elapsed_time = time.time() - start_time
        
        assert returncode == 0
        assert output_file.exists()
        
        content = read_output_file(output_file)
        file_count = content.count("\n## ")
        assert file_count == 100
        
        # Should handle 100 files quickly
        assert elapsed_time < 10
    
    def test_output_consistency(self, code2txt_path, temp_dir):
        """Test that output is consistent across multiple runs."""
        test_files = {
            "a.py": "print('a')",
            "b.py": "print('b')",
            "c.py": "print('c')"
        }
        
        create_test_files(temp_dir, test_files)
        
        # Run twice
        output1 = temp_dir / "output1.txt"
        output2 = temp_dir / "output2.txt"
        
        run_command([str(code2txt_path), "-o", str(output1), str(temp_dir)])
        run_command([str(code2txt_path), "-o", str(output2), str(temp_dir)])
        
        content1 = read_output_file(output1)
        content2 = read_output_file(output2)
        
        # Output should be identical
        assert content1 == content2