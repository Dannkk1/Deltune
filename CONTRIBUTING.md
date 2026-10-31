# Contributing

Bug reports, device compatibility reports, and focused pull requests are welcome.
Please discuss new hardware backends before implementing them. This project uses
ratbagd API v2; it does not send undocumented raw HID writes.

## Development

Use Linux with Python 3.12 or later. On CachyOS/Arch, use the dependencies listed
in README.md. For an isolated development environment on another Linux distro:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

Building evdev may require a C compiler, Python development headers, and Linux
input headers. Qt also needs the system EGL/OpenGL/xkbcommon runtime libraries.
Tests use mock devices and don't change your mouse configuration.

Keep UI changes separate from hardware operations. Preserve the last-left-click
guard, capability validation, write-failure monitoring, and readback checks.
Add meaningful tests for changes affecting device writes. Never report a device
as tested when only a fixture was used. Keep diagnostic reports free of private
information. Submit contributions under the project's MIT license.
