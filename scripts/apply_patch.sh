#!/usr/bin/env bash
set -euo pipefail

# Script to apply a patch to a Git repository
# Usage: ./apply_patch.sh <patch_file>

PATCH_FILE="$1"

if [[ ! -f "$PATCH_FILE" ]]; then
    echo "Error: Patch file not found: $PATCH_FILE"
    exit 1
fi

echo "Resetting repository to clean state..."
git checkout -f .

echo "Applying patch: $PATCH_FILE"
if git apply --index "$PATCH_FILE"; then
    echo "Patch applied successfully."
    exit 0
else
    echo "Error: Failed to apply patch"
    exit 1
fi
