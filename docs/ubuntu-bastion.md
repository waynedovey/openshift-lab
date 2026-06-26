# Ubuntu 24.04.4 LTS bastion requirements

This repo assumes the automation runs from the Ubuntu bastion VM, `RedHat-VM01`, at `10.23.22.12`.

The Ubuntu bastion is the Ansible control node. It needs network reachability to:

- vCenter: `10.23.22.10`
- ESXi host through vCenter inventory: `10.23.22.11`
- AD DNS server, if DNS automation is used: `10.23.22.100`
- iDRAC/BMC addresses: `10.23.22.80-85`
- OpenShift hub/spoke API and ingress VIPs
- Red Hat and OpenShift image registries, unless this is later converted to a disconnected workflow

## Required Ubuntu packages

The bootstrap script installs the practical baseline:

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl dnsutils genisoimage git gzip iproute2 iputils-ping jq \
  netcat-openbsd openssh-client openssl pipx python3 python3-full python3-pip \
  python3-venv sshpass tar unzip wget xz-utils
```

`nmstate` is installed only if the package is available from your enabled Ubuntu repositories. The repo renders NMState YAML into OpenShift Agent Installer and Assisted Installer resources, so `nmstatectl` is helpful for local validation but not strictly required.

## Python virtual environment

Ubuntu 24.04 uses Python's externally managed environment model, so do not install the required Python packages into the system Python with `pip --user`.

Use the repo virtual environment instead:

```bash
cd ocp-sno-vsphere-ansible
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements-python.txt
ansible-galaxy collection install -r requirements.yml
```

Expected key Python packages:

- `ansible-core`
- `pyvmomi` for vSphere automation
- `requests` for Redfish/iDRAC checks
- `PyYAML` for rendered YAML validation
- `netaddr` for IP/CIDR validation filters
- `pywinrm` for optional AD DNS automation over WinRM

## OpenShift CLI and installer

The `oc`, `kubectl`, and `openshift-install` binaries must be in `PATH`.

The bootstrap script downloads them from the OpenShift client mirror:

```bash
OPENSHIFT_VERSION=stable-4.21 ./scripts/bootstrap-ubuntu-24.04.sh
```

You can pin a specific payload client version instead:

```bash
OPENSHIFT_VERSION=4.21.0 ./scripts/bootstrap-ubuntu-24.04.sh
```

Validate afterwards:

```bash
oc version --client
kubectl version --client
openshift-install version
ansible --version
```

## Run from the venv

Every run should start with:

```bash
cd ocp-sno-vsphere-ansible
source .venv/bin/activate
```

Then run the normal flow:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/00_preflight.yml --ask-vault-pass
./scripts/run-full-hub-and-spoke.sh
```

## Notes

- Keep `inventories/pod22/group_vars/vault.yml` encrypted with Ansible Vault.
- Do not commit `.venv/`, generated ISOs, kubeconfigs, pull secrets, or the `build/` directory.
- If the Ubuntu VM uses a proxy, export `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` before running the bootstrap and playbooks. Include `10.23.22.0/24`, `.poc.local`, vCenter, iDRACs, and the OpenShift API VIPs in `NO_PROXY`.


## Ansible callback compatibility

Ubuntu 24.04 will normally install a recent Ansible version and the latest `community.general` collection. In `community.general` 12.0.0 and later, the old YAML callback plugin is removed.

The repo therefore uses this in `ansible.cfg`:

```ini
stdout_callback = ansible.builtin.default
callback_result_format = yaml
```

Do not set this anymore:

```ini
stdout_callback = yaml
```

That older setting can resolve to `community.general.yaml` and fail before the playbook starts.
