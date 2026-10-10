#!/usr/bin/env bash

# code2pdf and code2txt Installation Script
# Installs both tools with a private Python environment (Pygments + WeasyPrint).
# On macOS, prefer Homebrew: brew install readbysearch/tap/code2pdf

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
GITHUB_REPO="readbysearch/code2pdf"
INSTALL_DIR_SYSTEM="/usr/local/bin"
INSTALL_DIR_USER="$HOME/.local/bin"
SHARE_DIR_SYSTEM="/usr/local/share/code2pdf"
SHARE_DIR_USER="$HOME/.local/share/code2pdf"

# Command line options
USER_INSTALL=false
SYSTEM_INSTALL=false
FORCE=false
SOURCE_DIR=""
REF="main"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --user)
            USER_INSTALL=true
            shift
            ;;
        --system)
            SYSTEM_INSTALL=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --from)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --ref)
            REF="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --user       Install for current user only (~/.local/bin)"
            echo "  --system     Install system-wide (/usr/local/bin, requires sudo)"
            echo "  --force      Skip confirmations"
            echo "  --from DIR   Install from a local checkout instead of downloading"
            echo "  --ref REF    Branch or tag to download (default: main)"
            echo "  -h, --help   Show this help message"
            echo ""
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ask a yes/no question; reads the terminal so it also works under `curl ... | bash`
confirm() {
    [[ "$FORCE" == true ]] && return 0
    local reply
    read -p "$1 (y/n): " -n 1 -r reply < /dev/tty
    echo
    [[ $reply =~ ^[Yy]$ ]]
}

# Display header
print_header() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    code2pdf & code2txt Installer                     ║"
    echo "║                                                                      ║"
    echo "║  • code2pdf: Convert source code to PDF with syntax highlighting    ║"
    echo "║  • code2txt: Combine source code into LLM-optimized text files      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect OS
detect_system() {
    print_info "Detecting system information..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        print_warning "On macOS, Homebrew is the recommended install:"
        echo "  brew install readbysearch/tap/code2pdf"
        confirm "Continue with this script anyway?" || exit 1
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi

    print_success "Detected: $OS ($(uname -m))"
}

# Check dependencies
check_dependencies() {
    print_info "Checking dependencies..."

    local missing=()

    if [[ -z "$SOURCE_DIR" ]] && ! command_exists "curl" && ! command_exists "wget"; then
        missing+=("curl or wget")
    fi
    if ! command_exists "tar"; then
        missing+=("tar")
    fi
    if ! command_exists "python3" || ! python3 -m venv --help >/dev/null 2>&1; then
        missing+=("python3 (with venv)")
    fi
    if ! command_exists "gs"; then
        missing+=("ghostscript")
    fi
    if ! command_exists "jq"; then
        missing+=("jq")
    fi

    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required dependencies: ${missing[*]}"
        echo "Install them first:"
        echo "  Ubuntu/Debian: sudo apt install curl python3-venv ghostscript jq libpango-1.0-0 libpangoft2-1.0-0"
        echo "  Fedora/RHEL:   sudo dnf install curl python3 ghostscript jq pango"
        echo "  macOS:         brew install readbysearch/tap/code2pdf  (installs everything)"
        exit 1
    fi

    print_success "All dependencies are available!"
}

# Determine install directories
determine_install_dir() {
    print_info "Determining installation directory..."

    if [[ "$SYSTEM_INSTALL" != true && "$USER_INSTALL" != true ]]; then
        if [[ -w "$INSTALL_DIR_SYSTEM" ]] || [[ $EUID -eq 0 ]]; then
            SYSTEM_INSTALL=true
        elif [[ "$FORCE" == true ]]; then
            USER_INSTALL=true
        else
            echo "Options:"
            echo "  1) Install system-wide (requires sudo) - available for all users"
            echo "  2) Install for current user only - no sudo required"
            echo ""
            local reply
            read -p "Choose option (1 or 2): " -n 1 -r reply < /dev/tty
            echo
            if [[ $reply == "1" ]]; then SYSTEM_INSTALL=true; else USER_INSTALL=true; fi
        fi
    fi

    if [[ "$SYSTEM_INSTALL" == true ]]; then
        INSTALL_DIR="$INSTALL_DIR_SYSTEM"
        SHARE_DIR="$SHARE_DIR_SYSTEM"
        if [[ $EUID -eq 0 ]] || [[ -w "$INSTALL_DIR_SYSTEM" ]]; then SUDO=""; else SUDO="sudo"; fi
    else
        INSTALL_DIR="$INSTALL_DIR_USER"
        SHARE_DIR="$SHARE_DIR_USER"
        SUDO=""
    fi
    print_info "Commands: $INSTALL_DIR   Files: $SHARE_DIR"
}

# Fetch the source tree into $SRC
fetch_source() {
    if [[ -n "$SOURCE_DIR" ]]; then
        SRC="$(cd "$SOURCE_DIR" && pwd)"
        print_info "Installing from local checkout: $SRC"
        return
    fi

    TEMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TEMP_DIR"' EXIT
    local url="https://github.com/$GITHUB_REPO/archive/$REF.tar.gz"
    print_info "Downloading $url"
    if command_exists "curl"; then
        curl -fsSL "$url" -o "$TEMP_DIR/code2pdf.tar.gz"
    else
        wget -q "$url" -O "$TEMP_DIR/code2pdf.tar.gz"
    fi
    tar -xzf "$TEMP_DIR/code2pdf.tar.gz" -C "$TEMP_DIR"
    SRC="$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)"
}

