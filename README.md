# OCP SNO VMware Hub + ACM Bare-Metal Spoke - Ansible Starter

This repo bootstraps a Single Node OpenShift (SNO) cluster on VMware vSphere using the OpenShift Agent-based Installer, installs Red Hat Advanced Cluster Management (ACM) on that SNO hub, then uses ACM / multicluster engine / Assisted Installer to build a managed bare-metal OpenShift cluster from Dell PowerEdge nodes.

The pattern is:

1. Render `install-config.yaml` and `agent-config.yaml` from Ansible variables.
2. Generate an OpenShift `agent.iso` that contains the static network configuration for the SNO hub.
3. Upload the ISO to a vSphere datastore.
4. Create a vSphere VM with two NICs:
   - `eth0` / `ens192` on VLAN 3522 port group
   - `eth1` / `ens224` on VLAN 522 port group
5. Attach the ISO, boot the VM, and wait for the OpenShift SNO install to complete.
6. Install ACM on the SNO hub.
7. Configure Assisted Service storage on the hub.
8. Render and apply the bare-metal spoke cluster resources:
   - `ManagedCluster`
   - `KlusterletAddonConfig`
   - `ClusterDeployment`
   - `AgentClusterInstall`
   - `InfraEnv`
   - `NMStateConfig`
   - `BareMetalHost`
   - BMC and pull-secret `Secret` objects
9. Boot the Dell nodes through iDRAC Redfish virtual media and let ACM deploy the managed cluster.
10. Optionally configure AD DNS records for both clusters.

> Do not commit real credentials, pull secrets, kubeconfigs, or generated install state to GitHub.

---

## Hub and spoke design

```text
VMware / vSphere
  └── hub-sno VM
        └── OpenShift SNO
              └── ACM + multicluster engine + Assisted Service
                    └── bm-spoke-01 bare-metal OpenShift cluster
                          ├── b08-33 master
                          ├── b08-34 master
                          ├── b08-35 master
                          ├── b08-36 worker
                          ├── b09-33 worker
                          └── b09-34 worker
```

See [`docs/hub-spoke-architecture.md`](docs/hub-spoke-architecture.md) for the full IP and BMC plan.

## Lab assumptions

These values are based on the provided pod-22 lab details and should be adjusted in `inventories/pod22/group_vars/all.yml`.

| Item | Example |
|---|---|
| vCenter | `10.23.22.10` |
| ESXi host | `10.23.22.11` |
| Ansible controller / bastion | `10.23.22.12` / Ubuntu 24.04.4 LTS |
| AD DNS | `10.23.22.100` |
| Base domain | `poc.local` |
| Cluster name | `hub-sno` |
| SNO node IP | `10.23.22.90` |
| API VIP | `10.23.22.91` |
| Ingress VIP | `10.23.22.92` |
| Gateway | `10.23.22.1` |
| Machine network | `10.23.22.0/24` |
| DNS server | `10.23.22.100` |
| VLAN 3522 port group | `VLAN3522` |
| VLAN 522 port group | `VLAN522` |
| Bare-metal cluster | `bm-spoke-01` |
| Bare-metal API VIP | `10.23.22.120` |
| Bare-metal Ingress VIP | `10.23.22.121` |

DNS records expected:

```text
api.hub-sno.poc.local       -> 10.23.22.91
api-int.hub-sno.poc.local   -> 10.23.22.91
*.apps.hub-sno.poc.local    -> 10.23.22.92
hub-sno-0.hub-sno.poc.local -> 10.23.22.90
```

---

## Prerequisites on the Ubuntu 24.04.4 LTS bastion

The Ansible controller for this lab is the Ubuntu bastion VM:

| Item | Value |
|---|---|
| Bastion VM | `RedHat-VM01` |
| Bastion IP | `10.23.22.12` |
| OS | Ubuntu 24.04.4 LTS |
| Role | Ansible control node, OpenShift installer host, vSphere automation runner |

Use the included bootstrap script from the Ubuntu bastion:

```bash
cd ocp-sno-vsphere-ansible
./scripts/bootstrap-ubuntu-24.04.sh
source .venv/bin/activate
```

By default the script downloads the OpenShift client and installer from the `stable-4.21` client stream. To pin a specific client/installer version, run:

```bash
OPENSHIFT_VERSION=4.21.0 ./scripts/bootstrap-ubuntu-24.04.sh
```

The bootstrap installs the Ubuntu packages, creates a Python virtual environment, installs the Python module requirements, installs the Ansible Galaxy collections, and places `oc`, `kubectl`, and `openshift-install` in `/usr/local/bin`.

Validate the bastion before running the cluster automation:

```bash
source .venv/bin/activate
oc version --client
kubectl version --client
openshift-install version
ansible --version
ansible-galaxy collection list | egrep 'community.vmware|ansible.windows|ansible.utils'
```

The Ubuntu-specific requirements are split into two files:

```text
requirements-python.txt   # Python packages installed into .venv
requirements.yml          # Ansible Galaxy collections
```

See [`docs/ubuntu-bastion.md`](docs/ubuntu-bastion.md) for the full Ubuntu package list, venv setup, proxy notes, and validation steps.

---

## Configure variables

Edit:

```bash
inventories/pod22/group_vars/all.yml
```

Create your private vault file from the example:

