#!/usr/bin/env python3
"""Add an extra VMDK to an existing vSphere VM using pyVmomi."""
import argparse
import atexit
import ssl
import time
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def wait_for_task(task):
    while task.info.state in (vim.TaskInfo.State.running, vim.TaskInfo.State.queued):
        time.sleep(1)
    if task.info.state == vim.TaskInfo.State.error:
        raise task.info.error
    return task.info.result


def find_vm(content, name, datacenter=None):
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    try:
        matches = []
        for vm in view.view:
            if vm.name != name:
                continue
            if datacenter:
                parent = vm.parent
                dc_name = None
                while parent:
                    if isinstance(parent, vim.Datacenter):
                        dc_name = parent.name
                        break
                    parent = getattr(parent, 'parent', None)
                if dc_name != datacenter:
                    continue
            matches.append(vm)
        if not matches:
            raise RuntimeError(f"VM {name!r} not found" + (f" in datacenter {datacenter!r}" if datacenter else ""))
        if len(matches) > 1:
            raise RuntimeError(f"Multiple VMs named {name!r} found; pass --datacenter")
        return matches[0]
    finally:
        view.Destroy()


def existing_disks(vm):
    return [d for d in vm.config.hardware.device if isinstance(d, vim.vm.device.VirtualDisk)]


def find_scsi_controller(vm):
    controllers = [d for d in vm.config.hardware.device if isinstance(d, vim.vm.device.VirtualSCSIController)]
    # Prefer VMware paravirtual controller when present.
    for c in controllers:
        if isinstance(c, vim.vm.device.ParaVirtualSCSIController):
            return c
    if controllers:
        return controllers[0]
    raise RuntimeError("No SCSI controller found on VM")


def next_unit_number(vm, controller_key):
    used = set()
    for d in vm.config.hardware.device:
        if getattr(d, 'controllerKey', None) == controller_key and getattr(d, 'unitNumber', None) is not None:
            used.add(d.unitNumber)
    for unit in range(0, 16):
        if unit == 7:  # SCSI controller reserved ID
            continue
        if unit not in used:
            return unit
    raise RuntimeError("No free SCSI unit number available")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--datacenter', default=None)
    parser.add_argument('--vm', required=True)
    parser.add_argument('--datastore', required=True)
    parser.add_argument('--size-gb', type=int, required=True)
    parser.add_argument('--thin', action='store_true')
    parser.add_argument('--skip-if-size-exists', action='store_true')
    parser.add_argument('--insecure', action='store_true')
    args = parser.parse_args()

    context = ssl._create_unverified_context() if args.insecure else None
    si = SmartConnect(host=args.hostname, user=args.username, pwd=args.password, sslContext=context)
    atexit.register(Disconnect, si)
    content = si.RetrieveContent()
    vm = find_vm(content, args.vm, args.datacenter)

    target_kb = args.size_gb * 1024 * 1024
    for disk in existing_disks(vm):
        disk_gb = int(round(disk.capacityInKB / 1024 / 1024))
        if args.skip_if_size_exists and disk_gb == args.size_gb:
            print(f"VM {args.vm} already has a {args.size_gb}GB disk; no change")
            return 0

    controller = find_scsi_controller(vm)
    unit = next_unit_number(vm, controller.key)

    backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    backing.diskMode = 'persistent'
    backing.thinProvisioned = bool(args.thin)
    backing.fileName = f"[{args.datastore}]"

    disk = vim.vm.device.VirtualDisk()
    disk.key = -100
    disk.controllerKey = controller.key
    disk.unitNumber = unit
    disk.capacityInKB = target_kb
    disk.backing = backing

    spec = vim.vm.device.VirtualDeviceSpec()
    spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create
    spec.device = disk

    config = vim.vm.ConfigSpec()
    config.deviceChange = [spec]
    wait_for_task(vm.ReconfigVM_Task(config))
    print(f"Added {args.size_gb}GB {'thin' if args.thin else 'thick'} disk to {args.vm} on datastore {args.datastore} at SCSI unit {unit}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
