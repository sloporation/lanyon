#!/usr/bin/env bash
# Builds a single-file `lanyon` binary for the current OS/arch using PyInstaller.
# Run this separately on each target platform (Linux, macOS, Windows) -
# PyInstaller does not cross-compile.
set -euo pipefail

python3 -m venv .build-venv
source .build-venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --onefile --name lanyon src/lanyon_entry.py

deactivate
echo ""
echo "Binary built at dist/lanyon"
echo "Install with: sudo cp dist/lanyon /usr/bin/lanyon"
