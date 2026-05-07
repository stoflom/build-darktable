#!/bin/bash

# ==============================================================================
# Script: build_darktable.sh
# Purpose: Build darktable with specific features.
# Dependencies: Requires darktable source and git.
# Usage: ./build_darktable.sh
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
DARKTABLE_DIR="${SCRIPT_DIR}/darktable"

# -----------------------------------------------------------------------------
# Check Dependencies
# -----------------------------------------------------------------------------
if [ ! -d "$DARKTABLE_DIR" ]; then
	echo "Error: darktable directory not found at $DARKTABLE_DIR"
	exit 1
fi

# -----------------------------------------------------------------------------
# Fetch and Update Source
# -----------------------------------------------------------------------------
cd "$DARKTABLE_DIR"

echo "Updating source code and submodules..."
if ! git pull --recurse-submodules; then
	echo "Error: Failed to pull from remote."
	exit 1
fi

# -----------------------------------------------------------------------------
# Clean Build Directory
# -----------------------------------------------------------------------------
if [ -d "${DARKTABLE_DIR}/build" ]; then
	echo "Cleaning old build directory: ${DARKTABLE_DIR}/build"
	rm -rf "${DARKTABLE_DIR}/build"
fi

# -----------------------------------------------------------------------------
# Build Options
# -----------------------------------------------------------------------------
BUILD_OPTIONS=(
	--prefix /opt/darktable
	--build-type Release
	--enable-ai
	--install
	--sudo
    --
    -DCMAKE_C_FLAGS="-Wno-error=nonnull -Wno-dev"
)

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
echo "Starting darktable build..."
if ! ./build.sh "${BUILD_OPTIONS[@]}"; then
	echo "Error: darktable build failed."
	exit 1
fi

echo "Build completed successfully."
