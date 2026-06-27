#!/usr/bin/env python3
"""Discover Dell iDRAC host NIC MACs/link state through Redfish.

This is intentionally read-only. It walks common Dell Redfish NIC endpoints and
prints a compact table plus YAML suggestions for bm_nodes.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any


def get_json(host: str, path: str, user: str, password: str, timeout: int = 15) -> Any | None:
    url = f"https://{host}{path}"
    req = urllib.request.Request(url)
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as exc:
        return None


def member_ids(obj: Any) -> list[str]:
    if not isinstance(obj, dict):
        return []
    out: list[str] = []
    for m in obj.get("Members", []) or []:
        if isinstance(m, dict) and m.get("@odata.id"):
            out.append(m["@odata.id"])
    return out


def nested_odata_ids(obj: Any) -> list[str]:
    ids: list[str] = []
    def walk(x: Any):
        if isinstance(x, dict):
            oid = x.get("@odata.id")
            if isinstance(oid, str) and any(k in oid.lower() for k in ["network", "ethernet", "adapter", "port", "function"]):
                ids.append(oid)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(obj)
    return ids


def macs_from(obj: dict[str, Any]) -> list[str]:
    keys = ["MACAddress", "PermanentMACAddress", "CurrentMACAddress"]
    macs: list[str] = []
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and ":" in v:
            macs.append(v.upper())
    for k in ["AssociatedNetworkAddresses", "IPv4Addresses"]:
        v = obj.get(k)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str) and ":" in item and len(item) >= 12:
                    macs.append(item.upper())
    # Preserve order, unique
    seen=set(); out=[]
    for m in macs:
        if m not in seen:
            out.append(m); seen.add(m)
    return out


def collect_for_host(host: str, user: str, password: str) -> list[dict[str, Any]]:
    roots = [
        "/redfish/v1/Systems/System.Embedded.1/EthernetInterfaces",
        "/redfish/v1/Systems/System.Embedded.1/NetworkInterfaces",
        "/redfish/v1/Chassis/System.Embedded.1/NetworkAdapters",
        "/redfish/v1/Managers/iDRAC.Embedded.1/EthernetInterfaces",
    ]
    to_fetch: list[str] = []
    seen: set[str] = set()
    for root in roots:
        data = get_json(host, root, user, password)
        if data is None:
            continue
        to_fetch.extend(member_ids(data))
        to_fetch.extend(nested_odata_ids(data))
    records: list[dict[str, Any]] = []
    depth = 0
    while to_fetch and depth < 250:
        depth += 1
        path = to_fetch.pop(0)
        if path in seen:
            continue
        seen.add(path)
        data = get_json(host, path, user, password)
        if data is None or not isinstance(data, dict):
            continue
        to_fetch.extend([p for p in member_ids(data) if p not in seen])
        to_fetch.extend([p for p in nested_odata_ids(data) if p not in seen])
        macs = macs_from(data)
        if macs:
            records.append({
                "path": path,
                "id": data.get("Id", ""),
                "name": data.get("Name", ""),
                "description": data.get("Description", ""),
                "macs": macs,
                "link": data.get("LinkStatus", data.get("Status", {}).get("State", "")),
                "health": data.get("Status", {}).get("Health", ""),
                "speed": data.get("CurrentLinkSpeedMbps", data.get("SpeedMbps", data.get("LinkSpeedMbps", ""))),
                "port": data.get("PhysicalPortNumber", data.get("PortId", data.get("PortNumber", ""))),
            })
    # de-duplicate by path+macs
    uniq=[]; seenkeys=set()
    for r in records:
        key=(r["path"], tuple(r["macs"]))
        if key not in seenkeys:
            uniq.append(r); seenkeys.add(key)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes-json", required=True, help="JSON list with node name/bmc_ip/boot_mac/ip fields")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password-env", default="IDRAC_PASSWORD")
    args = ap.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        print(f"ERROR: environment variable {args.password_env} is not set", file=sys.stderr)
        return 2
    nodes = json.loads(args.nodes_json)
    for node in nodes:
        if not node.get("enabled", True):
            continue
        print(f"\n# {node.get('name')}  iDRAC={node.get('bmc_ip')}  current boot_mac={node.get('boot_mac')}  target_ip={node.get('ip')}")
        recs = collect_for_host(str(node.get("bmc_ip")), args.user, password)
        if not recs:
            print("  No NIC MACs found from Redfish candidate endpoints")
            continue
        print("  Link       Speed     Port/Id                         MAC(s)                         Redfish path/name")
        print("  ---------  --------  ------------------------------  -----------------------------  -----------------")
        for r in recs:
            link = str(r.get("link") or "")[:9]
            speed = str(r.get("speed") or "")[:8]
            port = str(r.get("port") or r.get("id") or "")[:30]
            mac = ",".join(r["macs"])
            name = str(r.get("name") or r.get("description") or r.get("path"))[:80]
            print(f"  {link:<9}  {speed:<8}  {port:<30}  {mac:<29}  {name}")
        current = str(node.get("boot_mac", "")).upper()
        matches = [r for r in recs if current and current in r["macs"]]
        if matches:
            m = matches[0]
            print(f"  MATCH: current boot_mac {current} found on {m.get('name') or m.get('id')} link={m.get('link')} speed={m.get('speed')}")
        link_up = [r for r in recs if str(r.get("link", "")).lower() in ["up", "enabled"]]
        if link_up:
            print("  Link-up MAC candidates:")
            for r in link_up:
                for mac in r["macs"]:
                    print(f"    - {mac}  # {r.get('name') or r.get('id')} {r.get('port')} {r.get('speed')}")
    print("\n# NOTE: iDRAC can tell you the hardware MAC/link state, but not the RHCOS Linux interface name.")
    print("# Use the interface name shown on the RHCOS console/login banner or from Agent inventory. For these R6525 Broadcom ports it is commonly eno33np0 for Integrated NIC 1 Port 1.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
