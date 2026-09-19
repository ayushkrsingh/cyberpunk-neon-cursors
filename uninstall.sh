#!/usr/bin/env bash
# Remove the Cyberpunk-Neon cursor theme.
set -euo pipefail
THEME="Cyberpunk-Neon"

rm -rf "$HOME/.icons/$THEME" "$HOME/.local/share/icons/$THEME"
[ "$(id -u)" -eq 0 ] && rm -rf "/usr/share/icons/$THEME"

if command -v gsettings >/dev/null 2>&1; then
  current=$(gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null || echo "")
  if [ "$current" = "'$THEME'" ]; then
    gsettings set org.gnome.desktop.interface cursor-theme "Adwaita"
    echo "reverted cursor-theme to Adwaita"
  fi
fi
echo "removed $THEME"
