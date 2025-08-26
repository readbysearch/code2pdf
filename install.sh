#!/usr/bin/env bash

# code2pdf and code2txt Installation Script
# Installs code2pdf and code2txt tools on Linux systems

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="waleking/code2pdf"
INSTALL_DIR_SYSTEM="/usr/local/bin"
INSTALL_DIR_USER="$HOME/.local/bin"

# Command line options
USER_INSTALL=false
SYSTEM_INSTALL=false
FORCE=false

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
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --user     Install for current user only (~/.local/bin)"
            echo "  --system   Install system-wide (/usr/local/bin, requires sudo)"
            echo "  --force    Skip confirmations"
            echo "  -h, --help Show this help message"
            echo ""
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Print colored output
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

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

# Detect OS and architecture
detect_system() {
    print_info "Detecting system information..."
    
    # OS Detection
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        print_warning "This script is optimized for Linux. For macOS, consider using Homebrew."
        if [[ "$FORCE" != true ]]; then
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
        fi
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Architecture Detection
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) ARCH="x86_64" ;;
        aarch64) ARCH="arm64" ;;
        arm64) ARCH="arm64" ;;
        *) print_warning "Unsupported architecture: $ARCH. Continuing anyway..." ;;
    esac
    
    print_success "Detected: $OS ($ARCH)"
}

