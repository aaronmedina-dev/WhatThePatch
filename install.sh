#!/bin/bash
#
# WhatThePatch Installer
# Usage: curl -sSL https://raw.githubusercontent.com/aaronmedina-dev/WhatThePatch/main/install.sh | bash
#

set -e

REPO="aaronmedina-dev/WhatThePatch"
BRANCH="${WTP_BRANCH:-main}"
TEMP_DIR=$(mktemp -d)

echo ""
echo "WhatThePatch Installer"
echo "======================"
echo ""

# Cleanup on exit
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo "Downloading from github.com/$REPO (branch: $BRANCH)..."

# Download and extract
curl -sSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar xz -C "$TEMP_DIR"

# Find extracted directory (name varies by branch)
EXTRACT_DIR=$(ls -d "$TEMP_DIR"/WhatThePatch-* 2>/dev/null | head -1)

if [ -z "$EXTRACT_DIR" ] || [ ! -d "$EXTRACT_DIR" ]; then
    echo "Error: Failed to download or extract files"
    exit 1
fi

echo "Running setup..."
echo ""

cd "$EXTRACT_DIR"
python3 setup.py

echo ""
echo "Installation complete!"
