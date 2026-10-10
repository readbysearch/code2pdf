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
USE_CONDA=false

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
        --conda)
            USE_CONDA=true
            shift
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
            echo "  --conda      Get Python, WeasyPrint and Pango from conda-forge (no system packages needed)"
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
        if [[ -r /etc/os-release ]] && . /etc/os-release && [[ "${ID:-}" == "ubuntu" && "${VERSION_ID%%.*}" -ge 24 ]]; then
            print_info "On Ubuntu ${VERSION_ID}, the .deb package is simpler (dependencies come from apt):"
            echo "  curl -LO https://github.com/readbysearch/code2pdf/releases/latest/download/code2pdf_all.deb"
            echo "  sudo apt install ./code2pdf_all.deb"
        fi
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
    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required dependencies: ${missing[*]}"
        echo "Install them first:"
        echo "  Ubuntu/Debian: sudo apt install curl tar"
        echo "  macOS:         brew install readbysearch/tap/code2pdf  (installs everything)"
        exit 1
    fi

    # Python is not strictly required: without a usable one (or without Pango), the installer
    # falls back to conda-forge, which needs no system packages and no sudo.
    if command_exists "python3"; then
        local venv_note="venv ready"
        python3 -c "import ensurepip" 2>/dev/null || venv_note="no ensurepip (python3-venv); pip will be bootstrapped"
        print_info "Python: $(python3 -c 'import sys; print(sys.version.split()[0])') ($venv_note)"
    else
        print_info "Python: not found; Python will come from conda-forge"
    fi
    print_success "Dependencies checked"
}

# Download URL to FILE with curl or wget
download() {
    if command_exists "curl"; then
        curl -fsSL "$1" -o "$2"
    else
        wget -q "$1" -O "$2"
    fi
}

# Private environment from the system python3, without sudo even if python3-venv is missing
create_system_env() {
    local env="$1"
    command_exists "python3" || return 1
    if python3 -c "import ensurepip" 2>/dev/null; then
        $SUDO python3 -m venv "$env" || return 1
    else
        print_info "python3-venv is not installed; creating the environment without it and bootstrapping pip"
        $SUDO python3 -m venv --without-pip "$env" || return 1
        local get_pip
        get_pip="$(mktemp)"
        download "https://bootstrap.pypa.io/get-pip.py" "$get_pip" || { rm -f "$get_pip"; return 1; }
        $SUDO "$env/bin/python3" "$get_pip" --quiet --disable-pip-version-check || { rm -f "$get_pip"; return 1; }
        rm -f "$get_pip"
    fi
    $SUDO "$env/bin/python3" -m pip install --quiet --disable-pip-version-check -r "$SHARE_DIR/requirements.txt" || return 1
    "$env/bin/python3" -c "import weasyprint" 2>/dev/null
}

# Private environment from conda-forge (Python + WeasyPrint + Pango), via a downloaded micromamba
create_conda_env() {
    local env="$1" platform
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64) platform="linux-64" ;;
        Linux-aarch64|Linux-arm64) platform="linux-aarch64" ;;
        Linux-ppc64le) platform="linux-ppc64le" ;;
        Darwin-arm64) platform="osx-arm64" ;;
        Darwin-x86_64) platform="osx-64" ;;
        *) print_error "No conda-forge build for $(uname -s) $(uname -m)"; return 1 ;;
    esac
    local mamba_dir="$SHARE_DIR/.micromamba"
    print_info "Getting Python, WeasyPrint and Pango from conda-forge (no system packages needed; ~400 MB)..."
    $SUDO mkdir -p "$mamba_dir"
    download "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-$platform" "$mamba_dir/micromamba.tmp" \
        || { print_error "Could not download micromamba"; return 1; }
    $SUDO mv "$mamba_dir/micromamba.tmp" "$mamba_dir/micromamba"
    $SUDO chmod +x "$mamba_dir/micromamba"
    $SUDO rm -rf "$env"
    $SUDO env MAMBA_ROOT_PREFIX="$mamba_dir" "$mamba_dir/micromamba" create --yes --quiet --prefix "$env" \
        --override-channels -c conda-forge python pygments weasyprint pypdf >/dev/null || return 1
    # The environment is self-contained; drop the package cache and micromamba itself
    $SUDO rm -rf "$mamba_dir"
    "$env/bin/python3" -c "import weasyprint" 2>/dev/null
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
    $SUDO cp -R "$SRC/bin" "$SRC/scripts" "$SRC/config" "$SRC/fonts" "$SRC/requirements.txt" "$SHARE_DIR/"
    # VERSION is filled in by GitHub tarballs (export-subst); for a local checkout, ask git
    if [[ -f "$SRC/VERSION" ]] && ! grep -q '\$Format' "$SRC/VERSION"; then
        $SUDO cp "$SRC/VERSION" "$SHARE_DIR/VERSION"
    elif git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1; then
        echo "$(git -C "$SRC" describe --tags --dirty --always)|$(git -C "$SRC" rev-parse --short HEAD)|$(git -C "$SRC" log -1 --format=%cs)" \
            | $SUDO tee "$SHARE_DIR/VERSION" >/dev/null
    fi
    $SUDO chmod +x "$SHARE_DIR"/bin/* "$SHARE_DIR"/scripts/*.sh

    print_info "Creating Python environment with Pygments, WeasyPrint and pypdf..."
    local env="$SHARE_DIR/venv" env_ok=false
    if [[ "$USE_CONDA" != true ]]; then
        if create_system_env "$env" 2>"$SHARE_DIR/.install-errors.log"; then
            env_ok=true
        else
            if command_exists "python3"; then
                print_warning "The system Python can't run WeasyPrint here (most likely the Pango library is missing)."
            fi
            $SUDO rm -rf "$env"
        fi
    fi
    if [[ "$env_ok" != true ]]; then
        create_conda_env "$env" 2>>"$SHARE_DIR/.install-errors.log" && env_ok=true
    fi
    if [[ "$env_ok" == true ]]; then
        $SUDO rm -f "$SHARE_DIR/.install-errors.log"
    fi

    # The launchers find $SHARE_DIR by following these links
    for cmd in code2pdf code2txt; do
        $SUDO ln -sf "$SHARE_DIR/bin/$cmd" "$INSTALL_DIR/$cmd"
    done

    if [[ "$env_ok" != true ]]; then
        print_error "Could not set up a Python environment for code2pdf (details: $SHARE_DIR/.install-errors.log)."
        echo "code2txt works already. For code2pdf, either install the system packages"
        echo "  Ubuntu/Debian: sudo apt install python3-venv libpango-1.0-0 libpangoft2-1.0-0"
        echo "or check your network access to github.com and conda.anaconda.org, then re-run this installer."
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
