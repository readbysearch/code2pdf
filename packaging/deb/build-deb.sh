#!/usr/bin/env bash
# Build code2pdf_<version>_all.deb using Ubuntu's own Python packages (Ubuntu 24.04+ / Debian 13+).
#
# Usage: packaging/deb/build-deb.sh VERSION [OUTPUT_DIR]
# Needs dpkg-deb (any Debian/Ubuntu system or container).

set -euo pipefail

VERSION="${1:?usage: build-deb.sh VERSION [OUTPUT_DIR]}"
VERSION="${VERSION#v}"
OUT_DIR="$(mkdir -p "${2:-dist}" && cd "${2:-dist}" && pwd)"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

SHARE="$STAGE/usr/share/code2pdf"
DOC="$STAGE/usr/share/doc/code2pdf"
mkdir -p "$SHARE" "$STAGE/usr/bin" "$DOC" "$STAGE/DEBIAN"

# Program files; the launchers find scripts/ and fonts/ next to their real location
cp -R "$SRC/bin" "$SRC/scripts" "$SRC/fonts" "$SHARE/"
find "$SHARE" -name '__pycache__' -prune -exec rm -rf {} +
find "$SHARE" -type d -exec chmod 755 {} +
find "$SHARE" -type f -exec chmod 644 {} +
# Executable: the launchers and anything with a #! line
for f in "$SHARE"/bin/* "$SHARE"/scripts/*; do
    if [ "$(head -c 2 "$f")" = "#!" ]; then chmod 755 "$f"; fi
done
for cmd in code2pdf code2txt; do
    ln -s "../share/code2pdf/bin/$cmd" "$STAGE/usr/bin/$cmd"
done

# For `code2pdf --version`: release from the argument, commit and date from git when available
COMMIT="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || true)"
COMMIT_DATE="$(git -C "$SRC" log -1 --format=%cs 2>/dev/null || true)"
echo "v${VERSION}|${COMMIT}|${COMMIT_DATE}" > "$SHARE/VERSION"
chmod 644 "$SHARE/VERSION"

# Documentation and manual pages
cp "$SRC/README.md" "$DOC/README.md"
mkdir -p "$STAGE/usr/share/man/man1"
for page in code2pdf code2txt; do
    gzip -9n -c "$SRC/packaging/deb/man/$page.1" > "$STAGE/usr/share/man/man1/$page.1.gz"
    chmod 644 "$STAGE/usr/share/man/man1/$page.1.gz"
done
cat > "$DOC/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: code2pdf
Source: https://github.com/readbysearch/code2pdf

Files: *
Copyright: readbysearch and contributors
License: AGPL-3.0-only
 This program is free software: you can redistribute it and/or modify it under the
 terms of the GNU Affero General Public License, version 3, as published by the Free
 Software Foundation. See https://www.gnu.org/licenses/agpl-3.0.html

Files: fonts/*
Copyright: 2017 IBM Corp. with Reserved Font Name "Plex"
License: OFL-1.1
 The IBM Plex fonts are licensed under the SIL Open Font License, Version 1.1;
 the full text is in /usr/share/code2pdf/fonts/LICENSE-IBM-Plex.txt
COPYRIGHT
printf 'code2pdf (%s) stable; urgency=medium\n\n  * Release %s, see https://github.com/readbysearch/code2pdf/releases\n\n -- readbysearch <readbysearch@users.noreply.github.com>  %s\n' \
    "$VERSION" "$VERSION" "$(LC_ALL=C date -u -R)" | gzip -9n > "$DOC/changelog.gz"

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: code2pdf
Version: $VERSION
Architecture: all
Maintainer: readbysearch <readbysearch@users.noreply.github.com>
Installed-Size: $(du -sk "$STAGE/usr" | cut -f1)
Depends: python3 (>= 3.10), weasyprint (>= 61), python3-pygments (>= 2.15)
Recommends: python3-pypdf (>= 4), fonts-noto-cjk, git
Section: text
Priority: optional
Homepage: https://github.com/readbysearch/code2pdf
Description: print source code to PDF with a contents page and CJK support
 code2pdf converts a single file or a whole directory of source code into one
 PDF: a contents page grouped by folder with clickable page numbers, then each
 file with syntax highlighting (500+ languages via Pygments), line numbers,
 dates from git, and bundled IBM Plex fonts. Themes: paper (colour, designed
 for print), mono (black and white) or any Pygments style. Files can be chosen
 with globs or an exact list, printed in part with their real line numbers, or
 taken from a git change (--changed REV) with the changed lines marked.
 .
 code2txt combines a directory into one Markdown text file for LLM context.
CONTROL

DEB="$OUT_DIR/code2pdf_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null
echo "$DEB"
