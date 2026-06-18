#!/usr/bin/env bash
set -euo pipefail

ZIP_NAME="${1:-3796_3771_3672_ECE494.zip}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ "$ZIP_NAME" != *.zip ]]; then
  echo "error: output filename must end in .zip" >&2
  exit 1
fi

TOP_DIR="${ZIP_NAME%.zip}"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT

python3 - "$ROOT_DIR" "$STAGING_DIR" "$TOP_DIR" "$ZIP_NAME" <<'PY'
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
staging = Path(sys.argv[2]).resolve()
top_dir = sys.argv[3]
zip_name = sys.argv[4]

out_zip = root / zip_name
package_root = staging / top_dir
package_root.mkdir(parents=True, exist_ok=True)


def run_git(args, cwd=root, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_zlist(args, cwd=root):
    proc = run_git(args, cwd=cwd)
    return [Path(p.decode()) for p in proc.stdout.split(b"\0") if p]


def copy_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def is_initialized_submodule(path: Path) -> bool:
    if not path.is_dir():
        return False
    proc = run_git(["-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if proc.returncode != 0:
        return False
    try:
        return Path(proc.stdout.decode().strip()).resolve() == path.resolve()
    except OSError:
        return False

# Files that are not ignored by the superproject .gitignore.  This preserves
# the repository layout inside the archive instead of creating separate design/
# and reports/ folders.
root_files = git_zlist(["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
submodule_paths = [p for p in root_files if p.parts and p.parts[0].startswith("cv32e40p_")]
submodule_roots = set()

# Prefer .gitmodules so empty/untracked submodule paths are still checked.
mods = run_git(["config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"], check=False)
if mods.returncode == 0:
    for line in mods.stdout.decode().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            submodule_roots.add(Path(parts[1]))
for p in submodule_paths:
    submodule_roots.add(Path(p.parts[0]))

missing = sorted(str(p) for p in submodule_roots if not is_initialized_submodule(root / p))
if missing:
    print("error: these submodules are not initialized:", file=sys.stderr)
    for p in missing:
        print(f"  {p}", file=sys.stderr)
    print("run: git submodule update --init --recursive", file=sys.stderr)
    sys.exit(1)

for rel in root_files:
    if not rel.parts:
        continue
    if rel.parts[0].startswith("cv32e40p_"):
        # The superproject entry is only a gitlink; actual source files are
        # copied from each initialized submodule below.
        continue
    src = root / rel
    if src.is_file():
        copy_file(src, package_root / rel)

# Copy initialized CV32E40P submodules in-place, using each submodule's own
# ignore rules so local/generated files inside the checkout are omitted.
for sub in sorted(submodule_roots, key=str):
    sub_abs = root / sub
    files = git_zlist(["ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=sub_abs)
    for rel in files:
        src = sub_abs / rel
        if src.is_file():
            copy_file(src, package_root / sub / rel)

if out_zip.exists():
    out_zip.unlink()

with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(package_root.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(staging))

print(out_zip)
PY

echo "Created $ZIP_NAME"
