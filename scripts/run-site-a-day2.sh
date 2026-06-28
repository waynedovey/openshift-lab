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
HUB_KUBECONFIG="$PWD/build/hub-sno/install/auth/kubeconfig"

# Ask for the Ansible Vault password once, then reuse it for every playbook.
# If ANSIBLE_VAULT_PASSWORD_FILE is already set, use that instead and do not prompt.
if [[ -n "${ANSIBLE_VAULT_PASSWORD_FILE:-}" ]]; then
  VAULT_ARGS=(--vault-password-file "$ANSIBLE_VAULT_PASSWORD_FILE")
else
  VAULT_PASSWORD_FILE_TMP="$(mktemp)"
  chmod 600 "$VAULT_PASSWORD_FILE_TMP"
  trap 'rm -f "$VAULT_PASSWORD_FILE_TMP"' EXIT

  read -r -s -p "Vault password: " VAULT_PASSWORD
  echo
  printf '%s\n' "$VAULT_PASSWORD" > "$VAULT_PASSWORD_FILE_TMP"
  unset VAULT_PASSWORD

  VAULT_ARGS=(--vault-password-file "$VAULT_PASSWORD_FILE_TMP")
fi

run_playbook() {
  local playbook="$1"
  ansible-playbook -i "$INV" "${VAULT_ARGS[@]}" "$playbook"
}

hub_is_up() {
  [[ -f "$HUB_KUBECONFIG" ]] || return 1
  timeout 15 oc --kubeconfig "$HUB_KUBECONFIG" get clusterversion version >/dev/null 2>&1 || return 1
  timeout 15 oc --kubeconfig "$HUB_KUBECONFIG" get nodes >/dev/null 2>&1 || return 1
}

if ! hub_is_up; then
  echo "Hub SNO is not reachable yet. Run ./scripts/run.sh first, then rerun this script." >&2
  exit 1
fi

# Hub day-2. These playbooks are idempotent and can safely be rerun.
run_playbook playbooks/02_add_sno_extra_disk.yml
run_playbook playbooks/05_install_lvm_storage.yml
run_playbook playbooks/04_configure_ad_dns.yml
run_playbook playbooks/06_install_acm.yml
run_playbook playbooks/07_configure_assisted_service.yml
run_playbook playbooks/07_enable_baremetal_provisioning.yml
run_playbook playbooks/07_validate_assisted_image_service.yml

# Site-A provisioning.
run_playbook playbooks/10_configure_bm_ad_dns.yml
run_playbook playbooks/05_idrac_preflight.yml
run_playbook playbooks/05_discover_idrac_nics.yml
run_playbook playbooks/08_apply_baremetal_cluster.yml
run_playbook playbooks/09_wait_baremetal_cluster.yml
