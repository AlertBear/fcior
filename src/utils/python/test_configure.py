#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import os
import time
import threading
import commands
import Ldom
import re


def execute(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        raise Exception("Execution of [%s] failed:\n%s" % (cmd, output))
    return output


def get_volume_of_domain(ldm):
    '''
    Purpose:
        Get the volume of a domain
    Arguments:
        ldm - Domain name
    Return:
        source_volume - Volume of the domain
    '''
    source_volume = []
    cmd_get_disk_num = "ldm list-bindings -p %s|grep VDISK|wc -l" % ldm
    disk_num_string = execute(cmd_get_disk_num)
    disk_num = int(disk_num_string.strip())
    if disk_num > 1:
        cmd_list_bindings = 'ldm list-bindings -p %s' % ldm
        bindings = execute(cmd_list_bindings)
        pattern = re.compile('VDISK.*')
        disk_bindings_list = pattern.findall(bindings)
        for disk_binding in disk_bindings_list:
            disk_volume = disk_binding.split("|")[2].split("@")[0]
            cmd_get_disk_service = "ldm list-services -p|grep {0}".format(
                disk_volume)
            all_vd_services = execute(cmd_get_disk_service)
            pattern = re.compile(r'{0}.*'.format(disk_volume))
            all_vdsdev_list = pattern.findall(all_vd_services)
            for vdsdev_info in all_vdsdev_list:
                vol = vdsdev_info.split("|")[0]
                match_vdsdev_volume = re.match(
                    r'^{0}$'.format(disk_volume),
                    vol)
                if match_vdsdev_volume is not None:
                    match_vdsdev_info = vdsdev_info
                    break
            source_volume.append(
                match_vdsdev_info.split("|")[2].lstrip("dev=/dev/zvol/dsk/"))
    else:
        cmd_get_disk_binding = "ldm list-bindings -p %s|grep VDISK" % ldm
        disk_binding = execute(cmd_get_disk_binding).strip()
        disk_volume = disk_binding.split("|")[2].split("@")[0]

        cmd_get_disk_service = "ldm list-services -p|grep {0}".format(
            disk_volume)
        all_vds_services = execute(cmd_get_disk_service)
        pattern = re.compile(r'{0}.*'.format(disk_volume))
        all_vdsdev_list = pattern.findall(all_vds_services)
        for vdsdev_info in all_vdsdev_list:
            vol = vdsdev_info.split("|")[0]
            match_vdsdev_volume = re.match(r'^{0}$'.format(disk_volume), vol)
            if match_vdsdev_volume is not None:
                match_vdsdev_info = vdsdev_info
                break
        source_volume.append(
            match_vdsdev_info.split("|")[2].lstrip("dev=/dev/zvol/dsk/"))
    return source_volume


def clone_from_source_domain(source_volume_snapshot, *target_list):
    '''
    Purpose:
        Create a domain by clone the volume
    Arguments:
        source_volume_snapshot - Snapshot of the volume
        target_list - Domains to create
    Return:
        None
    '''
    for target in target_list:
        target_domain_volume = 'rpool/{0}'.format(target)
        cmd_clone_from_source_volume = 'zfs clone {0} {1}'.format(
            source_volume_snapshot,
            target_domain_volume)
        execute(cmd_clone_from_source_volume)
        cmd_add_domain = 'ldm add-domain %s' % target
        cmd_add_vcpu = 'ldm add-vcpu 8 %s' % target
        cmd_add_memory = 'ldm add-memory 16G %s' % target

        cmd_get_vsw = "ldm list-services -p|grep VSW|awk -F'|' '{print $2}'"
        vsw = execute(cmd_get_vsw).split("=")[1]
        cmd_add_vnet = 'ldm add-vnet vnet_{0} {1} {2}'.format(
            target,
            vsw,
            target)

        cmd_get_vds = "ldm list-services -p|grep VDS|awk -F'|' '{print $2}'"
        vds = execute(cmd_get_vds).split("=")[1]
        cmd_add_vdsdev = 'ldm add-vdsdev /dev/zvol/dsk/{0} {1}@{2}'.format(
            target_domain_volume,
            target,
            vds)

        cmd_add_vdisk = 'ldm add-vdisk vdisk_{0} {1}@{2} {3}'.format(
            target,
            target,
            vds,
            target)
        cmd_set_auto_boot = 'ldm set-var auto-boot?=true {0}'.format(target)
        cmd_set_boot_device = 'ldm set-var boot-device=vdisk_{0} {1}'.format(
            target,
            target)
        cmd_bind_domain = 'ldm bind {0}'.format(target)
        cmd_create_domain_list = [
            cmd_add_domain,
            cmd_add_vcpu,
            cmd_add_memory,
            cmd_add_vnet,
            cmd_add_vdsdev,
            cmd_add_vdisk,
            cmd_set_auto_boot,
            cmd_set_boot_device,
            cmd_bind_domain]
        for cmd in cmd_create_domain_list:
            execute(cmd)
        time.sleep(1)


def get_pf_bus(pf):
    '''
    Purpose:
        Get the bus where pf affiliated
    Arguments:
        pf - port of the device
    Return:
        None
    '''
    pci_dev = pf[:-10]
    cmd_get_bus = "ldm list-io -l -p %s|grep 'type=PCIE'" % pci_dev
    try:
        output_get_bus = execute(cmd_get_bus)
    except Exception as e:
        raise Exception("No mapping PCIE device of %s in the system" % pf)
    bus = output_get_bus.split('|')[6].split('=')[1]
    return bus


def main():
    root_domain_1_name = os.getenv("NPRD_A")
    root_domain_2_name = os.getenv("NPRD_B")
    io_domain_name = os.getenv("IOD")
    password = os.getenv("SOURCE_DOMAIN_PASSWORD")
    pf_1 = os.getenv("PF_A")
    pf_2 = os.getenv("PF_B")
    domains_list = [root_domain_1_name, root_domain_2_name, io_domain_name]
    for domain in domains_list:
        cmd_ldm_list = "ldm list %s" % domain
        (status, output) = commands.getstatusoutput(cmd_ldm_list)
        if status == 0:
            print "%s already exists, abort to create root domains " \
                  "and io domain" % domain
            return 1

    source_domain_name = os.getenv("SOURCE_DOMAIN")
    cmd = 'ldm list %s' % source_domain_name
    try:
        execute(cmd)
    except Exception as e:
        print(e)
        return 1

    print("Begin clone domains from source domain %s" % source_domain_name)
    source_volume_list = get_volume_of_domain(source_domain_name)
    if len(source_volume_list) > 1:
        # User choose which volume to snapshot
        while True:
            user_choose_num = 0
            for source_volume in source_volume_list:
                print "[{0}]{1}".format(user_choose_num, source_volume)
                user_choose_num += 1
            snapshot_volume_input_flag = raw_input(
                "Which volume do you want to snapshot?")
            if snapshot_volume_input_flag == "":
                snapshot_volume_input_num = 0
            else:
                try:
                    snapshot_volume_input_num = int(snapshot_volume_input_flag)
                except Exception:
                    print "Please input a num above"
                else:
                    if not 0 <= snapshot_volume_input_num <= len(
                            source_volume_list):
                        print "Please input a num above"
                    else:
                        break
        source_volume = source_volume_list[snapshot_volume_input_num]
    else:
        source_volume = source_volume_list[0]

    #  Snapshot this volume to create new volume used by new domains
    now = time.strftime("%m%d%H%M")
    source_volume_snapshot = "{0}".format(source_volume) + "@ior-" + now
    cmd_snapshot = "zfs snapshot {0}".format(source_volume_snapshot)
    print "Creating snapshot of {0} as {1}".format(source_volume,
                                                   source_volume_snapshot)
    execute(cmd_snapshot)
    cmd_check_snapshot_success = 'zfs list -t snapshot|grep %s' % \
                                 source_volume_snapshot
    try:
        execute(cmd_check_snapshot_success)
    except Exception:
        print(
            "snapshot %s not as expected,cancel configuration" %
            source_volume)
    else:
        print "Done,remember to destroy the snapshot %s after all the test" % \
              source_volume_snapshot
    try:
        print "Creating domain %s..." % domains_list
        clone_from_source_domain(source_volume_snapshot, *domains_list)
    except Exception as e:
        print(e)
    else:
        print("Create %s success" % domains_list)
        time.sleep(5)

    domain_pf_dict = {root_domain_1_name: pf_1, root_domain_2_name: pf_2}
    for root_domain, pf in domain_pf_dict.items():
        try:
            bus = get_pf_bus(pf)
            cmd_add_bus = "ldm add-io iov=on %s %s" % (bus, root_domain)
            print "Allocating bus %s to domain %s" % (bus, root_domain)
            execute(cmd_add_bus)
        except Exception as e:
            print "Failed to allocate bus to %s due to:\n%s" % (root_domain, e)
            print "Test user should allocate pci bus to domain manually"
            return 1
        else:
            print "Done"

    print "Waiting created domains boot up..."
    for domain in domains_list:
        cmd_start = "ldm start %s" % domain
        execute(cmd_start)
    time.sleep(150)

    for domain in domains_list:
        cmd_list_domain = 'ldm list %s | grep %s' % (domain, domain)
        output_list_domain = execute(cmd_list_domain)

        domain_status = output_list_domain.split()[1].strip()
        if domain_status != 'active':
            print "%s is not up and could not login" % domain
            break
        cmd_check_hostname = 'hostname %s' % domain
        domain_port = output_list_domain.split()[3].strip()
        ldom = Ldom.Ldom(domain, password, domain_port, record=False)
        try:
            ldom.sendcmd(cmd_check_hostname, timeout=600)
        except Exception as e:
            print "%s is not up and not able to login due to:\n%s" % (domain, e)
        else:
            cmd_delete_ip = "ipadm delete-ip net0"
            ldom.sendcmd(cmd_delete_ip, check=False)
            cmd_disable_ldap = "svcadm disable svc:/network/ldap/client:default"
            ldom.sendcmd(cmd_disable_ldap, check=False)
            print "%s is up and able to test now" % domain

if __name__ == "__main__":
    main()
