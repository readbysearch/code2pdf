#!/usr/bin/env python3
"""
Convert source code to PDF with syntax highlighting and UTF-8 support.
Uses Pygments for syntax highlighting and WeasyPrint for PDF generation.
"""

import sys
import os
from pathlib import Path
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


def generate_html(file_path, file_content, relative_path=None):
    """Generate HTML with syntax highlighting for the given file."""

    # Try to get appropriate lexer based on filename
    try:
        lexer = get_lexer_for_filename(file_path)
    except:
        # Fallback to plain text if language can't be detected
        lexer = TextLexer()

    # Generate syntax-highlighted HTML
    formatter = HtmlFormatter(
        style='default',
        full=False,
        linenos='inline',
        cssclass='highlight'
    )

    highlighted_code = highlight(file_content, lexer, formatter)

    # Get CSS for syntax highlighting
    css = formatter.get_style_defs('.highlight')

    # Use relative path for display if provided, otherwise use full path
    display_path = relative_path if relative_path else file_path

    # Generate complete HTML document with UTF-8 support
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{os.path.basename(file_path)}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @top-center {{
                content: "{display_path}";
                font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
                font-size: 10pt;
                color: #666;
            }}
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
                font-size: 10pt;
                color: #666;
            }}
        }}

        body {{
            font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono", "DejaVu Sans Mono", "Courier New", monospace;
            font-size: 9pt;
            line-height: 1.4;
            margin: 0;
            padding: 0;
        }}

        .highlight {{
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            padding: 10px;
            overflow-x: auto;
        }}

        .highlight pre {{
            margin: 0;
            font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono", "DejaVu Sans Mono", "Courier New", monospace;
            font-size: 9pt;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        /* Pygments syntax highlighting */
        {css}

        /* Line numbers styling */
        .highlight .linenos {{
            color: #999;
            background-color: #eee;
            padding-right: 10px;
            border-right: 1px solid #ccc;
            margin-right: 10px;
            user-select: none;
        }}
    </style>
</head>
<body>
    {highlighted_code}
</body>
</html>
"""
    return html


def convert_to_pdf(file_path, output_pdf, relative_path=None):
    """Convert a source code file to PDF with syntax highlighting."""

    # Read the file with UTF-8 encoding
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()

    # Generate HTML
    html_content = generate_html(file_path, content, relative_path)

    # Configure fonts for CJK support
    font_config = FontConfiguration()

    # Convert HTML to PDF
    HTML(string=html_content).write_pdf(
        output_pdf,
        font_config=font_config
    )

    return output_pdf


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: code_to_pdf.py <input_file> <output_pdf> [relative_path]")
        print("  input_file: Path to the source code file")
        print("  output_pdf: Path for the output PDF file")
        print("  relative_path: Optional display path for the header (e.g., 'src/main.py')")
        sys.exit(1)

    input_file = sys.argv[1]
    output_pdf = sys.argv[2]
    relative_path = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_pdf) or '.', exist_ok=True)

    try:
        convert_to_pdf(input_file, output_pdf, relative_path)
        print(f"PDF created at {output_pdf}")
    except Exception as e:
        print(f"Error creating PDF: {e}")
        sys.exit(1)
