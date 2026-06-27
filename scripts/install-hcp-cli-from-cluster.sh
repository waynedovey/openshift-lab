#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <kubeconfig> <destination-hcp-path>" >&2
  exit 2
fi

KUBECONFIG_PATH="$1"
DEST="$2"
DEST_DIR="$(dirname "$DEST")"
mkdir -p "$DEST_DIR"

if [ -x "$DEST" ]; then
  "$DEST" version || true
  exit 0
fi

if command -v hcp >/dev/null 2>&1; then
  cp "$(command -v hcp)" "$DEST"
  chmod +x "$DEST"
  "$DEST" version || true
  exit 0
fi

JSON="$(oc --kubeconfig "$KUBECONFIG_PATH" get consoleclidownload hcp-cli-download -o json)"
URL="$(python3 -c '
import json, sys
obj=json.load(sys.stdin)
links=obj.get("spec",{}).get("links",[])
for link in links:
    text=(link.get("text") or "").lower()
    href=link.get("href") or ""
    blob=(text+" "+href).lower()
    if ("linux" in blob) and ("amd64" in blob or "x86_64" in blob or "x86-64" in blob):
        print(href); raise SystemExit
for link in links:
    blob=((link.get("text") or "")+" "+(link.get("href") or "")).lower()
    if "linux" in blob:
        print(link.get("href")); raise SystemExit
raise SystemExit("No Linux hcp CLI link found in ConsoleCLIDownload hcp-cli-download")
' <<<"$JSON")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -kL "$URL" -o "$TMP/hcp.tar.gz"
tar -xzf "$TMP/hcp.tar.gz" -C "$TMP"
FOUND="$(find "$TMP" -type f -name hcp | head -1)"
if [ -z "$FOUND" ]; then
  echo "hcp binary was not found in downloaded archive from $URL" >&2
  exit 1
fi
cp "$FOUND" "$DEST"
chmod +x "$DEST"
"$DEST" version || true
