#!/usr/bin/env python3
import configparser
import pathlib
import sys

if len(sys.argv) < 6:
    raise SystemExit("usage: validate-networkmanager-keyfile.py KEYFILE IP/PREFIX GATEWAY DNS_CSV MAC")

path = pathlib.Path(sys.argv[1])
expected_addr = sys.argv[2]
expected_gateway = sys.argv[3]
expected_dns = [x for x in sys.argv[4].split(',') if x]
expected_mac = sys.argv[5].lower()

raw = path.read_text()
parser = configparser.ConfigParser(interpolation=None, strict=True)
parser.optionxform = str
try:
    parser.read_string(raw)
except Exception as exc:
    raise SystemExit(f"invalid NetworkManager keyfile syntax: {exc}")

for section in ("connection", "802-3-ethernet", "ipv4", "ipv6"):
    if section not in parser:
        raise SystemExit(f"missing [{section}] section")

conn = parser["connection"]
eth = parser["802-3-ethernet"]
ipv4 = parser["ipv4"]

checks = {
    "connection.autoconnect": conn.get("autoconnect", "").lower() == "true",
    "ethernet.mac-address": eth.get("mac-address", "").lower() == expected_mac,
    "ipv4.method": ipv4.get("method", "").lower() == "manual",
    "ipv4.address1": ipv4.get("address1", "") == expected_addr,
    "ipv4.gateway": ipv4.get("gateway", "") == expected_gateway,
    "ipv4.never-default": ipv4.get("never-default", "").lower() == "false",
    "ipv4.may-fail": ipv4.get("may-fail", "").lower() == "false",
}

raw_dns = ipv4.get("dns", "")
actual_dns = [x for x in raw_dns.split(';') if x]
checks["ipv4.dns"] = actual_dns == expected_dns

failed = [name for name, ok in checks.items() if not ok]
if failed:
    details = "\n".join(f"  {name}: FAIL" for name in failed)
    raise SystemExit(
        "NetworkManager keyfile validation failed:\n"
        + details
        + f"\nExpected address={expected_addr} gateway={expected_gateway} dns={expected_dns} mac={expected_mac}"
        + f"\nParsed ipv4={dict(ipv4)}"
    )

# Guard specifically against the V6 Jinja trim_blocks failure.
if "never-default=false" in raw_dns:
    raise SystemExit("invalid dns value: never-default=false was concatenated onto dns= due to Jinja whitespace trimming")

print(
    f"VALID keyfile: address={expected_addr} gateway={expected_gateway} "
    f"dns={','.join(expected_dns)} mac={expected_mac} autoconnect=true never-default=false"
)
