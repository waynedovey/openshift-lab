# OpenShift Hub, Spokes and Hosted Control Planes Lab

An Ansible-based lab for deploying and managing an OpenShift environment with:

- OpenShift **4.21.25**
- A vSphere **Single Node OpenShift (SNO)** management hub
- Red Hat Advanced Cluster Management (**RHACM 2.16**)
- Multicluster Engine (**MCE 2.11**)
- Two physical OpenShift spoke clusters: **Site-A** and **Site-B**
- Hosted Control Plane (HCP) tenant clusters on the spokes
- Everpure and Portworx integration

Run commands from the repository root unless stated otherwise.

## Architecture

```text
Ubuntu 24.04 Bastion
        |
        v
vSphere SNO Hub
RHACM + MCE
   /        \
  v          v
Site-A     Site-B
OpenShift  OpenShift
  |           |
Portworx    Portworx
  |           |
HCPs        HCPs
```

The SNO hub is the central management cluster. Site-A and Site-B are the physical HCP hosting clusters. HCP tenant control planes and KubeVirt workers run on the spoke clusters, not on the SNO hub.

## Repository Layout

```text
inventories/env/group_vars/all/main.yml   Non-secret environment configuration
inventories/env/group_vars/all/vault.yml  Encrypted secrets
playbooks/                                 Ansible playbooks
scripts/                                   Deployment and maintenance scripts
templates/                                 OpenShift, NMState and other templates
files/                                     Supporting configuration files
build/                                     Generated installation state and kubeconfigs
```

`build/` is generated and must not be committed to Git.

## 1. Configure the Environment

Edit the non-secret configuration:

```bash
nano inventories/env/group_vars/all/main.yml
```

Typical values include:

- Cluster names and OpenShift release
- SNO IP address, gateway and DNS
- vCenter, ESXi, datastore and port group
- SNO VM CPU, memory and disks
- Site-A and Site-B networking
- Bare-metal/iDRAC information
- Everpure and Portworx configuration
- HCP tenant sizing and network ranges

Display the active configuration:

```bash
./scripts/show-environment-config.sh
```

### Secrets

Secrets belong only in:

```text
inventories/env/group_vars/all/vault.yml
```

Create the vault from the example if required:

```bash
cp inventories/env/group_vars/all/vault.yml.example \
   inventories/env/group_vars/all/vault.yml

nano inventories/env/group_vars/all/vault.yml
ansible-vault encrypt inventories/env/group_vars/all/vault.yml
```

Edit an existing encrypted vault with:

```bash
ansible-vault edit inventories/env/group_vars/all/vault.yml
```

View it when troubleshooting:

```bash
ansible-vault view inventories/env/group_vars/all/vault.yml
```

Do not commit decrypted vault files, pull secrets, private keys, generated kubeconfigs or other credentials.

## 2. Prepare the Ubuntu Bastion

Supported bastion OS:

```text
Ubuntu 24.04
```

Bootstrap the required tools:

```bash
chmod +x scripts/*.sh scripts/lib/*.sh
./scripts/bootstrap-ubuntu-24.04.sh
source .venv/bin/activate
```

Activate the virtual environment in every new terminal:

```bash
source .venv/bin/activate
```

Check the main tools:

```bash
oc version --client
openshift-install version
ansible --version
nmstatectl --version
```

## 3. SNO Networking

The SNO Agent configuration does **not** hard-code Linux interface names such as `ens33` or `ens192`.

The configuration uses:

```text
logical interface: eth0
        |
        v
VMware vNIC MAC address
        |
        v
actual RHCOS interface name
```

The Agent Installer maps the logical interface to the real NIC by MAC address.

Before creating the ISO, the automation validates that the generated NetworkManager configuration contains the configured:

- SNO IP address
- Default gateway
- DNS server
- NIC MAC address

If the gateway is missing, ISO creation stops instead of booting a broken image.

### Refresh the Ubuntu NMState shim

If the SNO networking templates or NMState shim have changed, run:

```bash
./scripts/install-nmstatectl-ubuntu.sh
```

V9 performs a default-route self-test and must confirm that a gateway is generated correctly.

## 4. Deploy the SNO Hub

The easiest method is:

```bash
./scripts/run.sh
```

This performs the SNO preflight, DNS configuration, Agent ISO generation, vSphere VM creation and the hub installation workflow.

For troubleshooting, the SNO stages can be run separately:

```bash
ansible-playbook -i inventories/env/hosts.yml \
  playbooks/00_preflight.yml --ask-vault-pass

ansible-playbook -i inventories/env/hosts.yml \
  playbooks/01_render_agent_iso.yml --ask-vault-pass

ansible-playbook -i inventories/env/hosts.yml \
  playbooks/02_create_vsphere_vm.yml --ask-vault-pass \
  -e sno_vm_recreate=true

ansible-playbook -i inventories/env/hosts.yml \
  playbooks/03_wait_install.yml --ask-vault-pass
```

