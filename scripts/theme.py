#!/usr/bin/env python3
"""
Themes, bundled fonts and page CSS for code2pdf.

  paper  (default) colour theme designed for print; every token class also differs in
         lightness, weight or slant, so it stays readable when printed in greyscale
  mono   pure black and white for laser printers
  <name> any Pygments style (see `theme.py --list`); code uses its colours, the page stays white

Run `theme.py --list` to print every theme name.
"""

import sys
from pathlib import Path

from pygments.style import Style
from pygments.styles import get_all_styles, get_style_by_name
from pygments.token import (Comment, Error, Generic, Keyword, Literal, Name, Number, Operator,
                            Punctuation, String, Text)
from pygments.util import ClassNotFound


FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

# (CSS family, file, weight, style)
FONT_FACES = [
    ("c2p Code", "IBMPlexMono-Regular.ttf", 400, "normal"),
    ("c2p Code", "IBMPlexMono-Italic.ttf", 400, "italic"),
    ("c2p Code", "IBMPlexMono-Medium.ttf", 500, "normal"),
    ("c2p Code", "IBMPlexMono-SemiBold.ttf", 700, "normal"),
    ("c2p Text", "IBMPlexSans-Regular.ttf", 400, "normal"),
    ("c2p Text", "IBMPlexSans-SemiBold.ttf", 600, "normal"),
]

# Plex has no CJK glyphs; fall back to the system's CJK fonts (monospace ones first for code,
# so CJK text keeps to the code columns when e.g. setup_cjk_fonts.sh installed Noto Sans Mono CJK)
CJK_FALLBACK = '"PingFang SC", "Hiragino Sans", "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK KR", sans-serif'
CJK_MONO_FALLBACK = ('"Noto Sans Mono CJK SC", "Noto Sans Mono CJK TC", "Noto Sans Mono CJK JP", '
                     '"Noto Sans Mono CJK KR", "Noto Sans Mono CJK HK", ' + CJK_FALLBACK)


class Palette:
    def __init__(self, ink, graphite, faint):
        self.ink = ink            # body text
        self.graphite = graphite  # secondary text: folders, details, headers
        self.faint = faint        # line numbers and dot leaders only (not for reading text)


PAPER = Palette(ink="#1c2541", graphite="#6b6f76", faint="#a3a7ad")
MONO = Palette(ink="#000000", graphite="#555555", faint="#8c8c8c")

MULBERRY, FERN, OCHRE, COBALT = "#7a1f4b", "#2e6b3a", "#8a5a00", "#1f4fa3"


class PaperStyle(Style):
    name = "paper"
    background_color = "#ffffff"
    styles = {
        Text: PAPER.ink, Punctuation: PAPER.ink, Operator: PAPER.ink, Name: PAPER.ink,
        Comment: f"italic {PAPER.graphite}", Comment.Preproc: f"italic {PAPER.graphite}",
        Comment.Hashbang: f"italic {PAPER.graphite}",
        Keyword: f"bold {MULBERRY}", Keyword.Type: MULBERRY, Keyword.Constant: f"bold {MULBERRY}",
        Operator.Word: f"bold {MULBERRY}",
        String: FERN, String.Doc: FERN, String.Escape: OCHRE, String.Interpol: OCHRE,
        Number: OCHRE, Literal: OCHRE,
        Name.Function: COBALT, Name.Class: f"bold {COBALT}", Name.Decorator: COBALT,
        Name.Builtin: COBALT, Name.Variable: PAPER.ink, Name.Tag: MULBERRY, Name.Attribute: COBALT,
        Generic.Heading: f"bold {PAPER.ink}", Generic.Subheading: f"bold {PAPER.ink}",
        Generic.Emph: "italic", Generic.Strong: "bold", Generic.Inserted: FERN, Generic.Deleted: MULBERRY,
        Error: MULBERRY,
    }


class MonoStyle(Style):
    name = "mono"
    background_color = "#ffffff"
    styles = {
        Text: MONO.ink, Name: MONO.ink, String: MONO.ink, Number: MONO.ink,
        Comment: f"italic {MONO.graphite}", Comment.Hashbang: f"italic {MONO.graphite}",
        Keyword: f"bold {MONO.ink}", Operator.Word: f"bold {MONO.ink}",
        Name.Class: f"bold {MONO.ink}", Name.Tag: f"bold {MONO.ink}",
        Generic.Heading: f"bold {MONO.ink}", Generic.Subheading: f"bold {MONO.ink}",
        Generic.Emph: "italic", Generic.Strong: "bold",
    }