```bash
source .venv/bin/activate
cp inventories/pod22/group_vars/vault.yml.example inventories/pod22/group_vars/vault.yml
ansible-vault encrypt inventories/pod22/group_vars/vault.yml
ansible-vault edit inventories/pod22/group_vars/vault.yml
```

Put your real vCenter password, pull secret, and SSH public key in the encrypted vault file.

---

## Run the SNO hub build

Run all commands from the Ubuntu bastion with the repo virtual environment active:

```bash
source .venv/bin/activate
```

Then run:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/00_preflight.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/04_configure_ad_dns.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/01_render_agent_iso.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/02_create_vsphere_vm.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/03_wait_install.yml --ask-vault-pass
```

Or run the SNO-only flow:

```bash
./scripts/run.sh
```

## Install ACM on the SNO hub

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/06_install_acm.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/07_configure_assisted_service.yml --ask-vault-pass
```

The ACM channel is controlled by this variable:

```yaml
acm_subscription_channel: release-2.16
```

Check available channels on your hub with:

```bash
oc get packagemanifest advanced-cluster-management -n openshift-marketplace \
  -o jsonpath='{.status.channels[*].name}'
```

## Build the ACM managed bare-metal cluster

First, confirm the missing boot MACs for `b09-33` and `b09-34` in:

```bash
inventories/pod22/group_vars/all.yml
```

Then run:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/10_configure_bm_ad_dns.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/05_idrac_preflight.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/08_apply_baremetal_cluster.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/09_wait_baremetal_cluster.yml --ask-vault-pass
```

Or run the full hub-and-spoke flow:

```bash
./scripts/run-full-hub-and-spoke.sh
```

---

## Optional AD DNS setup

If WinRM is enabled to the AD server, you can run:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/04_configure_ad_dns.yml --ask-vault-pass
```

If WinRM is not enabled, create these records manually in AD DNS:

```powershell
Add-DnsServerResourceRecordA -ZoneName "poc.local" -Name "api.hub-sno" -IPv4Address "10.23.22.91"
Add-DnsServerResourceRecordA -ZoneName "poc.local" -Name "api-int.hub-sno" -IPv4Address "10.23.22.91"
Add-DnsServerResourceRecordA -ZoneName "poc.local" -Name "*.apps.hub-sno" -IPv4Address "10.23.22.92"
Add-DnsServerResourceRecordA -ZoneName "poc.local" -Name "hub-sno-0.hub-sno" -IPv4Address "10.23.22.90"
```

---

## Bare-metal cluster defaults

The default spoke cluster uses the Dell nodes like this:

| Node | iDRAC IP | OpenShift IP | Role | Status |
|---|---:|---:|---|---|
| b08-33 | 10.23.22.80 | 10.23.22.110 | master | ready |
| b08-34 | 10.23.22.81 | 10.23.22.111 | master | ready |
| b08-35 | 10.23.22.82 | 10.23.22.112 | master | ready |
| b08-36 | 10.23.22.83 | 10.23.22.113 | worker | ready |
| b09-33 | 10.23.22.84 | 10.23.22.114 | worker | needs boot MAC |
| b09-34 | 10.23.22.85 | 10.23.22.115 | worker | needs boot MAC |

The `10.23.22.80-85` addresses are treated as BMC/iDRAC IPs, not OpenShift node IPs.

The default BMC URL format is:

```text
redfish-virtualmedia://<idrac-ip>/redfish/v1/Systems/System.Embedded.1
```

This is required for this no-DHCP/no-provisioning-network style of automation.

## Switching to a 3-node compact cluster

For a smaller demo cluster, keep only the first three nodes enabled:

```yaml
bm_control_plane_count: 3
bm_worker_count: 0

# b08-36, b09-33, b09-34
enabled: false
```

## Validation

After the SNO hub install finishes:

```bash
export KUBECONFIG="$PWD/build/hub-sno/auth/kubeconfig"
oc get nodes
oc get clusterversion
oc get co
oc get route console -n openshift-console
```

After the bare-metal cluster is created from ACM:

```bash
oc get managedcluster
oc -n bm-spoke-01 get clusterdeployment,agentclusterinstall,infraenv
oc -n bm-spoke-01 get bmh,agents -o wide
```

Console URL:

```text
https://console-openshift-console.apps.hub-sno.poc.local
```

---

## Important notes

- DHCP is not used. Static IP is embedded in `agent-config.yaml`.
- The SNO VM NIC MAC addresses must match the MAC addresses in `agent-config.yaml`.
- The VMware port group backing `eth0` must be an access port group for VLAN 3522.
- The VMware port group backing `eth1` must be an access port group for VLAN 522.
- `apiVIPs` and `ingressVIPs` must be in the machine network.
- The VMware playbook defaults to the standalone ESXi host at `10.23.22.11`; if your vCenter inventory uses a cluster, edit `02_create_vsphere_vm.yml` to use `cluster` instead of `esxi_hostname`.
- Use a separate API VIP and Ingress VIP. Do not reuse the node IP unless you have validated that specific design.
- `.local` can conflict with mDNS in some environments. It is okay for a controlled lab, but a normal DNS zone is cleaner.
- The ACM bare-metal flow assumes Redfish virtual media because DHCP and a provisioning network are not being used.
- The b09-33 and b09-34 boot NIC MAC addresses are placeholders and must be filled in before running `08_apply_baremetal_cluster.yml`.
- The starter enforces iDRAC firmware consistency and currently expects `7.30.30.51`. Update `idrac_firmware_expected` if you standardise on a different version.