### Check the generated SNO network configuration

Before booting the VM, verify:

```bash
grep -nE 'address1=|gateway=|dns=|never-default=' \
  build/lab-sno/rendered/networkmanager-generated.yaml
```

You should see the configured address, gateway and DNS values.

To inspect the Agent configuration:

```bash
cat build/lab-sno/rendered/agent-config.yaml
```

## 5. Deploy Hub and Physical Spokes

Deploy or resume the SNO hub, Site-A and Site-B:

```bash
./scripts/run-full-hub-and-spoke.sh
```

The workflow validates the environment, deploys the clusters, imports the spokes into RHACM and applies the required hosting-cluster configuration.

Site-specific day-2 workflows can be run independently:

```bash
./scripts/run-site-a-day2.sh
./scripts/run-site-b-day2.sh
```

## 6. Portworx and Everpure

Deploy or reconcile Site-A storage:

```bash
SITE=site-a ./scripts/bootstrap-pure-token-and-portworx.sh
SITE=site-a ./scripts/check-portworx-pure.sh
```

Deploy or reconcile Site-B storage:

```bash
SITE=site-b ./scripts/bootstrap-pure-token-and-portworx.sh
SITE=site-b ./scripts/check-portworx-pure.sh
```

Validate HCP storage classes:

```bash
./scripts/check-hcp-portworx-storage.sh
```

## 7. Hosted Control Plane Tenants

Create all configured HCP tenants and import them into RHACM:

```bash
./scripts/hcp-create.sh
```

Verify them with:

```bash
./scripts/check-hcp-guest-imports.sh
./scripts/check-hcp-portworx-storage.sh
```

Exported HCP kubeconfigs are stored under:

```text
build/lab-sno/hcp-kubeconfigs/
```

Delete the HCP tenants with:

```bash
./scripts/hcp-delete.sh
```

## 8. Verify the Environment

Load the hub kubeconfig:

```bash
export KUBECONFIG="$PWD/build/lab-sno/install/auth/kubeconfig"
```

Basic checks:

```bash
oc get nodes
oc get clusterversion
oc get managedcluster
```

Check ACM:

```bash
./scripts/check-acm.sh
```

Useful diagnostics:

```bash
./scripts/acm-diagnostics.sh
./scripts/show-repo-disk-usage.sh
```

Additional troubleshooting information is in:

```text
docs/troubleshooting.md
```

## 9. Clean Rebuild

For a full teardown, remove resources in dependency order:

```bash
./scripts/hcp-delete.sh

# Only when intentionally removing Portworx data:
CONFIRM_PORTWORX_WIPE=true \
  ./scripts/portworx-uninstall-and-wipe-spokes.sh

CONFIRM_DELETE_SITE_B=true ./scripts/site-b-delete.sh
CONFIRM_DELETE_SITE_A=true ./scripts/site-a-delete.sh
CONFIRM_DELETE_HUB=true ./scripts/hub-delete.sh
```

Prepare the repo for a fresh OpenShift 4.21 build:

```bash
CONFIRM_PREPARE_421_REBUILD=true \
  ./scripts/prepare-clean-4.21-rebuild.sh
```

For only the SNO installation state:

```bash
./scripts/reset-sno-hub-build.sh
```

## Main Commands

| Task | Command |
|---|---|
| Bootstrap bastion | `./scripts/bootstrap-ubuntu-24.04.sh` |
| Deploy/resume SNO hub | `./scripts/run.sh` |
| Deploy hub + both spokes | `./scripts/run-full-hub-and-spoke.sh` |
| Site-A day-2 | `./scripts/run-site-a-day2.sh` |
| Site-B day-2 | `./scripts/run-site-b-day2.sh` |
| Deploy HCP tenants | `./scripts/hcp-create.sh` |
| Delete HCP tenants | `./scripts/hcp-delete.sh` |
| Check ACM | `./scripts/check-acm.sh` |
| Check HCP imports | `./scripts/check-hcp-guest-imports.sh` |
| Check Portworx | `./scripts/check-portworx-pure.sh` |
| Refresh NMState shim | `./scripts/install-nmstatectl-ubuntu.sh` |
| Show configuration | `./scripts/show-environment-config.sh` |

## Security

Keep all credentials in the encrypted Ansible Vault. Never commit:

- Plaintext credentials
- Pull secrets
- Private SSH keys
- Kubeconfigs
- Generated ISO images
- The `build/` directory
- Vault password files

The repository `.gitignore` is configured to exclude generated installation artifacts and common local files.
