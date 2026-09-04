#!/bin/zsh
set -euo pipefail

repo_dir="${0:A:h:h}"
cd "$repo_dir"

version=$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -1)
if [[ -z "$version" ]]; then
  print -u2 "无法从 pyproject.toml 读取版本号"
  exit 1
fi

bundle_name="macbook-live-meeting-notes-${version}-macos-arm64"
archive_path="$repo_dir/dist/${bundle_name}.zip"
staging_dir=$(mktemp -d)
trap 'rm -rf "$staging_dir"' EXIT
bundle_dir="$staging_dir/$bundle_name"

mkdir -p "$bundle_dir/docs" "$bundle_dir/src" "$bundle_dir/tests"

rsync -a \
  LICENSE MODEL_ATTRIBUTION.md QUICKSTART_ZH.md README.md \
  pyproject.toml uv.lock run.command \
  "$bundle_dir/"
rsync -a --exclude='.DS_Store' --exclude='__pycache__/' --exclude='*.py[cod]' \
  docs/ "$bundle_dir/docs/"
rsync -a --exclude='.DS_Store' --exclude='__pycache__/' --exclude='*.py[cod]' \
  src/ "$bundle_dir/src/"
rsync -a --exclude='.DS_Store' --exclude='__pycache__/' --exclude='*.py[cod]' \
  tests/ "$bundle_dir/tests/"

chmod +x "$bundle_dir/run.command"
mkdir -p "$repo_dir/dist"
rm -f "$archive_path"
(
  cd "$staging_dir"
  COPYFILE_DISABLE=1 /usr/bin/zip -X -q -r "$archive_path" "$bundle_name"
)

print "$archive_path"
shasum -a 256 "$archive_path"
