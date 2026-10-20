# PyInstaller spec for code2pdf.exe: `python -m PyInstaller packaging/windows/code2pdf.spec`
# on Windows, with Pango's DLLs (MSYS2's ucrt64 pango) on PATH: WeasyPrint's PyInstaller hook
# bundles them. Makes dist/code2pdf/, a folder to zip.
import os

from PyInstaller.utils.hooks import collect_all

root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
datas = [(os.path.join(root, "fonts"), "fonts"), (os.path.join(root, "bin", "code2pdf"), "bin"),
         (os.path.join(root, "VERSION"), ".")]
# fc-list tells code2pdf whether a font has Chinese, Japanese or Korean characters (or they'd
# print as empty boxes): MSYS2's, with the same fontconfig DLL that WeasyPrint uses
binaries = [(r"C:\msys64\ucrt64\bin\fc-list.exe", ".")]
# The scripts import each other at run time, and parts mode's workers import parts
hiddenimports = ["dir_to_pdf", "code_to_pdf", "parts", "theme", "changes", "progress", "version"]
for package in ("pygments",):  # lexers and styles are found by name at run time
    d, b, h = collect_all(package)
    datas, binaries, hiddenimports = datas + d, binaries + b, hiddenimports + h

a = Analysis([os.path.join(SPECPATH, "code2pdf.py")], pathex=[os.path.join(root, "scripts")],
             datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
# UTF-8 mode: file names, git's output and the progress text are UTF-8 whatever Windows' code page
exe = EXE(pyz, a.scripts, [("X utf8", None, "OPTION")], exclude_binaries=True, name="code2pdf",
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="code2pdf")
