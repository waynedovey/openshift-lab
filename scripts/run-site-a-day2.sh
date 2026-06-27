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

ansible-playbook -i "$INV" playbooks/02_add_sno_extra_disk.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/05_install_lvm_storage.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/04_configure_ad_dns.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/06_install_acm.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/07_configure_assisted_service.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/07_enable_baremetal_provisioning.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/07_validate_assisted_image_service.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/10_configure_bm_ad_dns.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/05_idrac_preflight.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/05_discover_idrac_nics.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/08_apply_baremetal_cluster.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/09_wait_baremetal_cluster.yml --ask-vault-pass
