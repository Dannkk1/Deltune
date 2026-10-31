# Publish this project on GitHub

Suggested repository name: **g502x-control**

Suggested description:
> Native Linux app for Logitech G502 X DPI, buttons, and onboard profiles. Built for CachyOS / Arch with Qt 6 and libratbag.

Suggested topics: `linux`, `cachyos`, `arch-linux`, `logitech`, `g502x`, `mouse`, `pyside6`, `libratbag`.

## First upload

1. Open https://github.com/new and create a public repository named `g502x-control`.
2. Leave "Add a README", license, and .gitignore unchecked: this project already includes them.
3. Extract the project ZIP and open a terminal inside the extracted `g502x-control` folder.
4. Run the commands below, replacing YOUR_USERNAME with your GitHub username:

```bash
git init -b main
git add .
git commit -m "Initial G502 X Control preview"
git remote add origin https://github.com/YOUR_USERNAME/g502x-control.git
git push -u origin main
```

Use your existing GitHub authentication. If Git asks you to configure your name
and email, use your preferred author name and GitHub-provided noreply email.
Do not put tokens in the repository or in command URLs.

The terminal method includes `.github`, `.gitignore`, and `.gitattributes`.
If you use GitHub's "uploading an existing file" page instead, upload the
**extracted contents**, not the ZIP or its containing folder, and include the
hidden files/directories. In KDE Dolphin, Ctrl+H shows hidden files. README.md,
app.py and install.sh should be at the repository root.

## Verify the first publication

- Open the Actions tab and wait for both Python test jobs to complete.
- Check that the README and screenshot render correctly.
- Install on CachyOS and test a DPI change and a non-primary button assignment.
- Reconnect the mouse and check whether its onboard settings persisted.
- Report the exact model, connection and libratbag version in the compatibility table.

## First release

After checking the app, create a release from GitHub's Releases page. Use tag
`v0.1.0` and title `G502 X Control 0.1.0 — Preview`. Mark it as a pre-release while
hardware validation remains incomplete. Use CHANGELOG.md as the release notes.
GitHub supplies downloadable source ZIP/tar archives automatically. Users can
extract them and run `bash install.sh`; no compiled binary is required.

This package does not create a remote repository or publish a release for you.
