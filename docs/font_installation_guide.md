# CJK Font Installation Guide for code2pdf

## Overview

This guide documents how to install CJK (Chinese/Japanese/Korean) fonts required for proper Unicode character rendering in code2pdf. Without these fonts, Chinese/Japanese/Korean characters will appear as boxes or fail to render.

## Why Are CJK Fonts Needed?

code2pdf uses WeasyPrint for PDF generation, which requires fonts that contain the necessary glyphs for Chinese, Japanese, and Korean characters. The default system fonts (DejaVu) only support Latin characters.

## Quick Installation (Recommended)

### For Simplified Chinese (简体中文)

```bash
# 1. Download Noto Sans CJK fonts
cd /tmp
wget https://github.com/googlefonts/noto-cjk/releases/download/Sans2.004/01_NotoSansCJK-OTF-VF.zip

# 2. Extract the package
python3 -m zipfile -e 01_NotoSansCJK-OTF-VF.zip .

# 3. Create font directory
mkdir -p ~/.local/share/fonts/noto-cjk

# 4. Install Simplified Chinese fonts
cp Variable/OTF/Subset/NotoSansSC-VF.otf ~/.local/share/fonts/noto-cjk/
cp Variable/OTF/Mono/NotoSansMonoCJKsc-VF.otf ~/.local/share/fonts/noto-cjk/

# 5. Update font cache
fc-cache -f ~/.local/share/fonts/noto-cjk/

# 6. Verify installation
fc-list | grep -i "noto.*cjk"
```

**Disk space required**: ~30 MB

### For Traditional Chinese (繁體中文)

Replace step 4 with:
```bash
cp Variable/OTF/Subset/NotoSansTC-VF.otf ~/.local/share/fonts/noto-cjk/
cp Variable/OTF/Mono/NotoSansMonoCJKtc-VF.otf ~/.local/share/fonts/noto-cjk/
```

### For Japanese (日本語)

Replace step 4 with:
```bash
cp Variable/OTF/Subset/NotoSansJP-VF.otf ~/.local/share/fonts/noto-cjk/
cp Variable/OTF/Mono/NotoSansMonoCJKjp-VF.otf ~/.local/share/fonts/noto-cjk/
```

### For Korean (한국어)

Replace step 4 with:
```bash
cp Variable/OTF/Subset/NotoSansKR-VF.otf ~/.local/share/fonts/noto-cjk/
cp Variable/OTF/Mono/NotoSansMonoCJKkr-VF.otf ~/.local/share/fonts/noto-cjk/
```

## Install All CJK Fonts (For Multi-Language Support)

If you work with multiple CJK languages:

```bash
cd /tmp
wget https://github.com/googlefonts/noto-cjk/releases/download/Sans2.004/01_NotoSansCJK-OTF-VF.zip
python3 -m zipfile -e 01_NotoSansCJK-OTF-VF.zip .
mkdir -p ~/.local/share/fonts/noto-cjk

# Install all regional variants
cp Variable/OTF/Subset/*.otf ~/.local/share/fonts/noto-cjk/
cp Variable/OTF/Mono/*.otf ~/.local/share/fonts/noto-cjk/

# Update font cache
fc-cache -f ~/.local/share/fonts/noto-cjk/
```

**Disk space required**: ~150 MB

## Verification

### Check Font Installation

```bash
# List all installed Noto CJK fonts
fc-list | grep -i "noto.*cjk"

# Expected output should include:
# - Noto Sans SC (Simplified Chinese)
# - Noto Sans Mono CJK SC (Monospace)
```

### Test Chinese Character Rendering

Create a test file:
```bash
cat > /tmp/test_chinese.py << 'EOF'
# 测试中文注释
def 你好():
    print("世界！")
EOF
```

Convert to PDF:
```bash
code2pdf -s /tmp/test_chinese.py
```

Open the generated PDF and verify:
- ✅ Chinese characters are clearly visible
- ✅ Characters are not boxes/squares
- ✅ Syntax highlighting is applied

## Font Sources

### Noto Sans CJK

- **Developer**: Google
- **License**: SIL Open Font License 1.1 (free for commercial use)
- **Download**: https://github.com/googlefonts/noto-cjk/releases
- **Version Used**: Sans 2.004
- **Coverage**: Complete CJK Unified Ideographs

### Font Variants

