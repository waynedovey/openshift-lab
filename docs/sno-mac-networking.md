# SNO networking: MAC-based, device-name independent

This repository deliberately avoids hard-coding the Linux interface name for the vSphere SNO VM.

## Why

VMware/RHCOS can expose the same vNIC as `ens33`, `ens192`, `eno1`, or another predictable-network-interface name depending on the virtual hardware and environment. A default route that refers to the wrong kernel name can fail to apply, leaving DNS reachable on the local subnet but external destinations such as `quay.io` unreachable.

## Design

`inventories/env/group_vars/all/main.yml` defines only a stable logical profile and the vNIC MAC:

```yaml
sno_node:
  primary_profile: primary
  mac_eth0: "00:50:56:23:74:90"
```

`playbooks/02_create_vsphere_vm.yml` assigns that MAC to the VMware vNIC. `templates/agent-config.yaml.j2` uses the same MAC with Nmstate:

```yaml
interfaces:
  - name: primary
    type: ethernet
    state: up
    identifier: mac-address
    mac-address: 00:50:56:23:74:90
```

The default route points to the logical profile rather than a kernel device name:

```yaml
routes:
  config:
    - destination: 0.0.0.0/0
      next-hop-address: 10.23.74.1
      next-hop-interface: primary
      table-id: 254
```

## Validation

`00_preflight.yml` validates the MAC/profile/gateway inputs. `01_render_agent_iso.yml` parses the rendered AgentConfig and refuses to create the ISO if MAC matching or the default route is absent.

After rendering, inspect the effective configuration with:

```bash
sed -n '1,180p' build/lab-sno/rendered/agent-config.yaml
```

You should see `identifier: mac-address` and a default route via `10.23.74.1` using `next-hop-interface: primary`.
