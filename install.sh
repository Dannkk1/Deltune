#!/usr/bin/env bash
set -euo pipefail
if (( EUID == 0 )); then echo 'Run as your normal user: bash install.sh'; exit 1; fi
command -v pacman >/dev/null || { echo 'This installer is for CachyOS / Arch Linux.'; exit 1; }
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
echo 'Installing dependencies. Pacman will ask you to approve its package transaction.'
sudo pacman -S --needed pyside6 python-dbus-next python-evdev libratbag
sudo systemctl start ratbagd.service
install_dir="$HOME/.local/share/g502x-control"
mkdir -p "$install_dir" "$HOME/.local/share/applications"
install -m 644 "$source_dir/app.py" "$source_dir/backend.py" "$install_dir/"
# Quote the executable path according to the Desktop Entry specification.
python3 - "$install_dir" <<'PY'
import pathlib, sys
path = str(pathlib.Path(sys.argv[1]) / 'app.py')
quoted = '"' + path.replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%') + '"'
desktop = pathlib.Path.home()/'.local/share/applications/g502x-control.desktop'
desktop.write_text('[Desktop Entry]\nType=Application\nName=G502 X Control\nComment=Configure Logitech mouse DPI and buttons\nExec=/usr/bin/python3 '+quoted+'\nIcon=input-mouse\nTerminal=false\nCategories=Settings;HardwareSettings;\nStartupNotify=true\n')
PY
echo 'Installed! Open G502 X Control from your application menu.'
