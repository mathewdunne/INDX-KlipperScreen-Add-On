#!/usr/bin/env bash
# INDX KlipperScreen add-on installer
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Links the panel, add-on, icon, menu conf and companion cfg into place,
# includes the menu conf from KlipperScreen.conf and sets enable_addons.
# Never touches printer.cfg or moonraker.conf. install.sh -u reverses it.

set -euo pipefail

addon_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
printer_config=$HOME/printer_data/config
klipperscreen_dir=$HOME/KlipperScreen
uninstall=false

marker="# added by INDX add-on install.sh"
include_line="[include indx_menu.conf]"
companion_include="[include indx_companion.cfg]"
exclude_paths=("panels/indx.py" "addons/indx.py" "styles/*/images/indx.svg")

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*"; }
die() {
  echo "[ERROR] $*"
  exit 1
}

show_help() {
  echo "Usage: $0 [-p <printer_config>] [-k <klipperscreen_dir>] [-u] [-h]"
  echo "  -p  printer config directory (default: \$HOME/printer_data/config)"
  echo "  -k  KlipperScreen directory (default: \$HOME/KlipperScreen)"
  echo "  -u  uninstall"
  echo "  -h  show this help"
}

checks() {
  [ "$EUID" -ne 0 ] || die "Do not run this as root."
  [ -f "$klipperscreen_dir/screen.py" ] || die "KlipperScreen not found at $klipperscreen_dir (use -k)."
  [ -d "$printer_config" ] || die "Printer config directory not found at $printer_config (use -p)."
  # The add-on hook arrived in KlipperScreen PR #1770 (commit 8abe645c, 2026-09-13)
  grep -q "_load_addons" "$klipperscreen_dir/screen.py" ||
    die "This KlipperScreen has no add-on support. Update it: git -C $klipperscreen_dir pull"
}

# link <target in this repo> <link path>: never replaces a real file
link() {
  if [ -e "$2" ] && [ ! -L "$2" ]; then
    warn "$2 exists and is not a symlink, leaving it alone."
    return
  fi
  ln -sfn "$1" "$2"
  info "Linked $2"
}

