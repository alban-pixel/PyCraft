#!/usr/bin/env bash
# PyCraft Release Preparation Helper
# Usage: ./scripts/prepare_release.sh <version> [title]

set -e

VERSION="$1"
TITLE="$2"

if [ -z "$VERSION" ]; then
    echo "Usage: ./scripts/prepare_release.sh <version> [title]"
    echo "Example: ./scripts/prepare_release.sh 1.8.0 \"PyCraft 1.8.0 - The Bountiful Update\""
    exit 1
fi

if [ -z "$TITLE" ]; then
    TITLE="PyCraft v${VERSION}"
fi

python3 scripts/release.py --version "$VERSION" --title "$TITLE"
