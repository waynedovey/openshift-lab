#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLD="$ROOT_DIR/inventories/pod22/group_vars/vault.yml"
NEW_DIR="$ROOT_DIR/inventories/pod22/group_vars/all"
NEW="$NEW_DIR/vault.yml"
EXAMPLE="$NEW_DIR/vault.yml.example"

mkdir -p "$NEW_DIR"

if [[ -f "$NEW" ]]; then
  echo "Vault already exists at the correct path: $NEW"
  exit 0
fi

if [[ -f "$OLD" ]]; then
  mv "$OLD" "$NEW"
  echo "Moved vault file to: $NEW"
  echo "Rerun your playbook with --ask-vault-pass."
  exit 0
fi

if [[ -f "$EXAMPLE" ]]; then
  cp "$EXAMPLE" "$NEW"
  echo "Created vault file from example: $NEW"
  echo "Now edit/encrypt it:"
  echo "  ansible-vault encrypt $NEW"
  echo "  ansible-vault edit $NEW"
  exit 0
fi

echo "Could not find old vault or example file. Expected one of:"
echo "  $OLD"
echo "  $EXAMPLE"
exit 1