# unlink <link path>: only removes links that point into this repo
unlink_ours() {
  if [ -L "$1" ] && [[ "$(readlink "$1")" == "$addon_dir"/* ]]; then
    rm -f "$1"
    info "Removed $1"
  fi
}

theme_image_dirs() {
  local dir
  for dir in "$klipperscreen_dir"/styles/*/images; do
    [ -d "$dir" ] && echo "$dir"
  done
}

conf_file() { echo "$printer_config/KlipperScreen.conf"; }

# Is the companion cfg included from an uncommented line of the printer config?
companion_included() {
  grep -Eqs '^[[:space:]]*\[include indx_companion\.cfg\]' "$printer_config"/*.cfg
}

# Insert lines, each after a "$marker" line, before the auto-generated block
# (or at the end)
insert_before_saved() {
  local file block="" line
  file=$(conf_file)
  for line in "$@"; do
    block+="$marker"$'\n'"$line"$'\n'
  done
  BLOCK="$block" awk '
    !done && /^#~# --- Do not edit below this line/ { printf "%s", ENVIRON["BLOCK"]; done = 1 }
    { print }
    END { if (!done) printf "%s", ENVIRON["BLOCK"] }
  ' "$file" >"$file.indx.tmp"
  cat "$file.indx.tmp" >"$file" && rm -f "$file.indx.tmp"
}

# Lines above the auto-generated block, which is where users write
user_part() {
  awk '/^#~# --- Do not edit below this line/ { exit } { print }' "$(conf_file)"
}

configure_klipperscreen() {
  local file
  file=$(conf_file)
  [ -f "$file" ] || {
    touch "$file"
    info "Created $file"
  }

  if grep -Fxq "$include_line" "$file"; then
    info "$include_line already present."
  else
    insert_before_saved "$include_line"
    info "Added $include_line to $file"
  fi

  if user_part | grep -Eq '^[[:space:]]*enable_addons[[:space:]]*[:=][[:space:]]*[Tt]rue'; then
    info "enable_addons already set."
  elif user_part | grep -Eq '^[[:space:]]*enable_addons'; then
    warn "enable_addons is set to something other than True in $file. Set it to True yourself."
  elif user_part | grep -Eq '^\[main\]'; then
    awk -v marker="$marker" '
      !done && /^\[main\]/ { print; print marker; print "enable_addons: True"; done = 1; next }
      { print }
    ' "$file" >"$file.indx.tmp"
    cat "$file.indx.tmp" >"$file" && rm -f "$file.indx.tmp"
    info "Set enable_addons: True in [main]."
  else
    insert_before_saved "[main]" "enable_addons: True"
    info "Added [main] with enable_addons: True."
  fi

  if grep -Eq '^#~# enable_addons = False' "$file"; then
    warn "Add-ons were switched off in KlipperScreen's settings menu, which overrides the file."
    warn "Turn 'Enable Add-ons' back on there after restarting KlipperScreen."
  fi
}

unconfigure_klipperscreen() {
  local file
  file=$(conf_file)
  [ -f "$file" ] || return 0
  # Drop each marker line and the line after it
  awk -v marker="$marker" '
    skip { skip = 0; next }
    $0 == marker { skip = 1; next }
    { print }
  ' "$file" >"$file.indx.tmp"
  cat "$file.indx.tmp" >"$file" && rm -f "$file.indx.tmp"
  info "Removed the add-on's lines from $file"
}

git_exclude() {
  local exclude="$klipperscreen_dir/.git/info/exclude" path
  [ -d "$klipperscreen_dir/.git" ] || return 0
  mkdir -p "$(dirname "$exclude")"
  touch "$exclude"
  for path in "${exclude_paths[@]}"; do
    grep -Fxq "$path" "$exclude" || echo "$path" >>"$exclude"
  done
  info "Excluded the add-on's files from KlipperScreen's git status."
}

git_unexclude() {
  local exclude="$klipperscreen_dir/.git/info/exclude" path
  [ -f "$exclude" ] || return 0
  for path in "${exclude_paths[@]}"; do
    grep -Fxv "$path" "$exclude" >"$exclude.indx.tmp" || true
    mv "$exclude.indx.tmp" "$exclude"
  done
}

install() {
  checks
  local dir
  link "$addon_dir/panels/indx.py" "$klipperscreen_dir/panels/indx.py"
  mkdir -p "$klipperscreen_dir/addons"
  link "$addon_dir/addons/indx.py" "$klipperscreen_dir/addons/indx.py"
  while read -r dir; do
    link "$addon_dir/icons/indx.svg" "$dir/indx.svg"
  done < <(theme_image_dirs)
  link "$addon_dir/klipperscreen/indx_menu.conf" "$printer_config/indx_menu.conf"
  link "$addon_dir/klipper/indx_companion.cfg" "$printer_config/indx_companion.cfg"
  configure_klipperscreen
  git_exclude

  echo
  info "Installed. Two steps left:"
  if companion_included; then
    info "  1. $companion_include is already in your config."
  else
    info "  1. Add this line to printer.cfg, after the INDX includes, then RESTART Klipper:"
    info "       $companion_include"
  fi
  info "  2. Restart KlipperScreen: sudo systemctl restart KlipperScreen"
}

uninstall() {
  [ "$EUID" -ne 0 ] || die "Do not run this as root."
  # Klipper would refuse to start with an include that points nowhere
  if companion_included; then
    die "Remove $companion_include from your printer config and RESTART Klipper first."
  fi
  local dir
  unlink_ours "$klipperscreen_dir/panels/indx.py"
  unlink_ours "$klipperscreen_dir/addons/indx.py"
  rmdir "$klipperscreen_dir/addons" 2>/dev/null || true
  while read -r dir; do
    unlink_ours "$dir/indx.svg"
  done < <(theme_image_dirs)
  unconfigure_klipperscreen
  unlink_ours "$printer_config/indx_menu.conf"
  unlink_ours "$printer_config/indx_companion.cfg"
  git_unexclude
  info "Uninstalled. enable_addons was removed only if this installer added it."
  info "Restart KlipperScreen: sudo systemctl restart KlipperScreen"
}

while getopts "p:k:uh" arg; do
  case $arg in
  p) printer_config=$OPTARG ;;
  k) klipperscreen_dir=$OPTARG ;;
  u) uninstall=true ;;
  h)
    show_help
    exit 0
    ;;
  *)
    show_help
    exit 1
    ;;
  esac
done

if $uninstall; then
  uninstall
else
  install
fi
