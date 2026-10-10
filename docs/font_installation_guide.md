# CJK Fonts for code2pdf

Latin text uses the IBM Plex fonts bundled with code2pdf. Plex has no Chinese, Japanese or
Korean glyphs, so those characters come from fonts installed on the system. **Without a CJK font
they print as empty boxes** (the text inside the PDF is still correct, so copy-paste works).
code2pdf checks this and warns before and after converting, and `code2pdf --version` shows the
CJK font it will use.

## macOS

Nothing to install: PingFang, Hiragino and Apple SD Gothic/Nanum are used automatically.

## Linux

Pick one:

```bash
# With sudo (Debian/Ubuntu; the code2pdf .deb recommends it)
sudo apt install fonts-noto-cjk

# Without sudo: Noto Sans Mono CJK (~26 MB) into ~/.local/share/fonts
~/.local/share/code2pdf/scripts/setup_cjk_fonts.sh        # or scripts/setup_cjk_fonts.sh in a checkout
~/.local/share/code2pdf/scripts/setup_cjk_fonts.sh tc     # sc (default), tc, hk, jp or kr glyph forms
```

`install.sh --user` runs `setup_cjk_fonts.sh` by itself when no CJK font is found (skip with
`--no-cjk-fonts`). Every Noto CJK font covers Chinese, Japanese and Korean; the language only
picks the regional glyph forms. The script needs curl or wget, and python3, unzip or bsdtar.

## Check

```bash
code2pdf --version                       # last line: "CJK font: Noto Sans Mono CJK SC"
fc-list ":charset=4e2d" family           # fonts that contain 中
```

Test rendering:

```bash
cat > /tmp/test_chinese.py << 'EOF'
# 测试中文注释
def hello():
    print("你好，世界！")  # Hello World
EOF
code2pdf -s /tmp/test_chinese.py         # writes test_chinese.pdf in the current directory
```

## How code2pdf picks fonts

Set in `scripts/theme.py`:

- **Code**: bundled IBM Plex Mono, then `CJK_MONO_FALLBACK`: Noto Sans Mono CJK SC/TC/JP/KR/HK
  (monospace, so CJK keeps to the code columns), then `CJK_FALLBACK`.
- **Titles, contents page, page headers**: bundled IBM Plex Sans, then `CJK_FALLBACK`:
  PingFang SC, Hiragino Sans, Noto Sans CJK SC/JP/KR.

To use another installed font (e.g. WenQuanYi Micro Hei), add its family name to
`CJK_FALLBACK` in `scripts/theme.py`.

## Troubleshooting

**Characters appear as boxes (□□□)**

```bash
fc-list ":charset=4e2d" family           # empty means no font has the characters
fc-cache -f ~/.local/share/fonts          # rebuild the cache after copying fonts by hand
ls -l ~/.local/share/fonts/noto-cjk/      # .otf files must be readable
```

Then convert again. If `fc-list` is missing, install fontconfig or check with `code2pdf --version`.

**Some characters render, others don't**: the installed font may not cover them (rare
characters, emoji). Install `fonts-noto-cjk` (full coverage) or `fonts-noto-color-emoji`.

## Uninstall

```bash
rm -rf ~/.local/share/fonts/noto-cjk && fc-cache -f
```

## License

Noto Sans CJK is licensed under the SIL Open Font License 1.1
(<https://github.com/notofonts/noto-cjk>); `setup_cjk_fonts.sh` copies its LICENSE next to the fonts.
