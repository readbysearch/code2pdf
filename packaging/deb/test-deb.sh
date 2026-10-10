#!/usr/bin/env bash
# Install a code2pdf .deb with apt in a clean system, use it as a normal user, then remove it.
# Run as root inside a fresh Ubuntu container, e.g.:
#   docker run --rm -v "$PWD/dist:/dist:ro" -v "$PWD/packaging:/packaging:ro" ubuntu:24.04 \
#       bash /packaging/deb/test-deb.sh /dist/code2pdf_3.6_all.deb

set -euo pipefail
DEB="$(realpath "${1:?usage: test-deb.sh PATH_TO_DEB}")"  # apt treats a bare relative path as a package name
export DEBIAN_FRONTEND=noninteractive

step() { echo "== $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

step "install with apt (resolves dependencies)"
apt-get update -qq
apt-get install -y -qq "$DEB" >/dev/null
dpkg -s code2pdf | grep -E '^(Version|Depends|Recommends):'

step "run as a normal user"
useradd -m tester
su tester -s /bin/bash -c '
    set -euo pipefail
    cd ~
    mkdir -p demo/src demo/build
    printf "#!/usr/bin/env bash\necho hi  # 你好\n" > demo/tool
    for i in $(seq 1 6); do printf "def f%d():\n    return %d\n" $i $i > demo/src/m$i.py; done
    printf "x = 1\n" > demo/build/generated.py
    printf "# Demo\n" > demo/README.md

    # capture first: with pipefail, `cmd | grep -q` fails when grep exits early (SIGPIPE)
    help=$(code2pdf --help); [[ "$help" == *"Usage: code2pdf"* ]]
    themes=$(code2pdf --list-themes); [[ "$themes" == paper$'"'"'\n'"'"'mono* ]]
    code2pdf -a demo --list-files > files.txt
    grep -q "src/m1.py" files.txt && ! grep -q build/ files.txt

    code2pdf -s demo/src/m1.py
    test -s m1.pdf

    code2pdf -a demo --theme mono
    test -s demo/merged.pdf

    CODE2PDF_PART_PAGES=1 code2pdf -a demo -j 2 2> parts.log
    grep -q "at a time" parts.log
    test -s demo/merged.pdf

    code2txt -o out.md demo >/dev/null
    grep -q "def f1" out.md
    echo "user checks passed"
'

step "fonts and files"
fc-list | grep -qi "noto.*cjk" || echo "note: fonts-noto-cjk not installed (Recommends)"
test -f /usr/share/code2pdf/fonts/IBMPlexMono-Regular.ttf

step "remove cleanly"
apt-get remove -y -qq code2pdf >/dev/null
test ! -e /usr/bin/code2pdf || fail "/usr/bin/code2pdf left behind"
test ! -e /usr/share/code2pdf || fail "/usr/share/code2pdf left behind"
echo "ALL CHECKS PASSED"
