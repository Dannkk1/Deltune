#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir/packaging/arch"
cp "$project_dir/app.py" "$project_dir/backend.py" "$project_dir/LICENSE" .
makepkg --cleanbuild --force "$@"
mkdir -p "$project_dir/dist"
cp ./*.pkg.tar.zst "$project_dir/dist/"
cd "$project_dir/dist"
sha256sum ./*.pkg.tar.zst > SHA256SUMS