| Font Name | Purpose | File Size | Coverage |
|-----------|---------|-----------|----------|
| NotoSansSC-VF.otf | Simplified Chinese UI/text | 15 MB | GB18030 |
| NotoSansTC-VF.otf | Traditional Chinese UI/text | 15 MB | Big5 |
| NotoSansJP-VF.otf | Japanese UI/text | 15 MB | JIS X 0208 |
| NotoSansKR-VF.otf | Korean UI/text | 15 MB | KS X 1001 |
| NotoSansMonoCJKsc-VF.otf | Chinese monospace (code) | 15 MB | GB18030 |
| NotoSansMonoCJKtc-VF.otf | Traditional Chinese monospace | 15 MB | Big5 |
| NotoSansMonoCJKjp-VF.otf | Japanese monospace | 15 MB | JIS X 0208 |
| NotoSansMonoCJKkr-VF.otf | Korean monospace | 15 MB | KS X 1001 |

## How code2pdf Uses These Fonts

The Python script `scripts/code_to_pdf.py` specifies font families in this order:

1. **For code blocks** (monospace):
   ```css
   font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono",
                "DejaVu Sans Mono", "Courier New", monospace;
   ```

2. **For headers/footers** (sans-serif):
   ```css
   font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
   ```

**Fallback behavior**: If CJK fonts are not installed, WeasyPrint will fall back to DejaVu Sans Mono, which **cannot** render CJK characters (will show boxes).

## Troubleshooting

### Issue: Chinese characters appear as boxes (□□□)

**Cause**: CJK fonts are not installed or not found by WeasyPrint.

**Solution**:
```bash
# 1. Verify fonts are installed
ls ~/.local/share/fonts/noto-cjk/

# 2. Rebuild font cache
fc-cache -f ~/.local/share/fonts/

# 3. Test font detection
fc-list | grep -i "noto.*cjk"

# 4. If no output, reinstall fonts (see Quick Installation above)
```

### Issue: "Font not found" warnings from WeasyPrint

**Cause**: Font cache is outdated or fonts are in wrong location.

**Solution**:
```bash
# Update font cache with verbose output
fc-cache -fv ~/.local/share/fonts/noto-cjk/

# Verify font directory permissions
ls -la ~/.local/share/fonts/noto-cjk/
# All .otf files should be readable (r-- permissions)
```

### Issue: Some characters render, others don't

**Cause**: Missing specific regional font variant.

**Solution**: Install all CJK variants (see "Install All CJK Fonts" section above).

### Issue: PDF generation is slow with CJK fonts

**Expected behavior**: First PDF generation with CJK text may take 2-3 seconds as WeasyPrint loads fonts. Subsequent conversions are cached and faster.

**Optimization**: This is normal. CJK fonts are large (~15 MB each) and take time to load.

## Alternative Fonts (If Noto Fonts Don't Work)

### WenQuanYi (文泉驿)

Free Chinese fonts:
```bash
# Debian/Ubuntu systems (if you have sudo)
sudo apt-get install fonts-wqy-microhei fonts-wqy-zenhei

# Manual installation
mkdir -p ~/.local/share/fonts/wqy
cd ~/.local/share/fonts/wqy
wget https://downloads.sourceforge.net/wqy/wqy-microhei-0.2.0-beta.tar.gz
tar -xzf wqy-microhei-0.2.0-beta.tar.gz
cp wqy-microhei/*.ttc .
fc-cache -f ~/.local/share/fonts/wqy/
```

Then update `scripts/code_to_pdf.py` to use "WenQuanYi Micro Hei" instead of "Noto Sans CJK SC".

### Source Han Sans (思源黑体)

Adobe's open-source CJK font (same as Noto CJK, different name):
```bash
# Download from Adobe
wget https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansSC.zip
```

## Uninstallation

To remove CJK fonts:
```bash
rm -rf ~/.local/share/fonts/noto-cjk/
fc-cache -f
```

**Note**: code2pdf will still work for non-CJK text after removing fonts.

## Additional Resources

- [Noto CJK GitHub Repository](https://github.com/googlefonts/noto-cjk)
- [Google Fonts: Noto Sans](https://fonts.google.com/noto)
- [WeasyPrint Font Documentation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#fonts)
- [Fontconfig User Guide](https://www.freedesktop.org/software/fontconfig/fontconfig-user.html)

## License

Noto Sans CJK fonts are licensed under the **SIL Open Font License 1.1**:
- ✅ Free for personal and commercial use
- ✅ Can be bundled with software
- ✅ Can be modified
- ❌ Cannot be sold by itself

Full license: https://scripts.sil.org/OFL

---

**Last Updated**: October 23, 2025
**Font Version**: Noto Sans CJK 2.004
**Tested With**: code2pdf (Python/WeasyPrint implementation)
