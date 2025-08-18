# TASKS.md - Code2txt Implementation Plan

## Project Goal
Create a `code2txt` tool that combines source code files into a single text file optimized for LLM context input, with table of contents and proper formatting.

## Design Decisions

### Command-Line Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder` | positional | `.` | Target directory to process |
| `--output`, `-o` | string | `combined.txt` | Output filename |
| `--ignore-types` | string | `bin,pdf,jpg,png,gif,zip,tar,gz,exe,dll,so,dylib,class,jar,war,ear,pyc,pyo,txt` | File extensions to ignore (comma-separated) **Updated: Added txt to prevent recursive inclusion** |
| `--ignore-folders` | string | `node_modules,.git,dist,out,build,__pycache__,.venv,venv,env,.env,vendor,target` | Folders to skip (comma-separated) |
| `--include-types` | string | (optional) | Only include these file types (overrides ignore-types) |
| `--max-file-size` | string | `500K` | Skip files larger than this (e.g., 500K, 1M, 10M) |
| `--no-toc` | flag | false | Skip table of contents generation |
| `--verbose` | flag | false | Show processing details |
| `--help` | flag | - | Show help message |

### Output Format
```
# Table of Contents
- path/to/file1.js
- path/to/file2.py
- README.md

---

## path/to/file1.js
```javascript
// file content here
```

## path/to/file2.py
```python
# file content here
```

## README.md
```markdown
# file content here
```
```

## Implementation Tasks

### Phase 1: Core Scripts ✅ **COMPLETED**
- [x] Create `bin/code2txt` main entry script
  - [x] Parse command-line arguments
  - [x] Validate input directory exists
  - [x] Convert relative paths to absolute paths
  - [x] Check for help flag and display usage
  - [x] Pass parameters to processing script

- [x] Create `scripts/combine_to_txt.sh` processing script
  - [x] Implement directory traversal with symbolic link protection
  - [x] Apply file filtering (ignore-types, ignore-folders)
  - [x] Implement file size checking
  - [x] Detect file language for syntax highlighting in markdown
  - [x] Generate table of contents
  - [x] Combine files with proper markdown formatting
  - [x] Write output to specified file
  - [x] Cross-platform compatibility (Linux/macOS stat command)

### Phase 2: Language Detection ✅ **COMPLETED**
- [x] Create language detection function
  - [x] Map file extensions to language names for markdown code blocks
  - [x] Handle common file types without extensions (Dockerfile, Makefile, etc.)
  - [x] Default to 'text' for unknown file types

### Phase 3: Testing & Documentation ✅ **PARTIALLY COMPLETED**
- [x] Test with various directory structures
  - [x] Simple flat directory
  - [x] Nested directories
  - [x] Symbolic links (protection implemented)
  - [x] Large files (max-file-size parameter)
  - [x] Binary files (filtered by ignore-types)

- [x] Update README.md
  - [x] Add code2txt usage examples
  - [x] Document all parameters
  - [x] Add installation instructions

- [x] Update CLAUDE.md
  - [x] Document code2txt architecture
  - [x] Add development commands
  - [x] Document file processing logic

### Phase 3.5: Automated Testing Suite ✅ **COMPLETED**

#### Test Infrastructure Design
- **Framework**: pytest (Python 3.8+)
- **Approach**: Subprocess-based testing to test bash scripts
- **Coverage**: Unit tests, integration tests, and edge cases

#### Implemented Test Files

**requirements-test.txt**:
```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
pytest-timeout>=2.1.0
```

**Test Structure** ✅:
1. **conftest.py**: Shared fixtures and utilities
   - [x] Create temporary directories
   - [x] Generate sample files with different extensions
   - [x] Helper functions for running bash commands
   - [x] Cleanup functions
   - [x] Output assertions helper class

2. **test_code2txt.py**: Unit tests for code2txt (16 tests)
   - [x] Test default behavior
   - [x] Test output file creation
   - [x] Test ignore-types filtering
   - [x] Test include-types filtering
   - [x] Test ignore-folders filtering
   - [x] Test max-file-size limits
   - [x] Test table of contents generation
   - [x] Test no-toc option
   - [x] Test verbose output
   - [x] Test invalid directory handling
   - [x] Test empty directory handling
   - [x] Test symbolic link handling
   - [x] Test language detection accuracy
   - [x] Test file ordering
   - [x] Test current directory processing

3. **test_code2pdf.py**: Unit tests for code2pdf (10 tests)
   - [x] Test dependency checking
   - [x] Test single file conversion (-s)
   - [x] Test directory conversion (-a)
   - [x] Test PDF creation
   - [x] Test merged.pdf generation
   - [x] Test development mode (--dev) - skipped when not configured
   - [x] Test error handling
   - [x] Test invalid options
   - [x] Test file filtering

4. **test_integration.py**: Integration tests (8 tests)
   - [x] Test code2txt on real project structure
   - [x] Test code2pdf on real project structure
   - [x] Test both tools on same directory
   - [x] Test large repository simulation
   - [x] Test deep directory nesting
   - [x] Test mixed file types
   - [x] Test performance with many files
   - [x] Test unicode and special characters
   - [x] Test output consistency

#### Test Fixtures (Sample Files) ✅
- [x] **Programming files**: .py, .js, .java
- [x] **Config files**: Dockerfile, Makefile, .gitignore, settings.json
- [x] **Documentation**: README.md
- [x] **Binary files**: large_binary.bin (1MB for testing size limits)
- [x] **Empty files**: empty_file.py
- [x] **Files with special characters**: special_chars_file.sh (unicode, escaping)
- [x] **Sample project structure**: Complete project with src/, docs/, tests/, config/

