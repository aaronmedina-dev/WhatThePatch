#!/bin/bash
#
# WhatThePatch Uninstaller
# Usage: curl -sSL https://raw.githubusercontent.com/aaronmedina-dev/WhatThePatch/main/uninstall.sh | bash
#

set -e

INSTALL_DIR="$HOME/.whatthepatch"
CLI_WRAPPER="$HOME/.local/bin/wtp"

echo ""
echo "WhatThePatch Uninstaller"
echo "========================"
echo ""

# Check what exists
FOUND=0
if [ -d "$INSTALL_DIR" ]; then
    echo "Found: $INSTALL_DIR"
    FOUND=1
fi
if [ -f "$CLI_WRAPPER" ]; then
    echo "Found: $CLI_WRAPPER"
    FOUND=1
fi

if [ $FOUND -eq 0 ]; then
    echo "WhatThePatch is not installed."
    exit 0
fi

echo ""
read -p "Remove WhatThePatch? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Remove CLI wrapper
if [ -f "$CLI_WRAPPER" ]; then
    rm -f "$CLI_WRAPPER"
    echo "Removed: $CLI_WRAPPER"
fi

# Remove install directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed: $INSTALL_DIR"
fi

echo ""
echo "WhatThePatch has been uninstalled."
