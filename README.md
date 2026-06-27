# OCP SNO Hub + Site-A + Site-B Lab

This repo builds a simple OpenShift lab:

```text
hub-sno on VMware/vSphere
  ├── RHACM + Assisted Installer
  ├── Site-A bare-metal cluster: b08-33, b08-34, b08-35
  └── Site-B bare-metal cluster: b08-36, b09-33, b09-34
```

The detailed docs are still in `docs/`. This README is the simple runbook.

---

## 1. Start on the Ubuntu bastion

```bash
cd ~/OCP/ocp-sno-vsphere-ansible
source .venv/bin/activate
```

If `.venv` does not exist yet:

```bash
./scripts/bootstrap-ubuntu-24.04.sh
source .venv/bin/activate
```

---

## 2. Check the main config

Edit this file:

```bash
vi inventories/pod22/group_vars/all/main.yml
```

Important values:

```text
hub-sno IP:       10.23.22.90
Site-A API VIP:   10.23.22.120
Site-A apps VIP:  10.23.22.121
Site-B API VIP:   10.23.22.130
Site-B apps VIP:  10.23.22.131
DNS server:       10.23.22.100
```

Site-A nodes:

```text
b08-33 -> 10.23.22.110
b08-34 -> 10.23.22.111
b08-35 -> 10.23.22.112
```

Site-B nodes:

```text
b08-36 -> 10.23.22.113
b09-33 -> 10.23.22.114
b09-34 -> 10.23.22.115
```

Before running Site-B, replace these placeholders in `main.yml`:

```text
CHANGE_ME_B09_33_BOOT_NIC_MAC
CHANGE_ME_B09_34_BOOT_NIC_MAC
```

Use this to discover the iDRAC NIC MACs:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/05_discover_site_b_idrac_nics.yml --ask-vault-pass
```

Use the MAC for the NIC cabled to the OpenShift machine network/VLAN. In this lab, the Linux interface name is expected to be `eno33np0`.

---

## 3. Build the SNO hub only

This creates the VMware SNO VM, uploads the Agent ISO, boots the VM, and waits for OpenShift install.

```bash
./scripts/run.sh
```

The script asks for the Vault password once.

After it finishes:

```bash
export KUBECONFIG=$PWD/build/hub-sno/install/auth/kubeconfig
oc get nodes
oc get clusterversion
oc get co
```

---

## 4. Configure hub services and create Site-A

After the hub is up, run:

```bash
./scripts/run-site-a-day2.sh
```

This does the hub Day-2 work and provisions Site-A:

```text
adds/checks SNO second disk
installs LVM Storage on the hub
installs RHACM
configures Assisted Service
configures Metal3/BareMetal provisioning
creates DNS for Site-A
checks iDRAC access
creates Site-A from b08-33, b08-34, b08-35
```

Watch Site-A:

```bash
export KUBECONFIG=$PWD/build/hub-sno/install/auth/kubeconfig
oc -n site-a get bmh,agent -w
```

When complete:

```bash
oc get managedcluster site-a
```

---

## 5. Create Site-B

First make sure the b09 MAC placeholders are fixed in `main.yml`.

Then run:

```bash
./scripts/run-site-b-day2.sh
```

This creates Site-B from:

```text
b08-36
b09-33
b09-34
```

Watch Site-B:

```bash
export KUBECONFIG=$PWD/build/hub-sno/install/auth/kubeconfig
oc -n site-b get bmh,agent -w
```

When complete:

```bash
oc get managedcluster site-b
```

---

## 6. Full run: hub + Site-A + Site-B

Only use this when you are ready to build everything in one go:

```bash
./scripts/run-full-hub-and-spoke.sh
```

It asks for the Vault password once and then runs the hub, Site-A, and Site-B flow.

---

## 7. Useful checks

Hub DNS:

```bash
getent hosts api.hub-sno.poc.local
getent hosts api-int.hub-sno.poc.local
getent hosts test.apps.hub-sno.poc.local
```

Hub health:

```bash
export KUBECONFIG=$PWD/build/hub-sno/install/auth/kubeconfig
oc get nodes
oc get co
```

Site-A:

```bash
oc -n site-a get clusterdeployment,agentclusterinstall,infraenv,bmh,agent -o wide
oc get managedcluster site-a
```

Site-B:

```bash
oc -n site-b get clusterdeployment,agentclusterinstall,infraenv,bmh,agent -o wide
oc get managedcluster site-b
```

---

## 8. If you need to reset

Reset the hub build directory only:

```bash
./scripts/reset-sno-hub-build.sh
```

Reset Site-A discovery objects after changing MACs/NMState:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/08_reset_site_a_for_nmstate_fix.yml --ask-vault-pass
```

Reset Site-B discovery objects after changing MACs/NMState:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/08_reset_site_b_for_nmstate_fix.yml --ask-vault-pass
```

Then reapply the relevant site:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/08_apply_baremetal_cluster.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/08_apply_site_b_baremetal_cluster.yml --ask-vault-pass
```

---

## 9. Common problem areas

If a bare-metal node does not get its static IP, check:

```bash
oc -n site-a get nmstateconfig -o yaml
oc -n site-b get nmstateconfig -o yaml
```

Make sure the MAC and interface name match the real NIC. For these Dell nodes, `eno33np0` is usually the correct RHCOS interface name for the cabled NIC.

If Agent ISO boot fails with rootfs download errors, check the Assisted Image Service route:

```bash
ansible-playbook -i inventories/pod22/hosts.yml playbooks/07_validate_assisted_image_service.yml --ask-vault-pass
```

If RHACM shows a managed cluster as `Unknown`, check:

```bash
oc get managedcluster
oc get managedclusteraddon -A
```

