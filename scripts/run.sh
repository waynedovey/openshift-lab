#!/usr/bin/env bash
set -euo pipefail

INV="inventories/pod22/hosts.yml"

ansible-playbook -i "$INV" playbooks/00_preflight.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/01_render_agent_iso.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/02_create_vsphere_vm.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/03_wait_install.yml --ask-vault-pass