class Theme:
    def __init__(self, name, style, palette, code_background=None, line_number_color=None):
        self.name = name
        self.style = style
        self.palette = palette
        self.code_background = code_background      # None: code sits directly on the white page
        self.line_number_color = line_number_color or palette.faint
        # Marked lines: a bar in the gutter and a light tint (prints as light grey in black and white)
        if palette is MONO:
            self.mark, self.mark_tint = "#000000", "#ececec"
        elif code_background:
            self.mark, self.mark_tint = "#e0a030", "rgba(224, 160, 48, 0.18)"
        else:
            self.mark, self.mark_tint = OCHRE, "#f8f0de"


BUILTIN = {"paper": (PaperStyle, PAPER), "mono": (MonoStyle, MONO)}


def list_themes():
    return list(BUILTIN) + sorted(set(get_all_styles()) - set(BUILTIN))


def _is_light(hex_color):
    value = (hex_color or "#ffffff").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return True
    return (0.299 * r + 0.587 * g + 0.114 * b) > 235


def resolve_theme(name):
    name = (name or "paper").strip().lower()
    if name in BUILTIN:
        style, palette = BUILTIN[name]
        return Theme(name, style, palette)
    try:
        style = get_style_by_name(name)
    except ClassNotFound:
        raise ValueError(f"unknown theme '{name}'") from None
    background = None if _is_light(style.background_color) else style.background_color
    return Theme(name, style, PAPER, code_background=background,
                 line_number_color=getattr(style, "line_number_color", None) if background else None)


def font_files():
    return [str(FONTS_DIR / filename) for _, filename, _, _ in FONT_FACES]


def drop_apple_cid_tables(document, pdf):
    """WeasyPrint finisher (`write_pdf(finisher=...)`): remove 'cidg' tables from embedded fonts.

    Apple's CJK fonts (PingFang, Hiragino) have an Apple-only 'cidg' table mapping character IDs
    to glyphs of the whole font. WeasyPrint keeps it in the subsets it embeds, and Preview follows
    it, so most CJK text printed empty or as other characters (poppler ignores it)."""
    import io
    import pydyf
    from fontTools.ttLib import TTFont
    for obj in pdf.objects:
        if not (isinstance(obj, pydyf.Stream) and len(obj.stream) == 1 and isinstance(obj.stream[0], bytes)
                and b"cidg" in _sfnt_tags(obj.stream[0])):
            continue
        font = TTFont(io.BytesIO(obj.stream[0]), recalcBBoxes=False, recalcTimestamp=False)
        del font["cidg"]
        kept = io.BytesIO()
        font.save(kept)
        obj.stream[0] = kept.getvalue()
        if "Length1" in obj.extra:
            obj.extra["Length1"] = len(obj.stream[0])


def _sfnt_tags(data):
    """Table tags of an OpenType/TrueType font file, or nothing for other data."""
    if data[:4] not in (b"OTTO", b"\0\1\0\0", b"true") or len(data) < 12:
        return set()
    count = int.from_bytes(data[4:6], "big")
    return {data[12 + 16 * i:16 + 16 * i] for i in range(count) if 16 + 16 * i <= len(data)}


def css_string(value):
    """Quote a value for use inside a CSS string."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def font_face_css():
    return "".join(
        f'@font-face {{ font-family: "{family}"; src: url("{(FONTS_DIR / filename).as_uri()}"); '
        f"font-weight: {weight}; font-style: {style}; }}\n"
        for family, filename, weight, style in FONT_FACES)


PAGE_SIZE = "size: A4; margin: 20mm 17mm 18mm 17mm;"


def chrome_css(theme, header_right):
    """Page header (file path, project and date) and footer (page / pages)."""
    p = theme.palette
    return f"""
@page {{
    {PAGE_SIZE}
    @top-left {{ content: string(path); font: 7.5pt "c2p Text", {CJK_FALLBACK}; color: {p.graphite}; }}
    @top-right {{ content: {css_string(header_right)}; font: 7.5pt "c2p Text", {CJK_FALLBACK}; color: {p.graphite}; }}
    @bottom-right {{ content: counter(page) " / " counter(pages); font: 7.5pt "c2p Text", {CJK_FALLBACK}; color: {p.graphite}; }}
}}
@page :first {{ @top-left {{ content: none; }} @top-right {{ content: none; }} }}
"""


def overlay_css(theme, header_right):
    """Headers and footers only, one empty <div class="page" data-path=...> per page; stamped onto
    documents rendered in parts (see parts.py)."""
    return chrome_css(theme, header_right) + """
