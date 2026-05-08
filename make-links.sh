#!/bin/bash
# Automatically create darktable symbolic links
# Scans /opt/darktable subdirectories and creates symlinks in system paths

set -euo pipefail

DT=/opt/darktable
BIN_DST=/usr/local/bin
MAN_DST=/usr/local/share/man
APP_DST=/usr/local/share/applications
PIXMAP_DST=/usr/share/pixmaps

make_links() {
    local links_made=0 links_failed=0

    make_link() {
        local src="$1" dst="$2"
        if [ ! -e "$src" ]; then
            echo "SKIP: source not found: $src"
            return
        fi
        mkdir -p "$(dirname "$dst")"
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            echo "OK:   $dst -> $src"
            return
        fi
        if [ -e "$dst" ] || [ -L "$dst" ]; then
            echo "SKIP: $dst exists, not overwriting"
            links_failed=$((links_failed + 1))
            return
        fi
        ln -s "$src" "$dst"
        echo "LINK: $dst -> $src"
        links_made=$((links_made + 1))
    }

    # .desktop files
    while IFS= read -r -d '' f; do
        make_link "$f" "$APP_DST/$(basename "$f")"
    done < <(find "$DT/share/applications" -maxdepth 1 -name '*.desktop' -print0 2>/dev/null || true)

    # main icon → /usr/share/pixmaps
    while IFS= read -r -d '' f; do
        make_link "$f" "$PIXMAP_DST/$(basename "$f")"
    done < <(find "$DT/share/icons/hicolor/scalable/apps" -name 'darktable.svg' -print0 2>/dev/null || true)

    # binaries
    while IFS= read -r -d '' f; do
        make_link "$f" "$BIN_DST/$(basename "$f")"
    done < <(find "$DT/bin" -maxdepth 1 -executable -type f -print0 2>/dev/null || true)

    # man pages — preserve locale structure
    while IFS= read -r -d '' f; do
        rel="${f#$DT/share/man/}"
        make_link "$f" "$MAN_DST/$rel"
    done < <(find "$DT/share/man" -type f -name '*.gz' -o -name '*.1' -print0 2>/dev/null || true)

    echo "---"
    echo "Done: $links_made links created, $links_failed skipped (already existed)"
}

if [ "$(id -u)" -ne 0 ]; then
    exec sudo "$0" "$@"
fi

make_links