# Copy files, build the private Python environment, link the commands
install_tools() {
    fetch_source

    if [[ ! -f "$SRC/bin/code2pdf" || ! -f "$SRC/scripts/print_all.sh" ]]; then
        print_error "$SRC does not look like a code2pdf source tree"
        exit 1
    fi

    # Replace a previous install (only if it is really ours)
    if [[ -d "$SHARE_DIR" ]]; then
        if [[ -f "$SHARE_DIR/scripts/print_all.sh" ]]; then
            print_info "Replacing previous install in $SHARE_DIR"
            $SUDO rm -rf "$SHARE_DIR"
        else
            print_error "$SHARE_DIR exists but is not a code2pdf install; remove it first"
            exit 1
        fi
    fi

    print_info "Installing files..."
    $SUDO mkdir -p "$SHARE_DIR" "$INSTALL_DIR"
    $SUDO cp -R "$SRC/bin" "$SRC/scripts" "$SRC/config" "$SRC/requirements.txt" "$SHARE_DIR/"
    $SUDO chmod +x "$SHARE_DIR"/bin/* "$SHARE_DIR"/scripts/*.sh

    print_info "Creating Python environment with Pygments and WeasyPrint..."
    $SUDO python3 -m venv "$SHARE_DIR/venv"
    $SUDO "$SHARE_DIR/venv/bin/python3" -m pip install --quiet --disable-pip-version-check -r "$SHARE_DIR/requirements.txt"

    # The launchers find $SHARE_DIR by following these links
    for cmd in code2pdf code2txt; do
        $SUDO ln -sf "$SHARE_DIR/bin/$cmd" "$INSTALL_DIR/$cmd"
    done

    if ! "$SHARE_DIR/venv/bin/python3" -c "import weasyprint" 2>/dev/null; then
        print_error "WeasyPrint is installed but cannot load its system libraries (Pango)."
        echo "  Ubuntu/Debian: sudo apt install libpango-1.0-0 libpangoft2-1.0-0"
        echo "  Fedora/RHEL:   sudo dnf install pango"
        echo "Then re-run this installer. code2txt works already; code2pdf needs Pango."
        exit 1
    fi

    print_success "Tools installed successfully!"
}

# Configure PATH
configure_path() {
    print_info "Configuring PATH..."

    # Skip if installing to system directory (already in PATH)
    if [[ "$INSTALL_DIR" == "$INSTALL_DIR_SYSTEM" ]]; then
        print_info "System directory is already in PATH"
        return
    fi

    # Check if already in PATH
    if [[ ":$PATH:" == *":$INSTALL_DIR:"* ]]; then
        print_info "$INSTALL_DIR is already in PATH"
        return
    fi

    # Add to shell configuration files
    local shell_configs=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile")
    local updated_configs=()

    for config_file in "${shell_configs[@]}"; do
        if [[ -f "$config_file" ]]; then
            if ! grep -q "# Added by code2pdf installer" "$config_file" 2>/dev/null; then
                echo "" >> "$config_file"
                echo "# Added by code2pdf installer" >> "$config_file"
                echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$config_file"
                updated_configs+=("$(basename "$config_file")")
            fi
        fi
    done

    if [[ ${#updated_configs[@]} -gt 0 ]]; then
        print_success "Updated PATH in: ${updated_configs[*]}"
        print_warning "Please restart your shell or run: source ~/.bashrc"
    else
        print_info "PATH configuration not needed or already present"
    fi
}

# Verify installation by converting a real file
verify_installation() {
    print_info "Verifying installation..."

    local check_dir
    check_dir=$(mktemp -d)
    printf '# code2pdf check 你好\nprint("ok")\n' > "$check_dir/check.py"

    if ! (cd "$check_dir" && "$INSTALL_DIR/code2txt" -o out.md . >/dev/null 2>&1 && grep -q 'print("ok")' out.md); then
        print_error "code2txt did not run correctly"
        rm -rf "$check_dir"
        return 1
    fi
    print_success "code2txt runs correctly"

    if ! (cd "$check_dir" && "$INSTALL_DIR/code2pdf" -s check.py >/dev/null 2>&1 && [[ -s check.pdf ]]); then
        print_error "code2pdf could not create a PDF; run: $INSTALL_DIR/code2pdf -s <file> to see the error"
        rm -rf "$check_dir"
        return 1
    fi
    print_success "code2pdf runs correctly"
    rm -rf "$check_dir"

    if [[ "$OS" == "linux" ]] && command_exists fc-list && ! fc-list :lang=zh 2>/dev/null | grep -q .; then
        print_warning "No Chinese/Japanese/Korean fonts found. For CJK text run:"
        echo "  $SHARE_DIR/scripts/setup_cjk_fonts.sh sc   (or: sudo apt install fonts-noto-cjk)"
    fi
}

# Display usage information
show_usage() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                          Installation Complete!                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage examples:"
    echo "  code2txt                           # Process current directory"
    echo "  code2txt --include-types js,py     # Only include specific file types"
    echo "  code2pdf -a /path/to/project       # Convert project to PDF"
    echo "  code2pdf -s single_file.py         # Convert single file to PDF"
    echo ""
    echo "To uninstall: rm -rf \"$SHARE_DIR\" \"$INSTALL_DIR/code2pdf\" \"$INSTALL_DIR/code2txt\""
    echo ""
    print_info "GitHub: https://github.com/$GITHUB_REPO"
}

# Main installation flow
main() {
    print_header

    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. Tools will be installed system-wide."
    fi

    detect_system
    check_dependencies
    determine_install_dir
    install_tools
    configure_path

    if verify_installation; then
        show_usage
    else
        print_error "Installation verification failed"
        exit 1
    fi
}

main "$@"
