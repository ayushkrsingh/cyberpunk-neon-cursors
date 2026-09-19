#!/usr/bin/env bash
# Install the Cyberpunk-Neon cursor theme for the current user.
#   ./install.sh            install to ~/.icons
#   sudo ./install.sh -s    install system-wide to /usr/share/icons
set -euo pipefail

THEME="Cyberpunk-Neon"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$THEME"
DEST="$HOME/.icons"
SYSTEM=0

while getopts "sh" o; do
  case "$o" in
    s) SYSTEM=1; DEST="/usr/share/icons" ;;
    h) sed -n '2,5p' "$0"; exit 0 ;;
    *) exit 1 ;;
  esac
done

if [ ! -d "$SRC/cursors" ]; then
  echo "error: $SRC/cursors not found." >&2
  echo "Run 'python3 src/generate.py' first, or use the release archive." >&2
  exit 1
fi

if [ "$SYSTEM" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "error: -s needs root. Try: sudo ./install.sh -s" >&2
  exit 1
fi

mkdir -p "$DEST"
rm -rf "${DEST:?}/$THEME"
cp -r "$SRC" "$DEST/$THEME"
echo "installed -> $DEST/$THEME"

# GTK4 and some Wayland apps also look here
if [ "$SYSTEM" -eq 0 ]; then
  mkdir -p "$HOME/.local/share/icons"
  ln -sfn "$DEST/$THEME" "$HOME/.local/share/icons/$THEME"
fi

if [ "$SYSTEM" -eq 0 ] && command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.interface cursor-theme "$THEME"
  gsettings set org.gnome.desktop.interface cursor-size 28
  echo "applied: cursor-theme=$THEME cursor-size=28"
else
  echo "now select '$THEME' in GNOME Tweaks > Appearance > Cursor"
fi

echo "note: apps that cache cursors (some Electron apps, open terminals) need a restart."