div.page { string-set: path attr(data-path); break-after: page; height: 1px; }
div.page:last-child { break-after: auto; }
"""


def page_css(theme, header_right, chrome=True):
    p = theme.palette
    code_block = (f".highlight {{ background: {theme.code_background}; padding: 3mm 3mm 3mm 1mm; }}"
                  if theme.code_background else ".highlight, .highlight pre { background: none; }")
    pages = chrome_css(theme, header_right) if chrome else f"@page {{ {PAGE_SIZE} }}\n"
    return pages + f"""
body {{ margin: 0; color: {p.ink}; font: 8.5pt/1.45 "c2p Code", {CJK_MONO_FALLBACK}; }}

/* Contents */
nav.toc {{ font-family: "c2p Text", {CJK_FALLBACK}; }}
nav.toc h1 {{ font-size: 22pt; font-weight: 600; margin: 8mm 0 1mm; letter-spacing: -0.01em; bookmark-level: none; }}
nav.toc .lede, section.file .lede {{ color: {p.ink}; font-size: 11pt; line-height: 1.4; max-width: 150mm;
    margin: 0 0 2.5mm; }}
nav.toc .summary {{ color: {p.graphite}; font-size: 9pt; margin: 0 0 0.8mm; }}
nav.toc .summary:last-of-type {{ margin-bottom: 9mm; }}
nav.toc h2 {{ font-size: 8.5pt; font-weight: 600; color: {p.graphite}; margin: 5mm 0 1.5mm; bookmark-level: none; }}
nav.toc ol {{ list-style: none; margin: 0; padding: 0; }}
nav.toc li {{ font-size: 9.5pt; line-height: 1.75; padding-left: 4mm; }}
nav.toc a {{ color: {p.ink}; text-decoration: none; }}
nav.toc a::after {{ content: leader(" . ") target-counter(attr(href), page); color: {p.faint}; }}
nav.toc a[data-page]::after {{ content: leader(" . ") attr(data-page); }}

/* File title: the one prominent element */
section.file {{ break-before: page; }}
section.file:first-child {{ break-before: auto; }}
section.file header {{ margin: 0 0 6mm; font-family: "c2p Text", {CJK_FALLBACK}; }}
section.file .dir {{ color: {p.graphite}; font-size: 9pt; }}
section.file h1 {{ string-set: path attr(data-path); font-size: 17pt; font-weight: 600; margin: 0.5mm 0 1mm;
                   letter-spacing: -0.01em; bookmark-label: attr(data-path); }}
section.file .meta {{ color: {p.graphite}; font-size: 8pt; }}

/* Code: line numbers in the margin; wrapped lines hang under the code */
.highlight pre {{ margin: 0; font: inherit; white-space: pre-wrap; overflow-wrap: anywhere; counter-reset: line; }}
/* 15mm = 9mm gutter + 6mm (2em at 8.5pt) hang; plain lengths because WeasyPrint < 62 ignores calc() here */
.highlight pre > span[id] {{ display: block; position: relative; padding-left: 15mm; text-indent: -6mm;
                             counter-increment: line; }}
/* The number's right edge is 6mm in. Its box reaches 11mm into the page margin, so numbers of
   five digits or more (7.4mm at 7pt) grow to the left instead of wrapping onto the next line */
.highlight pre > span[id]::before {{ content: counter(line); position: absolute; left: -11mm; width: 17mm;
    text-indent: 0; text-align: right; white-space: nowrap; color: {theme.line_number_color}; font-size: 7pt;
    line-height: 1.75; font-style: normal; font-weight: 400; }}
/* Part of a file: lines left out are marked; numbering restarts at each range (counter-reset inline) */
.highlight pre > span.gap {{ display: block; padding-left: 9mm; margin: 1.2mm 0; color: {theme.line_number_color};
                             font: italic 7.5pt "c2p Text", {CJK_FALLBACK}; }}
/* Marked lines (--changed, path:+START-END): a bar in the gutter between number and code */
.highlight pre > span.marked {{ background: {theme.mark_tint}; }}
.highlight pre > span.marked::after {{ content: ""; position: absolute; left: 7mm; top: 0; bottom: 0; width: 0.9mm;
                                       background: {theme.mark}; }}
.highlight pre > span.removed {{ display: block; position: relative; padding-left: 9mm; color: {theme.mark};
                                 font: italic 6.5pt "c2p Text", {CJK_FALLBACK}; line-height: 1.6; }}
.highlight pre > span.removed::after {{ content: ""; position: absolute; left: 6.5mm; top: 50%; width: 1.9mm;
                                        border-top: 0.9pt solid {theme.mark}; }}
{code_block}
"""


if __name__ == "__main__":
    if sys.argv[1:] == ["--list"]:
        print("\n".join(list_themes()))
    else:
        print(__doc__.strip())