#### Test Execution
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=.

# Run specific test file
pytest tests/test_code2txt.py

# Run with verbose output
pytest tests/ -v

# Run with timeout (prevent hanging tests)
pytest tests/ --timeout=30
```

### Phase 4: Enhancement (Optional)
- [ ] Add `--config` parameter to load settings from JSON file
- [ ] Add `--tree` flag to include directory tree structure
- [ ] Add `--stats` flag to show file count and total size statistics
- [ ] Add progress indicator for large directories
- [ ] Support for `.gitignore` pattern matching

## File Structure
```
code2pdf/
├── bin/
│   ├── code2pdf                  # Existing
│   └── code2txt                  # New ✅
├── scripts/
│   ├── print_all.sh              # Existing
│   ├── print_single_file_to_pdf.sh  # Existing
│   └── combine_to_txt.sh         # New ✅
├── config/
│   └── vimrc                     # Existing
├── tests/                        # Implemented ✅
│   ├── __init__.py              # Test package marker ✅
│   ├── conftest.py              # Pytest configuration and fixtures ✅
│   ├── test_code2txt.py         # 16 tests for code2txt ✅
│   ├── test_code2pdf.py         # 10 tests for code2pdf ✅
│   ├── test_integration.py      # 8 integration tests ✅
│   ├── README.md                # Testing documentation ✅
│   └── fixtures/                # Test data ✅
│       ├── sample_project/      # Complete sample project ✅
│       │   ├── src/            # Python, JS, Java files ✅
│       │   ├── docs/           # README.md ✅
│       │   ├── tests/          # test_main.py ✅
│       │   ├── config/         # settings.json ✅
│       │   ├── Dockerfile      # ✅
│       │   ├── Makefile        # ✅
│       │   └── .gitignore      # ✅
│       ├── edge_cases/         # Edge case files ✅
│       │   ├── large_binary.bin    # 1MB file ✅
│       │   ├── empty_file.py       # Empty file ✅
│       │   ├── special_chars_file.sh # Unicode/special chars ✅
│       │   └── large_file.txt      # Placeholder ✅
│       └── empty_dir/          # Empty directory for testing ✅
├── requirements-test.txt         # Test dependencies ✅
├── pytest.ini                   # Pytest configuration ✅
├── test_venv/                   # Virtual environment (git-ignored)
├── README.md                     # Updated ✅
├── CLAUDE.md                     # Updated ✅
└── TASKS.md                      # This file
```

## Language Mapping for Syntax Highlighting
| Extension | Language | Extension | Language |
|-----------|----------|-----------|----------|
| .js, .mjs, .cjs | javascript | .py | python |
| .ts, .tsx | typescript | .java | java |
| .jsx | javascript | .c | c |
| .cpp, .cc, .cxx | cpp | .h, .hpp | cpp |
| .cs | csharp | .go | go |
| .rs | rust | .rb | ruby |
| .php | php | .swift | swift |
| .kt, .kts | kotlin | .scala | scala |
| .sh, .bash | bash | .zsh | zsh |
| .ps1 | powershell | .bat, .cmd | batch |
| .html, .htm | html | .css | css |
| .scss, .sass | scss | .less | less |
| .xml | xml | .json | json |
| .yaml, .yml | yaml | .toml | toml |
| .md, .markdown | markdown | .rst | rst |
| .sql | sql | .r, .R | r |
| .m | matlab | .jl | julia |
| .lua | lua | .pl | perl |
| .vim | vim | .el | elisp |
| Dockerfile | dockerfile | Makefile | makefile |
| .env | bash | .gitignore | text |

## Current Status

### Completed Features
- ✅ **Phase 1**: Core functionality implemented and tested
- ✅ **Phase 2**: Language detection with comprehensive mapping
- ✅ **Phase 3**: Documentation completed (README.md and CLAUDE.md updated)
- ✅ **Phase 3.5**: Automated testing suite implemented with pytest
- ✅ All command-line parameters working as designed
- ✅ Cross-platform compatibility (Linux/macOS)
- ✅ Proper markdown formatting with syntax highlighting
- ✅ Table of contents generation
- ✅ Symbolic link recursion protection
- ✅ File size filtering
- ✅ Include/exclude type filtering
- ✅ Added `.txt` to default ignore list to prevent recursive inclusion

### Testing Status
- ✅ **34 automated tests** implemented (33 passing, 1 skipped)
- ✅ **Test coverage**: code2txt (16 tests), code2pdf (10 tests), integration (8 tests)
- ✅ **Test fixtures** created with sample projects and edge cases
- ✅ **Testing framework** configured with pytest
- ✅ All major functionality covered by tests
- ✅ Performance tests included
- ✅ Edge cases tested (empty files, special characters, large files)

### Next Steps
- **Phase 4**: Optional enhancements (config files, tree view, stats)
- **Future**: CI/CD integration for automated testing on commits

## Success Criteria
1. ✅ Tool can process a directory and output a single text file
2. ✅ Table of contents is generated and placed at the beginning
3. ✅ Each file is properly formatted with markdown code blocks
4. ✅ File paths are preserved and shown as headers
5. ✅ Configurable filtering for file types and folders
6. ✅ Handles edge cases (symbolic links, large files, binary files)
7. ✅ Clear error messages for common issues
8. ✅ Consistent with existing code2pdf tool design

## Notes
- Reuse directory traversal logic from existing `print_all.sh` script
- Keep dependencies minimal (bash, standard Unix tools)
- Ensure compatibility with both macOS and Linux
- Output format should be optimized for LLM token efficiency
- Consider file ordering (alphabetical within each directory)