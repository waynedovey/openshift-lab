# SNO VMware fixes for this lab

This repo version is fixed for the current pod-22 VMware SNO hub design.

## SNO networking

The SNO hub VM uses one NIC only:

```yaml
sno_node:
  primary_interface: ens192
  secondary_nic_enabled: false
  mac_eth1: ""
  secondary_interface: ""

vm_network_eth0: VLAN3522
vm_network_eth1: ""
```

Do not attach VLAN522 to the SNO hub. VLAN522 can be used later for other lab hosts or workloads, but the hub itself only needs the VLAN3522 machine network.

## vSphere disk UUID

The VM creation playbook enforces:

```text
disk.EnableUUID = TRUE
```

This is done with `scripts/set-vm-advanced-setting.py` through pyVmomi after the VM is created or updated.

## Clean rebuild after changing NIC config

If an earlier Agent ISO was generated with two NICs, remove the old build state and regenerate:

```bash
rm -rf build/hub-sno
ansible-playbook -i inventories/pod22/hosts.yml playbooks/01_render_agent_iso.yml --ask-vault-pass
ansible-playbook -i inventories/pod22/hosts.yml playbooks/02_create_vsphere_vm.yml --ask-vault-pass
```

For a full VM recreate, set:

```yaml
sno_vm_recreate: true
```

Then run `02_create_vsphere_vm.yml`. Set the value back to `false` afterwards.