# Check and install dependencies
check_dependencies() {
    print_info "Checking dependencies..."
    
    local missing_deps=()
    local optional_deps=()
    
    # Check required tools
    if ! command_exists "curl" && ! command_exists "wget"; then
        missing_deps+=("curl or wget")
    fi
    
    # Check for extraction tools (unzip or tar)
    if ! command_exists "unzip" && ! command_exists "tar"; then
        missing_deps+=("unzip or tar")
    fi
    
    # Check code2pdf dependencies (optional)
    if ! command_exists "vim"; then
        optional_deps+=("vim")
    fi
    
    if ! command_exists "gs"; then
        optional_deps+=("ghostscript")
    fi
    
    if ! command_exists "jq"; then
        optional_deps+=("jq")
    fi
    
    # Handle missing required dependencies
    if [[ ${#missing_deps[@]} -ne 0 ]]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        print_info "Please install them first:"
        echo "  Ubuntu/Debian: sudo apt update && sudo apt install curl unzip (or tar is fine too)"
        echo "  CentOS/RHEL:   sudo yum install curl unzip (or tar is fine too)"
        echo "  Fedora:        sudo dnf install curl unzip (or tar is fine too)"
        exit 1
    fi
    
    # Handle optional dependencies
    if [[ ${#optional_deps[@]} -ne 0 ]]; then
        print_warning "Optional dependencies for code2pdf: ${optional_deps[*]}"
        echo ""
        echo "To install them:"
        echo "  Ubuntu/Debian: sudo apt install vim ghostscript jq"
        echo "  CentOS/RHEL:   sudo yum install vim ghostscript jq"
        echo "  Fedora:        sudo dnf install vim ghostscript jq"
        echo ""
        echo "code2txt will work without these. code2pdf requires vim and ghostscript."
        echo ""
        if [[ "$FORCE" != true ]]; then
            read -p "Continue installation? (y/n): " -n 1 -r
            echo
            [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
        else
            print_info "Continuing with --force flag"
        fi
    else
        print_success "All dependencies are available!"
    fi
}

# Determine install directory and check permissions
determine_install_dir() {
    print_info "Determining installation directory..."
    
    # Handle command line options first
    if [[ "$SYSTEM_INSTALL" == true ]]; then
        INSTALL_DIR="$INSTALL_DIR_SYSTEM"
        USE_SUDO=true
        print_info "Installing system-wide (--system flag): $INSTALL_DIR"
        return
    elif [[ "$USER_INSTALL" == true ]]; then
        INSTALL_DIR="$INSTALL_DIR_USER"
        USE_SUDO=false
        print_info "Installing for current user (--user flag): $INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
        return
    fi
    
    # Check if we can write to system directory
    if [[ -w "$INSTALL_DIR_SYSTEM" ]] || [[ $EUID -eq 0 ]]; then
        INSTALL_DIR="$INSTALL_DIR_SYSTEM"
        print_info "Installing to system directory: $INSTALL_DIR"
    else
        # Check if user wants to install system-wide
        print_info "System directory requires sudo access."
        echo "Options:"
        echo "  1) Install system-wide (requires sudo) - available for all users"
        echo "  2) Install for current user only - no sudo required"
        echo ""
        read -p "Choose option (1 or 2): " -n 1 -r
        echo
        
        if [[ $REPLY == "1" ]]; then
            INSTALL_DIR="$INSTALL_DIR_SYSTEM"
            USE_SUDO=true
            print_info "Will install system-wide using sudo"
        else
            INSTALL_DIR="$INSTALL_DIR_USER"
            USE_SUDO=false
            print_info "Installing for current user: $INSTALL_DIR"
            # Create user bin directory if it doesn't exist
            mkdir -p "$INSTALL_DIR"
        fi
    fi
}

# Download and install files
install_tools() {
    print_info "Downloading and installing tools..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT
    
    # Download method
    local download_cmd
    if command_exists "curl"; then
        download_cmd="curl -L -o"
    elif command_exists "wget"; then
        download_cmd="wget -O"
    else
        print_error "Neither curl nor wget is available"
        exit 1
    fi
    
    # Download the repository (try tar.gz first, then zip)
    print_info "Downloading from GitHub..."
    cd "$TEMP_DIR"
    
    # Try tar.gz first (works without unzip)
    if command_exists "tar"; then
        print_info "Using tar.gz archive..."
        if command_exists "curl"; then
            curl -L "https://github.com/$GITHUB_REPO/archive/main.tar.gz" -o code2pdf.tar.gz
        else
            wget "https://github.com/$GITHUB_REPO/archive/main.tar.gz" -O code2pdf.tar.gz
        fi
        
        # Extract with tar
        print_info "Extracting files with tar..."
        tar -xzf code2pdf.tar.gz
        cd "code2pdf-main"
    elif command_exists "unzip"; then
        print_info "Using zip archive..."
        if command_exists "curl"; then
            curl -L "https://github.com/$GITHUB_REPO/archive/main.zip" -o code2pdf.zip
        else
            wget "https://github.com/$GITHUB_REPO/archive/main.zip" -O code2pdf.zip
        fi
        
        # Extract with unzip
        print_info "Extracting files with unzip..."
        unzip -q code2pdf.zip
        cd "code2pdf-main"
    else
        print_error "Neither tar nor unzip is available for extraction"
        exit 1
    fi
    
    # Install binary files
    print_info "Installing tools..."
    
    local install_cmd=""
    if [[ "$USE_SUDO" == true ]]; then
        install_cmd="sudo"
    fi
    
    # Install main scripts
    $install_cmd cp bin/code2pdf bin/code2txt "$INSTALL_DIR/"
    $install_cmd chmod +x "$INSTALL_DIR/code2pdf" "$INSTALL_DIR/code2txt"
    
    # Create scripts directory and install processing scripts
    local scripts_install_dir
    if [[ "$USE_SUDO" == true ]]; then
        scripts_install_dir="/usr/local/share/code2pdf"
        sudo mkdir -p "$scripts_install_dir"
        sudo cp -r scripts config "$scripts_install_dir/"
        sudo chmod +x "$scripts_install_dir"/scripts/*.sh
        
        # Update the main scripts to use the correct scripts directory
        sudo sed -i "s|INSTALL_DIR=\".*\"|INSTALL_DIR=\"$scripts_install_dir\"|g" "$INSTALL_DIR/code2pdf"
    else
        scripts_install_dir="$HOME/.local/share/code2pdf"
        mkdir -p "$scripts_install_dir"
        cp -r scripts config "$scripts_install_dir/"
        chmod +x "$scripts_install_dir"/scripts/*.sh
        
        # Update the main scripts to use the correct scripts directory
        sed -i "s|INSTALL_DIR=\".*\"|INSTALL_DIR=\"$scripts_install_dir\"|g" "$INSTALL_DIR/code2pdf"
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
            # Check if our PATH export is already there
            if ! grep -q "/.local/bin.*code2pdf" "$config_file" 2>/dev/null; then
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

# Verify installation
verify_installation() {
    print_info "Verifying installation..."
    
    # Test if commands are accessible
    export PATH="$PATH:$INSTALL_DIR"
    
    if command_exists "code2txt"; then
        print_success "code2txt is installed and accessible"
        code2txt --help >/dev/null 2>&1 && print_success "code2txt runs correctly"
    else
        print_error "code2txt is not accessible in PATH"
        return 1
    fi
    
    if command_exists "code2pdf"; then
        print_success "code2pdf is installed and accessible"
        code2pdf --help >/dev/null 2>&1 && print_success "code2pdf runs correctly"
    else
        print_error "code2pdf is not accessible in PATH"
        return 1
    fi
}

# Display usage information
show_usage() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                          Installation Complete!                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    print_success "Tools are now installed and ready to use!"
    echo ""
    echo "Usage examples:"
    echo "  code2txt                           # Process current directory"
    echo "  code2txt --include-types js,py     # Only include specific file types"
    echo "  code2pdf -a /path/to/project       # Convert project to PDF"
    echo "  code2pdf -s single_file.py         # Convert single file to PDF"
    echo ""
    echo "For help:"
    echo "  code2txt --help"
    echo "  code2pdf --help"
    echo ""
    
    if [[ "$INSTALL_DIR" != "$INSTALL_DIR_SYSTEM" ]]; then
        print_info "If commands are not found, restart your shell or run:"
        echo "  source ~/.bashrc"
    fi
    
    echo ""
    print_info "GitHub: https://github.com/$GITHUB_REPO"
}

# Main installation flow
main() {
    print_header
    
    # Check if running as root with warning
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

# Run main function
main "$@"