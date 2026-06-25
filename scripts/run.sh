#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "Missing .venv. Run ./scripts/bootstrap-ubuntu-24.04.sh first on the Ubuntu bastion." >&2
  exit 1
fi

INV="inventories/pod22/hosts.yml"

ansible-playbook -i "$INV" playbooks/00_preflight.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/01_render_agent_iso.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/02_create_vsphere_vm.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/03_wait_install.yml --ask-vault-pass
