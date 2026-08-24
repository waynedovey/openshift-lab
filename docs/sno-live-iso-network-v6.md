# SNO live-ISO network override (V6)

The AgentConfig remains the canonical OpenShift host network definition. V6 also
post-processes the generated Agent ISO with a NetworkManager keyfile using
`coreos-installer iso network embed`.

This is intentional. In this vSphere lab, the Agent TUI repeatedly received the
static IP and DNS but lost the default route in the live NetworkManager profile.
The direct keyfile is bound to the VM NIC MAC address rather than `ens33` or
`ens192`, so it remains portable between environments where Linux interface names
change.

The final ISO is validated by extracting its embedded network settings and
asserting that it contains:

- MAC address from `sno_node.mac_eth0`
- static SNO IP/prefix
- default gateway
- DNS server(s)
- `autoconnect=true`
- `never-default=false`

Troubleshooting artifacts are written under `build/<cluster>/rendered/`:

- `sno-primary.nmconnection`
- `iso-embedded-network.txt`
- `agent-config.yaml`
- `network-config.yaml`
- `networkmanager-generated.yaml`

No Linux kernel interface name is hard-coded.
