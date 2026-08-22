#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "Largest top-level entries (including hidden directories):"
du -sh .[!.]* * 2>/dev/null | sort -h

echo
echo "Largest files under the repository:"
find . -type f -printf '%s\t%p\n' 2>/dev/null \
  | sort -nr \
  | head -20 \
  | awk '{printf "%.2f GiB\t%s\n", $1/1024/1024/1024, $2}'
