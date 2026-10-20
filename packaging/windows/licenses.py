"""
Puts the licenses of what the Windows build bundles into DIST/licenses (python licenses.py DIST,
after PyInstaller): each MSYS2 package that a bundled DLL comes from, each Python package, and
Python itself. Run in the Python and MSYS2 that built it.
"""

import importlib.metadata
import os
import shutil
import subprocess
import sys

DIST = os.path.abspath(sys.argv[1])
OUT = os.path.join(DIST, "licenses")
MSYS2 = r"C:\msys64"
# Used to build, not bundled
BUILD_ONLY = {"pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile", "pywin32-ctypes", "packaging",
              "setuptools", "pip", "pytest", "iniconfig", "pluggy", "colorama"}

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
listed = []

# DLLs and programs from MSYS2: the package that owns each, and that package's license files
binaries = sorted({name for _, _, names in os.walk(DIST) for name in names
                   if name.lower().endswith((".dll", ".exe")) and name.lower() != "code2pdf.exe"})
packages = {}
for name in binaries:
    source = os.path.join(MSYS2, "ucrt64", "bin", name)
    if not os.path.isfile(source):
        continue  # from Python's own installation: covered by Python's license
    owner = subprocess.run([os.path.join(MSYS2, "usr", "bin", "pacman.exe"), "-Qqo", source],
                           capture_output=True, text=True).stdout.strip()
    if owner:
        packages.setdefault(owner, []).append(name)
for package, names in sorted(packages.items()):
    base = package.replace("mingw-w64-ucrt-x86_64-", "")
    found = os.path.join(MSYS2, "ucrt64", "share", "licenses", base)
    if os.path.isdir(found):
        shutil.copytree(found, os.path.join(OUT, base))
    else:
        print(f"Warning: no license files for {package} ({', '.join(names)})", file=sys.stderr)
    listed.append(f"{base}: {', '.join(names)}")

# Python packages
for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    if name.lower() in BUILD_ONLY:
        continue
    folder = os.path.join(OUT, "python", name)
    os.makedirs(folder, exist_ok=True)
    copied = 0
    for file in dist.files or []:
        base = os.path.basename(str(file)).upper()
        if base.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")):
            shutil.copy(dist.locate_file(file), os.path.join(folder, os.path.basename(str(file))))
            copied += 1
    license_text = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
    if not copied:
        with open(os.path.join(folder, "LICENSE"), "w", encoding="utf-8") as f:
            f.write(license_text or "See the project's page on pypi.org.\n")
    listed.append(f"python/{name} {dist.version}: {license_text.splitlines()[0] if license_text else 'see folder'}")

# code2pdf's own
shutil.copy(os.path.join(os.path.dirname(__file__), "..", "..", "LICENSE"), os.path.join(DIST, "LICENSE"))

# Python itself (its LICENSE.txt covers the libraries it bundles, such as libffi and OpenSSL)
shutil.copy(os.path.join(sys.base_prefix, "LICENSE.txt"), os.path.join(OUT, "python", "Python-LICENSE.txt"))
listed.append(f"python/Python-LICENSE.txt: Python {sys.version.split()[0]}")

with open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8") as f:
    f.write("code2pdf for Windows bundles the software below; each folder holds its license.\n"
            "code2pdf's own license is LICENSE, and the IBM Plex fonts' is in _internal/fonts.\n\n"
            + "\n".join(listed) + "\n")
print("\n".join(listed))
