#!/usr/bin/env bash
set -euo pipefail

INV="inventories/pod22/hosts.yml"

ansible-playbook -i "$INV" playbooks/00_preflight.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/04_configure_ad_dns.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/01_render_agent_iso.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/02_create_vsphere_vm.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/03_wait_install.yml --ask-vault-pass

ansible-playbook -i "$INV" playbooks/06_install_acm.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/07_configure_assisted_service.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/10_configure_bm_ad_dns.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/05_idrac_preflight.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/08_apply_baremetal_cluster.yml --ask-vault-pass
ansible-playbook -i "$INV" playbooks/09_wait_baremetal_cluster.yml --ask-vault-pass
