#!/usr/bin/env python3
"""
Convert one source file to PDF with syntax highlighting and UTF-8/CJK support.
Uses the same design as directory mode (see dir_to_pdf.py), without a table of contents.

Usage: code_to_pdf.py <input_file> <output_pdf> [relative_path] [--theme NAME]
"""

import os
import sys

from pygments.lexers import TextLexer, get_lexer_for_filename, guess_lexer
from pygments.util import ClassNotFound


def lexer_for(file_path, source=None):
    """Pygments lexer by file name; for unknown names, by a `#!` line; else plain text."""
    try:
        return get_lexer_for_filename(file_path)
    except ClassNotFound:
        pass
    if source and source.startswith("#!"):
        try:
            return guess_lexer(source)
        except ClassNotFound:
            pass
    return TextLexer()


def read_source(file_path):
    """Read a source file as UTF-8, falling back to latin-1."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def main(argv):
    args = list(argv)
    theme = os.environ.get("CODE2PDF_THEME", "paper")
    if "--theme" in args:
        i = args.index("--theme")
        if i + 1 >= len(args):
            print("Error: --theme needs a name", file=sys.stderr)
            return 1
        theme = args[i + 1]
        del args[i:i + 2]

    if len(args) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    input_file, output_pdf = args[0], args[1]
    relative_path = args[2] if len(args) > 2 else os.path.basename(input_file)

    import dir_to_pdf
    ranges = ()
    if not os.path.isfile(input_file):  # FILE:START-END prints part of the file
        base, wanted = dir_to_pdf.split_ranges(input_file)
        if wanted and os.path.isfile(base):
            try:
                ranges, note = dir_to_pdf.resolve_ranges(wanted, dir_to_pdf.file_lines(base))
            except ValueError as e:
                print(f"Error: {input_file}: {e}", file=sys.stderr)
                return 1
            if note:
                print(f"Note: {input_file}: {note}", file=sys.stderr)
            input_file, relative_path = base, dir_to_pdf.split_ranges(relative_path)[0]
    if not os.path.isfile(input_file):
        print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)

    try:
        dir_to_pdf.render_document([dir_to_pdf.Entry(relative_path, os.path.abspath(input_file), ranges)], output_pdf,
                                   theme_name=theme, project=None, contents=False)
    except ValueError as e:
        hint = "; run `code2pdf --list-themes` to see the names" if "theme" in str(e) else ""
        print(f"Error: {e}{hint}", file=sys.stderr)
        return 1
    print(f"PDF created at {output_pdf}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dir_to_pdf
    sys.exit(dir_to_pdf.run_main(main, sys.argv[1:]))
