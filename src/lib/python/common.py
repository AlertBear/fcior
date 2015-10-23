#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#


import os
import threading
import Ldom
import Host
import time
import re
import shutil
import tempfile
import xml.dom.minidom
from basic import *


def check_domain_exists(ldm):
    """
    Purpose:
        Check whether the domain exists
    Arguments:
        ldm - The domain name
    Return:
        None - Exception represents the domain does not exist
    """
    cmd = 'ldm list %s' % ldm
    try:
        execute(cmd)
    except ExecuteException:
        raise NoneException("%s doesn't exist" % ldm)


def check_io_domain_runmode(iod_name, iod_password):
    """
    Purpose:
        Check whether the io domain can run in current configuration
    Arguments:
        *iods - IO domain name
    Return:
        None
    """
    try:
        check_domain_exists(iod_name)
    except NoneException:
        raise Exception("%s doesn't exist on the system" % iod_name)

    if get_domain_status(iod_name) != "active":
        raise Exception(
            "%s is not active on the system, please ensure it to be active" %
            iod_name)
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)

    # Check whether MPxIO is enabled in IO domain
    # in S12, MPxIO is enabled and /etc/driver/drv/fp.conf not exists
    cmd_check_system = "uname -r"
    system_version = iod.retsend_one_line(cmd_check_system).strip()
    if system_version == "5.12":
        cmd = "test -f /etc/driver/drv/fp.conf"
        try:
            iod.sendcmd(cmd)
        except ExecuteException:
            return

    # Check and update "mpxio_disable=false" in Solaris11
    cmd = "sed -n '/^mpxio-disable=.*;$/p' /etc/driver/drv/fp.conf"
    output = iod.retsend_one_line(cmd)
    if re.search(r'no', output) is None:
        warn_report(
            "MPxIO is not enabled in IO domain [%s],trying to enabled" %
            iod_name)
        cmd1 = "sed '/^mpxio-disable=.*;$/s/yes/no/' /etc/driver/drv/fp.conf > " \
               "/etc/driver/drv/fp.conf.new"
        iod.sendcmd(cmd1)
        cmd2 = "rm /etc/driver/drv/fp.conf"
        iod.sendcmd(cmd2)
        cmd3 = "mv /etc/driver/drv/fp.conf.new /etc/driver/drv/fp.conf"
        iod.sendcmd(cmd3)
        time.sleep(3)
        iod.reboot()
        output = iod.retsend_one_line(cmd)
        if re.search('no', output) is None:
            raise Exception(
                "Failed to enabled MPxIO in io domain [%s]" % iod_name)


def check_root_domain_runmode(*root_domains):
    """
    Purpose:
        check whether the root domain can run in current configuration
    Arguments:
        root_domain_name - root domain name
    Return:
        None
    """
    for root_domain_name in root_domains:
        # Check whether root domain exists
        try:
            check_domain_exists(root_domain_name)
        except NoneException:
            raise Exception(
                "%s doesn't exist on the system" % root_domain_name)

        if get_domain_status(root_domain_name) != 'active':
            raise Exception(
                "%s is not active on the system, please ensure to be active" %
                root_domain_name)

        # Check whether root domain's failure-policy is ignore
        cmd = 'ldm list-bindings %s | grep failure-policy' % root_domain_name
        output = execute(cmd)
        policy = get_value_from_string(output.strip())
        if policy != 'ignore':
            warn_print("%s failure-policy is %s, setting to ignore"
                             % (root_domain_name, policy))
            cmd1 = 'ldm set-domain failure-policy=ignore %s' % root_domain_name
            try:
                execute(cmd1)
            except Exception:
                raise Exception
            else:
                info_print(
                    "Set failure-policy of %s to ignore success" %
                    root_domain_name)

        # Check whether a bus has been assigned to the root domain
        cmd = 'ldm list-io -p |grep domain=%s |grep BUS' % root_domain_name
        try:
            execute(cmd)
        except ExecuteException:
            raise Exception(
                "No pci bus has been assigned to %s" % root_domain_name)


def check_pf_support_ior(*pfs):
    """
    Purpose:
        Check whether PFs are fc device and support ior
    Arguments:
        pf_list - all the PFs provided
    Return:
        None
    """
    for pf in pfs:
        # Check whether the PF is a FC device port
        cmd = 'ldm list-io -l -p %s | grep type=PF' % pf
        pf_info = execute(cmd)
        pf_class = pf_info.split('|')[6].split('=')[1].strip()
        pf_dev = pf_info.split('|')[1].split('=')[1].strip()
        if pf_class != 'FIBRECHANNEL':
            raise Exception("%s is not a FC device port" % pf)
        else:
            if re.search('emlxs', pf_dev):
                pass
            elif re.search('qlc', pf_dev):
                pass
            else:
                raise Exception("%s does not support ior" % pf)

        # Check whether the PF belongs to any domain
        if len(pf_info.split('|')[4].split('=')) != 2:
            raise Exception("[%s] does not belong to any domain" % pf)


def check_pfs_domains_relation(ldom_pf_dict):
    """
    Purpose:
        Check whether PFs belongs to the root domains
    Arguments:
        ldom_pf_dict - root domains and PFs
    Return:
        None
    """
    for ldom, pf in ldom_pf_dict.items():
        cmd = 'ldm list-io -p %s|grep type=PF|grep %s' % (pf, ldom)
        try:
            execute(cmd)
        except ExecuteException:
            raise Exception("%s is not belong to %s" % (pf, ldom))

def list_all_vfs_on_pf(pf):
    """
    Purpose:
        List all vfs that pf has created
    Arguments:
        pf - PF name
    Return:
        vfs_list - All vfs that pf has created
    """
    cmd = 'ldm list-io | grep %s' % pf
    output = execute(cmd)
    pattern = re.compile(r'{0}\.VF\d+'.format(pf))
    match = pattern.findall(output)
    vfs_list = match
    return vfs_list


def check_whether_pf_has_created_vf(pf):
    """
    Purpose:
        Check whether the pf has created vf on it
    Arguments:
        pf - FC device PF
    Return:
        True - The pf has created vf
        False - The pf does not created any vf
    """
    vfs_list = list_all_vfs_on_pf(pf)
    if len(vfs_list) != 0:
        return True
    else:
        return False


def get_pf_another_port(pf):
    """
    Purpose:
        Get another port of fc device which
        pf is affiliated with
    Arguments:
        pf - pf name
    Return:
        result - Another port of fc device
    """
    pcie = pf.split('.')[0]
    cmd = "ldm list-io|grep %s|grep -v %s" % (pcie, pf)
    output = execute(cmd)
    result = output.split()[0]
    return result


def get_domain_status(domain):
    """
    Purpose:
        Get the current status of domain
    Arguments:
        domain - Ldom name
    Return:
        status - Current status of the domain
    """
    cmd = 'ldm list %s | grep %s' % (domain, domain)
    output = execute(cmd)
    status = output.split()[1].strip()
    return status


def get_domain_port(domain):
    """
    Purpose:
        Get the console port by using ldom name
    Arguments:
        domain - Ldom name
    Return:
        port - Port number
    """
    cmd = 'ldm list %s | grep %s' % (domain, domain)
    output = execute(cmd)
    if output is None:
        return None
    port = output.split()[3].strip()
    return port


def get_volume_of_domain(domain):
    """
    Purpose:
        Get the zfs volume of a domain which is created based on
        a zfs filesystem
    Arguments:
        domain - Domain name
    Return:
        source_volume - zfs filesystem e.g rpool/fc_nprd1
    """
    source_volume = []
    # Get the vdisk number, perhaps multiple vdisks in domain
    cmd_get_disk_num = "ldm list-bindings -p %s|grep VDISK|wc -l" % domain
    disk_num_string = execute(cmd_get_disk_num)
    disk_num = int(disk_num_string.strip())

    # VDISK number > 1, loop to get all the mapping zfs volumes
    if disk_num > 1:
        cmd_list_bindings = 'ldm list-bindings -p %s' % domain
        bindings = execute(cmd_list_bindings)
        pattern = re.compile(r'VDISK.*')
        disk_bindings_list = pattern.findall(bindings)
        for disk_binding in disk_bindings_list:
            disk_volume = disk_binding.split(
                "|")[2].split("@")[0]  # Get the volume
            cmd_get_disk_service = "ldm list-services -p|grep {0}".format(
                disk_volume)
            all_vd_services = execute(cmd_get_disk_service)
            pattern = re.compile(r'{0}.*'.format(disk_volume))
            all_vdsdev_list = pattern.findall(all_vd_services)
            for vdsdev_info in all_vdsdev_list:
                vol = vdsdev_info.split("|")[0]
                match_vdsdev_volume = re.match(
                    r'^{0}$'.format(disk_volume), vol)
                if match_vdsdev_volume is not None:
                    match_vdsdev_info = vdsdev_info
                    break
            source_volume.append(
                match_vdsdev_info.split("|")[2].lstrip("dev=/dev/zvol/dsk/"))
    else:
        cmd_get_disk_binding = "ldm list-bindings -p %s|grep VDISK" % domain
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


def snapshot_volume(source_volume):
    """
    Purpose:
        Snapsthot the zfs volume
    Arguments:
        source_volume - Source volume to snapshot
    Return:
        None
    """
    # Get current time to name the being created snapshot
    now = time.strftime("%m%d%H%M")
    source_volume_snapshot = "{0}".format(source_volume) + "@ior-" + now
    cmd_snapshot = "zfs snapshot {0}".format(source_volume_snapshot)
    execute(cmd_snapshot)

    # Check whether snapshot successfully
    cmd_check_snapshot_success = 'zfs list -t snapshot|grep %s' % \
                                 source_volume_snapshot
    try:
        execute(cmd_check_snapshot_success)
    except Exception:
        raise Exception(
            "Snapshot %s not as expected,cancel configuration" %
            source_volume)
    else:
        info_report(
            "Created snapshot of {0} as {1}".format(
                source_volume,
                source_volume_snapshot))
    return source_volume_snapshot


def create_domain_by_clone_snapshot(source_volume_snapshot, target):
    """
    Purpose:
        Create a domain by clone from a source domain
    Arguments:
        source_volume_snapshot - Source volume snapshot
        target - Target domain name
    Return:
        None
    """
    # Create the new zfs filesystem by clone from the source volume
    target_domain_volume = 'rpool/{0}'.format(target)
    cmd_clone_from_source_volume = 'zfs clone {0} {1}'.format(
        source_volume_snapshot,
        target_domain_volume)
    execute(cmd_clone_from_source_volume)

    # Add domain and allocate cpu/memory to new domain
    cmd_add_domain = 'ldm add-domain %s' % target
    cmd_add_vcpu = 'ldm add-vcpu 8 %s' % target
    cmd_add_memory = 'ldm add-memory 16G %s' % target

    # Add vnet to domain
    cmd_get_vsw = "ldm list-services -p|grep VSW|awk -F'|' '{print $2}'"
    vsw = execute(cmd_get_vsw).split("=")[1]
    cmd_add_vnet = 'ldm add-vnet vnet_{0} {1} {2}'.format(target, vsw, target)

    # Add vdisk to domain
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

    # Set auto-boot value to True and boot-device to new vdisk
    cmd_set_auto_boot = 'ldm set-var auto-boot?=true {0}'.format(target)
    cmd_set_boot_device = 'ldm set-var boot-device=vdisk_{0} {1}'.format(
        target,
        target)

    # Bound and start domain
    cmd_bind_domain = 'ldm bind {0}'.format(target)
    cmd_start_domain = 'ldm start {0}'.format(target)
    cmd_create_domain_list = [
        cmd_add_domain,
        cmd_add_vcpu,
        cmd_add_memory,
        cmd_add_vnet,
        cmd_add_vdsdev,
        cmd_add_vdisk,
        cmd_set_auto_boot,
        cmd_set_boot_device,
        cmd_bind_domain,
        cmd_start_domain]
    for cmd in cmd_create_domain_list:
        execute(cmd)


def create_domain(source_domain, *target_domains):
    """
    Purpose:
        Create a domain by clone from a source domain
    Arguments:
        source_domain - Source domain
        target_domains - Target domains name
    Return:
        None
    """
    source_volume_list = get_volume_of_domain(source_domain)
    if len(source_volume_list) > 1:
        pass
    else:
        source_volume_snapshot = snapshot_volume(source_volume_list[0])
        for target in target_domains:
            create_domain_by_clone_snapshot(source_volume_snapshot, target)


def destroy_domain(*domains):
    """
    Purpose:
        Destroy the domain
    Arguments:
        domains - Domains name
    Return:
        None
    """
    for ldom in domains:
        # Check the domain being destroyed whether exists
        try:
            check_domain_exists(ldom)
        except Exception:
            raise NoneException("%s does not exist" % ldom)

        # Stop and unbind the domain
        cmd_stop = 'ldm stop -f %s' % ldom
        cmd_unbind = 'ldm unbind %s' % ldom

        # Remove cpu/memory/vnet/vdisk from domain
        cmd_remove_vcpu = 'ldm remove-vcpu 8 %s' % ldom
        cmd_remove_memory = 'ldm remove-memory 16G %s' % ldom
        cmd_remove_vnet = 'ldm remove-vnet vnet_{0} {1}'.format(ldom, ldom)
        cmd_remove_vdisk = 'ldm remove-vdisk vdisk_{0} {1}'.format(ldom, ldom)

        # Remove the vdsdev
        cmd_remove_vdsdev = 'ldm remove-vdsdev {0}@p-vds0'.format(ldom)

        # Destroy domain and the mapping zfs filesystem
        cmd_destroy = 'ldm destroy %s' % ldom
        cmd_destroy_volume = 'zfs destroy rpool/{0}'.format(ldom)
        cmd_destroy_domain_list = [
            cmd_stop,
            cmd_unbind,
            cmd_remove_vcpu,
            cmd_remove_memory,
            cmd_remove_vnet,
            cmd_remove_vdisk,
            cmd_remove_vdsdev,
            cmd_destroy,
            cmd_destroy_volume]
        for cmd in cmd_destroy_domain_list:
            execute(cmd)


def destroy_snapshot_of_domain(ldm):
    """
    Purpose:
        Destroy the snapshot of a domain
    Arguments:
        ldm - Domain name
    Return:
        None
    """
    snapshot_list = []
    ldm_volume_list = get_volume_of_domain(ldm)
    # Get all the snapshot of the zfs filesystems which be bound to the domain
    for ldm_volume in ldm_volume_list:
        cmd_snapshot_list_of_this_volume = "zfs list -t snapshot | " \
                                           "grep %s|awk '{print $1}'" % ldm_volume
        result = execute(cmd_snapshot_list_of_this_volume)
        if result is None:
            pass
        else:
            pattern = re.compile(r'{0}.*'.format(ldm_volume))
            snapshot_list_of_one_volume = pattern.findall(result)
            for one_snapshot in snapshot_list_of_one_volume:
                snapshot_list.append(one_snapshot)
    # Destroy the snapshot
    if len(snapshot_list) == 0:
        pass
    else:
        for snapshot in snapshot_list:
            cmd_destroy_snapshot = 'zfs destroy %s' % snapshot
            execute(cmd_destroy_snapshot)


def check_domain_boot_up(name, password):
    """
    Purpose:
        Check the domain whether boot up and could login
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    # Check domain status
    status = get_domain_status(name)
    if status != 'active':
        raise Exception("%s is not up and colud not login" % name)

    # If domain is up, hostname domain will successfully
    cmd_check_hostname = 'hostname %s' % name
    port = get_domain_port(name)
    ldom = Ldom.Ldom(name, password, port)
    try:
        ldom.sendcmd(cmd_check_hostname, timeout=600)
    except Exception as e:
        raise Exception(
            "%s is not up and not able to login due to:\n%s" % (name, e))


def remove_vf_from_domain(vf, domain):
    """
    Purpose:
        Remove vf from ldom
    Arguments:
        vf - The specified vf to remove
        domain - The specified domain to remove from
    Return:
        None
    """
    cmd = 'ldm rm-io %s %s' % (vf, domain)
    execute(cmd)


def destroy_all_vfs_on_pf(pf):
    """
    Purpose:
        Destroy all the vfs that pf has created
    Arguments:
        pf - The specified pf where to destroy vfs
    Return:
        None
    """
    vfs_list = list_all_vfs_on_pf(pf)
    for vf in vfs_list:
        cmd = 'ldm list-io -l -p %s|grep %s' % (pf, vf)
        output = execute(cmd)
        # The vf has been bound to a domain,need to be removed
        domain = output.split('|')[4].split('=')[1]
        if domain != '':
            remove_vf_from_domain(vf, domain)
            time.sleep(5)

    # Destroy all the vfs created under the pf
    cmd_destroy = 'ldm destroy-vf -n max %s' % pf
    execute(cmd_destroy)


def create_vf_in_dynamic_mode(pf):
    """
    Purpose:
        Create vf in dynamic mode
    Arguments:
        pf - Create vf on this pf
    Return:
        vf - The newly created vf
    """
    cmd = 'ldm create-vf %s' % pf
    output = execute(cmd)
    vf = output.split(':')[1].strip()
    return vf


def create_vf_in_manual_mode(pf, port_wwn, node_wwn):
    """
    Purpose:
        Create vf in manual mode:assign port-wwn & node-wwn manually
    Arguments:
        pf - Create vf on this pf
        port_wwn - Assign the specified wwn to the creating vf
        node_wwn - Assign the specified wwn to the creating vf
    Return:
        vf - The newly created vf
    """
    cmd = 'ldm create-vf port-wwn=%s node-wwn=%s %s' % (port_wwn, node_wwn, pf)
    output = execute(cmd)
    vf = output.split(':')[1].strip()
    return vf


def assign_vf_to_domain(vf, domain):
    """
    Purpose:
        Assign vf to the domain
    Arguments:
        vf - VF to allocated
        domain - The domain that assigned to
    Return:
        None
    """
    cmd = 'ldm list-io -p | grep %s' % vf
    output = execute(cmd)
    # The vf has been bound to a domain,need to be removed
    bound_domain = output.split('|')[4].split('=')[1]
    if bound_domain:
        remove_vf_from_domain(vf, bound_domain)

    cmd = 'ldm add-io %s %s' % (vf, domain)
    execute(cmd)


def destroy_vf(vf):
    """
    Purpose:
        Destroy the vf
    Arguments:
        vf - VF to destroyed
    Return:
        None
    """
    cmd = 'ldm destroy-vf %s' % vf
    execute(cmd)


def reboot_domain(name, password):
    """
    Purpose:
        Reboot domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    domain.reboot()


def stop_reboot_domain(domain):
    """
    Purpose:
        Reboot domain
    Arguments:
        domain - Domain name
    Return:
        None
    """
    cmd = "ldm stop -r %s" % domain
    execute(cmd)


def offline_vf_in_domain(name, password, vf):
    """
    Purpose:
        Hotplug offline the vf
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - VF being offline
    Return:
        None
    """
    port = get_domain_port(name)
    iod = Ldom.Ldom(name, password, port)
    iod.offline_vf(vf)


def check_vdbench_exists(iod_name, iod_password):
    """
    Purpose:
        Check the vdbench file whether exists in io domain
    Arguments:
        iod_name - io domain name
        iod_password - io domain password
    Return:
        True - exists
        False - not exists
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    vdbench_path = "/export/home/vdbench"
    cmd = 'test -d %s' % vdbench_path
    iod.sendcmd(cmd)


def check_io_workload_exists(iod_name, iod_password):
    """
    Purpose:
        Check the io workload file whether exists in io domain
    Arguments:
        iod_name - io domain name
        iod_password - io domain password
    Return:
        True - exists
        False - not exists
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    cmd = 'test -f run_io.sh'
    try:
        iod.retsend(cmd)
    except Exception:
        return False
    else:
        return True


def check_domain_pingable(name, password):
    """
    Purpose:
        Check the domain whether be pinable from primary domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    cmd_show_ip = 'ipadm show-addr|grep net0/v4'
    output_show_ip = execute(cmd_show_ip)
    primary_ip = output_show_ip.split()[3].split("/")[0]
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd_ping = "ping %s" % primary_ip
    try:
        domain.sendcmd(cmd_ping)
    except ExecuteException as e:
        return False
    else:
        return True


def distribute_io_workload_files_to_domain(iod_name, iod_password):
    """
    Purpose:
        Distribute the I/O workload files to the domain
    Arguments:
        iod_name - IO domain name
        iod_password - IO domain password
    Return:
        None
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    s1 = '"while(true)"'
    s2 = '"do"'
    s3 = '"mkfile 500m /ior_pool/fs/fcior_test"'
    s4 = '"sleep 1"'
    s5 = '"mv /ior_pool/fs/fcior_test /export/home/"'
    s6 = '"sleep 1"'
    s7 = '"rm -f /ior_pool/fs/fcior_test"'
    s8 = '"sleep 1"'
    s9 = '"mv /export/home/fcior_test /ior_pool/fs/"'
    s10 = '"sleep 1"'
    s11 = '"rm -f /ior_pool/fs/fcior_test"'
    s12 = '"sleep 1"'
    s13 = '"done"'
    cmd = "touch run_io.sh"
    iod.sendcmd(cmd)
    s_list = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13]
    for s in s_list:
        cmd1 = 'echo %s >> run_io.sh' % s
        iod.sendcmd(cmd1)
    cmd2 = 'chmod +x run_io.sh'
    iod.sendcmd(cmd2)


def run_io_workload_on_vf_in_domain(iod_name, iod_password, vf):
    """
    Purpose:
        Run io workload on the vf in io domain
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        vf - VF where io workload run
    Return:
        None
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    iod.run_io_workload_on_vf(vf)


def run_vdbench_on_vf_in_domain(iod_name, iod_password, vf):
    """
    Purpose:
        Run io workload on the vf in io domain
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        vf - VF where io workload run
    Return:
        None
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    iod.run_vdbench_on_vf(vf)


def get_vf_port_wwn(vf):
    """
    Purpose:
        Get the vf mapping port_wwn from primary domain
    Arguments:
        vf - VF name
        e.g./SYS/MB/PCIE2/IOVFC.PF1.VF15
    Return:
        port_wwn
    """
    vf_format = vf.replace("/", "\/")
    cmd = 'ldm list-io -l | sed -n "/{0} /="'.format(vf_format)
    vf_line_num = execute(cmd)
    port_wwn_line_num = int(vf_line_num) + 3
    cmd1 = 'ldm list-io -l | sed -n "{0}p"'.format(port_wwn_line_num)
    output1 = execute(cmd1)
    port_wwn = get_value_from_string(output1).replace(':', '').strip()
    return port_wwn


def get_pf_maxvf_number(pf):
    """
    Purpose:
        Get the maxvf number of the pf
    Arguments:
        pf - PF name
        e.g./SYS/MB/PCIE2/IOVFC.PF1
    Return:
        number
    """
    cmd = "ldm list-io -l -p %s|grep maxvfs" % pf
    output = execute(cmd)
    number = output.split('|')[2].split('=')[1]
    return number


def get_vf_belong_to_which_root_domain(vf):
    """
    Purpose:
        Get the root domain that the vf belonged to
    Arguments:
        vf - VF name
    Return:
        nprd - root domain
    """
    cmd = 'ldm list-io | grep %s' % vf
    output = execute(cmd)
    if output is None:
        return None
    pci_bus = output.split()[2]
    cmd1 = 'ldm list-io | grep %s | grep BUS' % pci_bus
    output1 = execute(cmd1)
    nprd = output1.split()[3]
    return nprd


def get_pf_class(pf):
    """
    Purpose:
        Get the class of pf
    Arguments:
        pf - PF name
    Return:
        pf_class - e.g FIBRECHANNE/INFINIBAND/NETWORK
    """
    cmd = "ldm list-io -l -p %s|grep class" % pf
    output = execute(cmd)
    pf_class = get_value_from_string(output.split('|')[6])
    return pf_class


def get_vf_class(vf):
    """
    Purpose:
        Get the class of vf
    Arguments:
        vf - PF name
    Return:
        pf_class - e.g FIBRECHANNE/INFINIBAND/NETWORK
    """
    cmd = "ldm list-io -l -p|grep %s" % vf
    output = execute(cmd)
    vf_class = get_value_from_string(output.split('|')[6])
    return vf_class


def get_vf_hotplug_dev(vf):
    """
    Purpose:
        Get the hotplug dev info of vf
    Arguments:
        vf - VF name
    Return:
        hotplug_dev - e.g /pci@380/pci@1/pci@0/pci@5/SUNW,qlc@0,14
    """
    # Get through "ldm list-io -p"
    cmd_list_io = 'ldm list-io -p | grep %s' % vf
    output_list_io = execute(cmd_list_io)
    # output instance:
    # |dev=pci@700/pci@1/pci@0/pci@4/SUNW,emlxs@0
    # |alias=/SYS/PCI-EM14/IOVFC.PF0|status=|domain=fc-nprd3
    # |type=PF|bus=pci_3
    # Split to get the second element of the output
    hotplug_dev = output_list_io.split("|")[1].strip()
    # Split to get the second element
    hotplug_dev = hotplug_dev.split('=')[1].strip()
    hotplug_dev = '/' + hotplug_dev  # Add '/' to the header
    return hotplug_dev

def get_vf_hotplug_path(vf):
    """
    Purpose:
        Get the hotplug path of vf
    Arguments:
        vf - VF name
    Return:
        hotplug_path - e.g /pci@380/pci@1/pci@0/pci@5
    """
    # Get the hotplug dev of vf
    hotplug_dev = get_vf_hotplug_dev(vf)

    strip_char = '/' + hotplug_dev.split('/')[-1]
    hotplug_path = hotplug_dev.rstrip(strip_char)
    return hotplug_path


def get_vf_hotplug_port(vf):
    """
    Purpose:
        Get the hotplug port of vf
    Arguments:
        vf - VF name
    Return:
        hotplug_path - e.g pci.0,2
    """
    # Get the hotplug dev of vf
    hotplug_dev = get_vf_hotplug_dev(vf)

    port = hotplug_dev.split('@')[-1]
    hotplug_port = 'pci.' + port
    return hotplug_port


def get_nic_vf_mac(vf):
    """
    Purpose:
        Get the mac address of nic vf
    Arguments:
        vf - Nic vf
    Return:
        mac - MAC address
    """
    vf_str = vf.replace('/', '\/')
    pf = vf.split('.')[0] + '.' + vf.split('.')[1]
    cmd = "ldm list-io -l -p {0}|sed -n '/{1}/='".format(
        pf,
        vf_str)
    alias_line_num = int(execute(cmd))
    mac_line_num = alias_line_num + 1
    cmd = "ldm list-io -l -p {0}|sed -n '{1}p'".format(
        pf,
        mac_line_num)
    mac_line = execute(cmd)
    mac_addr = get_value_from_string(mac_line.split('|')[2])

    # Remove redundant "0"
    join_str = ":"
    items = []
    for item in mac_addr.split(':'):
        if item[0] == '0':
            item = item[1]
        items.append(item)

    valid_mac_addr = join_str.join(items)
    return valid_mac_addr


def get_nic_vf_interface_in_domain(name, password, vf):
    """
    Purpose:
        Get the interface of the vf in domain
    Arguments:
        name - Domain name
        password - Domain password
        vf - Nic vf
    Return:
        interface - Network interface
    """
    # Get the mac address of vf
    mac_addr = get_nic_vf_mac(vf)

    # Build domain by name and password
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the interface in domain
    cmd = "dladm show-phys -m -o LINK,ADDRESS|grep %s" % mac_addr
    output = domain.retsend(cmd)
    interface = output.split()[0]
    return interface


def get_nic_pf_interface_in_domain(name, password, pf):
    """
    Purpose:
        Get the mapping interface of nic pf in root domain
    Arguments:
        name - Root domain where the pf resides
        password - Root domain password
        pf - Get the interface from this pf
    Return:
        interface - Network interface
    """
    # Get pf hotplug_dev
    cmd = "ldm list-io -p %s|grep type=PF" % pf
    output = execute(cmd)
    hotplug_dev = '/' + get_value_from_string(output.split('|')[1])

    # Get the device from /etc/path_to_inst
    cmd = "grep '{0}' /etc/path_to_inst|head -1".format(hotplug_dev)
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    output = domain.retsend(cmd)
    device = output.split()[2].strip('"') + output.split()[1]

    # Get the interface
    cmd = "dladm show-phys -po link,device|grep %s" % device
    output = domain.retsend_one_line(cmd)
    interface = output.split(':')[0]

    return interface


def get_remote_nic_pf_interface(hostname, password, pf):
    """
    Purpose:
        Get the mapping interface of pf in remote host
    Arguments:
        name - Remote hostname
        password - Remote password
        pf - Get the interface from this pf
    Return:
        interface - Network interface
    """
    # Build a Host
    rmt_host = Host.Host(hostname, password)

    # Get pf hotplug_dev
    cmd = "ldm list-io -p %s|grep type=PF" % pf
    output = rmt_host.return_command(cmd)
    hotplug_dev = '/' + get_value_from_string(output.split('|')[1])

    # Get the device from /etc/path_to_inst
    cmd = "grep \"{0}\" /etc/path_to_inst".format(hotplug_dev)
    output = rmt_host.return_command(cmd)
    device = output.split()[2].strip('"') + output.split()[1]

    # Get the interface
    cmd = "dladm show-phys -po link,device|grep %s" % device
    output = rmt_host.return_command(cmd)
    interface = output.split(':')[0]

    return interface


def destroy_all_nic_vfs_on_pf(name, password, pf):
    """
    Purpose:
        Destroy all vfs created on the nic pf
    Arguments:
        name - IO Domain name
        password - IO Domain password
        pf - PF name
    Return:
        None
    """
    vfs_list = list_all_vfs_on_pf(pf)
    for vf in vfs_list:
        cmd = 'ldm list-io -l -p %s|grep %s' % (pf, vf)
        output = execute(cmd)
        # The vf has been bound to a domain,need to be removed
        domain = output.split('|')[4].split('=')[1]
        if domain != '':
            try:
                remove_vf_from_domain(vf, domain)
            except ExecuteException:
                if domain == name:
                    port = get_domain_port(domain)
                    iod = Ldom.Ldom(name, password, port)
                    interface = get_nic_vf_interface_in_domain(
                        name,
                        password,
                        vf)
                    cmd = "ipadm delete-ip %s" % interface
                    iod.sendcmd(cmd)
                    remove_vf_from_domain(vf, domain)
                else:
                    raise Exception("%s does is bound to %s "
                                    "and can not be removed" %
                                    (vf, domain))
            time.sleep(5)

    # Destroy all the vfs created under the pf
    cmd = 'ldm destroy-vf -n max %s' % pf
    execute(cmd)


def delete_int_vnic_over_pf_in_domain(name, password, pf):
    """
    Purpose:
        Delete the mapping interface of pf and vnic
        on this interface
    Arguments:
        name - Root domain where the pf resides
        password - Root domain password
        pf - Delete vnic and interface on this pf
    Return:
        None
    """
    port = get_domain_port(name)
    interface = get_nic_pf_interface_in_domain(
        name,
        password,
        pf)
    domain = Ldom.Ldom(name, password, port)

    # Check whether the interface up on in domain,
    # if yes, destroyed
    cmd = "ifconfig %s" % interface
    try:
        domain.sendcmd(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ipadm delete-ip %s" % interface
        domain.sendcmd(cmd)

    # Get the vnics over interface
    cmd = "dladm show-vnic -p -o link,over -l %s" % interface
    output = domain.retsend(cmd)
    vnics_over_int = re.findall(r'.*:{0}'.format(interface),
                                output)
    if vnics_over_int:
        for vnic in vnics_over_int:
            cmd = "dladm delete-vnic %s" % vnic
            domain.sendcmd(cmd)


def create_nic_vf(name, password, pf):
    """
    Purpose:
        Create NIC vf on pf
    Arguments:
        name - Root domain where the pf resides
        password - Root domain password
        pf - Create vf on this pf
    Return:
        vf - The newly created vf
    """
    cmd = 'ldm create-vf %s' % pf
    try:
        output = execute(cmd)
    except ExecuteException:
        delete_int_vnic_over_pf_in_domain(name, password, pf)
    else:
        vf = output.split(':')[1].strip()
        return vf


def check_remote_pingable_from_root_domain(
        name,
        password,
        ip,
        retry_count=3):
    """
    Purpose:
        Check the remote interface is pingable from
        root domain
    Arguments:
        name - Root domain name
        password - Root domain password
        ip - Remote nic interface ip address
        retry_count - Retry count
    Return:
        None
    """
    i = 0
    cmd = "ping %s" % ip
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    while True:
        if i >= retry_count:
            raise Exception("Remote ip %s is not "
                            "pingable from %s" % (ip, name))
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            break
        time.sleep(2)
        i += 1


def check_nic_pf_be_connected(rmt_host_dict, root_dict):
    """
    Purpose:
        Check the remote nic port has been connected
        to switch, thus, can be pingable from root domain
    Arguments:
        rmt_host_dict - Including remote host name, password, net link
        root_dict - Including root domain name, password, nic pf
    Return:
        None
    """
    # Build host
    rmt_name = rmt_host_dict.keys()[0]
    rmt_password = rmt_host_dict[rmt_name]['password']
    rmt_int = rmt_host_dict[rmt_name]['link']
    rmt_host = Host.Host(rmt_name, rmt_password)

    # Create vnic on remote interface
    # First delete the vnic if exist
    rmt_vnic = 'ior_chkvnic0'
    cmd = "ifconfig %s" % rmt_vnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd_unplumb = "ifconfig %s unplumb" % rmt_vnic
        rmt_host.send_command(cmd_unplumb)

    cmd = "dladm show-vnic %s" % rmt_vnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "dladm delete-vnic %s" % rmt_vnic
        rmt_host.send_command(cmd)
    # Second, create the vnic
    cmd = "dladm create-vnic -l %s %s" % (rmt_int, rmt_vnic)
    rmt_host.send_command(cmd)
    rmt_ip = "11.11.1.2"
    cmd = "ifconfig %s plumb %s/24 up" % (rmt_vnic, rmt_ip)
    rmt_host.send_command(cmd)

    for name, root_info in root_dict.items():
        password = root_info['password']
        pf = root_info['pf']
        port = get_domain_port(name)
        domain = Ldom.Ldom(name, password, port)
        interface = get_nic_pf_interface_in_domain(
            name,
            password,
            pf)
        # Create ip for int in root domain and ping remote vnic
        # First delete the vnic if exists
        vnic = 'ior_chkvnic0'
        cmd = "ifconfig %s" % vnic
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            cmd_unplumb = "ifconfig %s unplumb" % vnic
            domain.sendcmd(cmd_unplumb)
        cmd = "dladm show-vnic %s" % vnic
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            cmd = "dladm delete-vnic %s" % vnic
            domain.sendcmd(cmd)

        # Second, create the vnic
        cmd = "dladm create-vnic -l %s %s" % (interface, vnic)
        domain.sendcmd(cmd)
        ip = "11.11.1.1"
        cmd = "ifconfig %s plumb %s/24 up" % (vnic, ip)
        domain.sendcmd(cmd)

        # Ping remote vnic from root domain
        check_remote_pingable_from_root_domain(
            name,
            password,
            rmt_ip)

        # Delete the vnic
        cmd_unplumb = "ifconfig %s unplumb" % vnic
        domain.sendcmd(cmd_unplumb)
        cmd = "dladm delete-vnic %s" % vnic
        domain.sendcmd(cmd)

    # Delete the remote vnic
    cmd_unplumb = "ifconfig %s unplumb" % rmt_vnic
    rmt_host.send_command(cmd_unplumb)
    cmd = "dladm delete-vnic %s" % rmt_vnic
    rmt_host.send_command(cmd)


def get_ipmp_state_in_domain(name, password, ipmp):
    """
    Purpose:
        Get the state of the ipmp group in domain
    Arguments:
        name - Domain name
        password - Domain password
        ipmp - IPMP to be checked
    Return:
        None
    """
    # Build domain
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the ipmp state in domain
    cmd = "ipmpstat -o GROUP,STATE -P -g|grep %s" % ipmp
    output = domain.retsend(cmd)
    state = output.split(':')[1].strip()
    return state


def configure_nic_ip_in_remote(hostname, password, interface, ip):
    """
    Purpose:
        Create ip address for the interface in remote host
    Arguments:
        name - Domain name
        password - Domain password
        int - NIC interface to be configured
        ip - The interface will be configured to this ip address
    Return:
        None
    """
    # Build a Host
    rmt_host = Host.Host(hostname, password)

    # Check whether $vnic exists, if yes, unplumb
    vnic = 'ior_vnic0'
    cmd = "ifconfig %s" % vnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd_unplumb = "ifconfig %s unplumb" % vnic
        rmt_host.send_command(cmd_unplumb)

    # Delete the existing vnic
    cmd = "dladm delete-vnic %s" % vnic
    rmt_host.send_command(cmd, check=False)

    # Create vnic and configure ip address
    cmd = "dladm create-vnic -l %s %s" % (interface, vnic)
    rmt_host.send_command(cmd)
    cmd = "ifconfig %s plumb %s/24 up" % (vnic, ip)
    rmt_host.send_command(cmd)


def configure_nic_vfs_ipmp_in_domain(
        name,
        password,
        ipmp,
        vf1,
        vf2,
        ip):
    """
    Purpose:
        Create ipmp group for the test interfaces in the IO domain,
        configure IP for the ipmp group and the remote interface
    Arguments:
        name - Domain name
        password - Domain password
        ipmp - IPMP group name
        vf1 - NIC vf 1 in io domain
        vf2 - NIC vf 2 in io domain
        ip - IP address which will be used
    Return:
        None
    """
    # Build domain by name, password, port
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Check ipmp whether exist, if yes, unconfigure it.
    cmd = "ipmpstat -o GROUP -P -g"
    output = domain.retsend(cmd)
    if re.search(ipmp, output):
        unconfigure_nic_ipmp_in_domain(name, password, ipmp)

    # Create IPMP
    int1 = get_nic_vf_interface_in_domain(name, password, vf1)
    int2 = get_nic_vf_interface_in_domain(name, password, vf2)
    try:
        cmd = "ifconfig %s" % int1
        domain.sendcmd(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ipadm delete-ip %s" % int1
        domain.sendcmd(cmd)
    cmd = "ipadm create-ip %s" % int1
    domain.sendcmd(cmd)

    try:
        cmd = "ifconfig %s" % int2
        domain.sendcmd(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ipadm delete-ip %s" % int2
        domain.sendcmd(cmd)
    cmd = "ipadm create-ip %s" % int2
    domain.sendcmd(cmd)

    cmd = "ipadm create-ipmp %s" % ipmp
    domain.sendcmd(cmd)
    cmd = "ipadm add-ipmp -i %s -i %s %s" % (int1, int2, ipmp)
    domain.sendcmd(cmd)

    # Create address for IPMP
    cmd = "ipadm create-addr -T static -a {0}/24 {1}/v4addr1".format(
        ip, ipmp)
    domain.sendcmd(cmd)

    # Check the ipmp group state, should be ok
    state = get_ipmp_state_in_domain(name, password, ipmp)
    if state != 'ok':
        raise Exception("The state of %s is not ok, "
                        "please make sure the test interfaces are "
                        "connected to a switch" % ipmp)

def unconfigure_nic_ipmp_in_domain(name, password, ipmp):
    """
    Purpose:
        Delete ipmp group for the test interfaces in the IO domain
    Arguments:
        name - Domain name
        password - Domain password
        ipmp - IPMP group name
    Return:
        None
    """
    # Build domain
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the interface in IPMP group
    cmd = "ipmpstat -i -o INTERFACE,GROUP|grep %s|awk '{print $1}'" % \
          ipmp
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        cmd = "ipadm delete-ipmp %s" % ipmp
        domain.sendcmd(cmd)
    else:
        match = output.split()

        # Delete ipmp group
        for interface in match:
            cmd = "ipadm remove-ipmp -i %s %s" % (interface, ipmp)
            domain.sendcmd(cmd)
            cmd = "ipadm delete-ip %s" % interface
            domain.sendcmd(cmd)

        cmd = "ipadm delete-ipmp %s" % ipmp
        domain.sendcmd(cmd)


def check_remote_pingable_from_io_domain(
        name,
        password,
        rmt_ip,
        retry=2):
    """
    Purpose:
        Delete ipmp group for the test interfaces in the IO domain
    Arguments:
        name - IO domain name
        password - IO domain password
        rmt_ip - Remote ip address
        retry - retry count
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = "ping %s" % rmt_ip
    i = 0
    while True:
        if i >= retry:
            raise Exception("Remote ip %s is not pingable from %s" %
                            (rmt_ip, name))
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            break


def check_nic_vf_under_ipmp(name, password, vf):
    """
    Purpose:
        Check the corresponding interface of
        nic vf is under ipmp group in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - NIC vf name
    Return:
        True - Under IPMP group
        False - Not under IPMP group
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the mapping interface of the nic vf
    interface = get_nic_vf_interface_in_domain(name, password, vf)
    hotplug_dev = get_vf_hotplug_dev(vf)
    cmd = "ipadm |grep %s" % interface
    output = domain.retsend(cmd)
    if output.split()[3] != '--':
        ipmp_group = output.split()[3]
        cmd = "ipmpstat -i|grep %s|grep -v %s" % (
            ipmp_group,
            interface)
        output = domain.retsend(cmd)
        if output:
            another_int_under_ipmp = output.split()[0]
            cmd = "dladm show-phys -p -o LINK,DEVICE|grep %s" \
                  % another_int_under_ipmp
            output = domain.retsend(cmd)
            another_int_device = output.split(':')[1]
            another_int_driver = filter(
                str.isalpha,
                another_int_device)
            another_int_num = filter(
                str.isdigit,
                another_int_device)
            cmd = "cat /etc/path_to_inst|grep %s|grep %s" % (
                another_int_driver,
                another_int_num)
            output = domain.retsend(cmd)
            another_int_hotplug_dev = output.split()[0].strip('"')
            pci_bus_path = another_int_hotplug_dev.split('/')[1]
            if pci_bus_path != hotplug_dev.split('/')[1]:
                return True
            else:
                return False
        else:
            return False
    else:
        return False


def get_nic_vf_ipmp_group(name, password, vf):
    """
    Purpose:
        Get the ipmp group where the mapping interface of nic vf
        resides in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - NIC vf name
    Return:
        ipmp_group - IPMP group
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the mapping interface of the nic vf
    interface = get_nic_vf_interface_in_domain(name, password, vf)
    cmd = "ipadm |grep %s" % interface
    output = domain.retsend(cmd)
    ipmp_group = None
    if output.split()[3] != '--':
        ipmp_group = output.split()[3]
    return ipmp_group


def check_nic_ib_traffic_state_on_int_in_domain(
        name,
        password,
        interface,
        rmt_ip=None):
    """
    Purpose:
        Check whether the ipmp group still has
        ping traffic in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        interface - Network interface or ipmp group
        rmt_ip - Remote ip address
    Return:
        True or False
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Create a temp file
    cmd = "mktemp"
    tmpfile = domain.retsend(cmd)

    # Use snoop to test the io traffic on interface
    if rmt_ip:
        cmd = "timeout 10 snoop -I %s -c 10 -o %s %s" % (
            interface,
            tmpfile,
            rmt_ip)
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            return False
    else:
        cmd = "timeout 10 snoop -I %s -c 15 -o %s" % (
            interface,
            tmpfile)
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            return False

    # Check from the temp file where record the data
    cmd = "snoop -i %s|grep ICMP" % tmpfile
    try:
        domain.sendcmd(cmd)
    except ExecuteException:
        return False
    else:
        return True


def get_interface_by_ip(name, password, ip):
    """
    Purpose:
        Get the interface which has the given ip in domain
    Arguments:
        name - IO domain name
        password - IO domain password
        ip - IP address
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the interface which has the ip address
    cmd = "ipadm show-addr | grep %s" % ip
    output = domain.retsend(cmd)
    interface = output.split()[0].split('/')[0]

    return interface

def run_ping_traffic_in_domain(name, password, local_ip, rmt_ip):
    """
    Purpose:
        Ping the remote interface from ipmp group in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        local_ip - Local interface ip address
        rmt_ip - Remote interface ip address
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    cmd = "nohup ping -s -R -r -v -i %s %s 64 1000 > /dev/null &" % (
        local_ip,
        rmt_ip)
    domain.sendcmd(cmd)

    # Get the interface
    ipmp = get_interface_by_ip(name, password, local_ip)

    # Check the traffic on the interface
    if not check_nic_ib_traffic_state_on_int_in_domain(
            name,
            password,
            ipmp,
            rmt_ip):
        raise Exception("NIC or IB ping traffic does not run as expected")

def check_nic_vf_traffic_state(name, password, vf):
    """
    Purpose:
        Check whether there is traffic on the mapping interface
        of the vf
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - NIC vf
    Return:
        True or False
    """
    # If the mapping interface of the vf is under IPMP group,
    # check the ipmp group, else, check the interface.
    interface = get_nic_vf_interface_in_domain(name, password, vf)
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    if check_nic_vf_under_ipmp(name, password, vf):
        cmd = "ipadm |grep %s" % interface
        output = domain.retsend(cmd)
        int_check = output.split()[3]
    else:
        int_check = interface

    # Check the traffic on this interface
    if check_nic_ib_traffic_state_on_int_in_domain(
            name,
            password,
            int_check):
        return True
    else:
        return False


def get_ib_pf_link_in_domain(name, password, pf):
    """
    Purpose:
        Get the corresponding data link of ib pf in root domain
    Arguments:
        name - Domain name
        password - Domain password
        pf - IB pf
    Return:
        links - Data link
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the device of the pf
    cmd = "ldm list-io -p %s|grep type=PF" % pf
    output = execute(cmd)
    dev = '/' + get_value_from_string(output.split('|')[1])

    safe, tmpfile = tempfile.mkstemp()
    cmd = "fwflash -l -c IB"
    output = domain.retsend(cmd)
    with open(tmpfile, 'r+') as fo:
        fo.write(output)

    # Get the device path from tempfile
    cmd = "awk '/^Device/{print $NF}' %s | awk -F: '{print $1}'" % \
          tmpfile
    output = execute(cmd)
    devs = output.split()

    # Get the HCAGUID from tempfile
    cmd = "awk '/Node Image/{print $NF}' %s" % tmpfile
    output = execute(cmd)
    hcaids = output.split()

    # Compare the device path to get the pf HCAGUID
    i = 0
    for ldev in devs:
        if re.search(dev, ldev):
            match_hcaid = hcaids[i]
            break
        i += 1

    # Get the data links by "dladm show-ib"
    format_match_hcaid = match_hcaid[2:].upper()
    cmd = "dladm show-ib -po LINK,HCAGUID|grep %s" % \
          format_match_hcaid
    output = domain.retsend(cmd)
    links = re.findall(r'net\d+', output)
    return links


def save_ib_info_to_xml(ib_info_dict, ib_info_xml):
    """
    Purpose:
        Save the information of IB information to a xml file
    Arguments:
        ib_info_dict - All the IB information
        ib_info_xml - Where the info to be saved
    Return:
        None
    """
    impl = xml.dom.minidom.getDOMImplementation()
    dom = impl.createDocument(None, 'PFs', None)
    root = dom.documentElement

    for pf, pf_info_dict in ib_info_dict.items():
        pf_element = dom.createElement('PF')
        pf_element.setAttribute('alias', pf)
        hcaid = pf_info_dict['hcaid']
        pf_element.setAttribute('hcaid', hcaid)
        root.appendChild(pf_element)

        ports_dict = pf_info_dict['ports']
        for port, port_info in ports_dict.items():
            if port != 'hcaid':
                port_element = dom.createElement('PORT')
                port_element.setAttribute('ID', port)
                is_test_port = port_info['test']
                port_element.setAttribute('test', is_test_port)
                pf_element.appendChild(port_element)

                for key, value in port_info.items():
                    key_ele = dom.createElement(key)
                    key_text = dom.createTextNode(value)
                    key_ele.appendChild(key_text)
                    port_element.appendChild(key_ele)

    # If ib_info_xml exists, delete it.
    if os.path.isfile(ib_info_xml):
        os.remove(ib_info_xml)

    f = open(ib_info_xml, 'a')
    dom.writexml(f, addindent='  ', newl='\n')
    f.close()


def parse_ib_info_from_xml(ib_info_xml):
    """
    Purpose:
        Save the information of IB information to a xml file
    Arguments:
        ib_info_dict - All the IB information
        ib_info_xml - Where the info to be saved
    Return:
        None
    """
    DOMTree = xml.dom.minidom.parse(ib_info_xml)
    root = DOMTree.documentElement
    pfs = root.getElementsByTagName("PF")

    ib_info_dict = {}
    for pf in pfs:
        pf_alias = pf.getAttribute("alias")
        pf_hcaid = pf.getAttribute("hcaid")
        pf_info_dict = {'hcaid': pf_hcaid}
        ports = pf.getElementsByTagName("PORT")

        ports_dict = {}
        for port in ports:
            port_num = port.getAttribute("ID")
            is_test_port = port.getAttribute("test")
            if is_test_port == 'true':
                is_test_port = True
            else:
                is_test_port = False
            hcaid_ele = port.getElementsByTagName("hcaid")[0]
            hcaid = hcaid_ele.childNodes[0].nodeValue
            portid_ele = port.getElementsByTagName("portid")[0]
            portid = portid_ele.childNodes[0].nodeValue

            port_info_dict = {
                "test": is_test_port,
                "hcaid": hcaid,
                "portid": portid
            }
            ports_dict.update({port_num: port_info_dict})
        pf_info_dict.update({'ports': ports_dict})
        ib_info_dict.update({pf_alias: pf_info_dict})
    return ib_info_dict


def get_ib_pf_by_vf(vf):
    """
    Purpose:
        Get the corresponding pf where ib vf resides
    Arguments:
        vf - IB vf
    Return:
        pf - IB pf
    """
    first = vf.split('.')[0]
    second = vf.split('.')[1]
    pf = first + '.' + second
    return pf


def get_ib_vf_link_in_domain(name, password, vf):
    """
    Purpose:
        Get the corresponding net link of ib vf in root domain
    Arguments:
        name - Domain name
        password - Domain password
        vf - IB vf
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    pf = get_ib_pf_by_vf(vf)
    # Get which port are connected to switch
    ib_info_xml = os.getenv("IB_INFO")
    if os.path.isfile(ib_info_xml):
        ib_info_dict = parse_ib_info_from_xml(ib_info_xml)
    else:
        return None

    pf_hcaid = ib_info_dict[pf]['hcaid']
    for ca_port, port_info in ib_info_dict[pf]['ports'].items():
        if port_info['test']:
            test_portid = ib_info_dict[pf]['ports'][ca_port]['portid']
            break
    identical_hcaid = pf_hcaid[6:]  # Last eight nums are identical with VF's
    cmd = "dladm show-ib -o LINK,HCAGUID,PORT|grep %s" % identical_hcaid
    output = domain.retsend(cmd)
    links = re.findall(r'net\d+', output)
    usable_link = None
    for link in links:
        cmd = "dladm show-ib %s -po PORTGUID" % link
        output = domain.retsend(cmd)
        # Last four nums are identical with VF's
        if output[-4:] == test_portid[-4:]:
            usable_link = link
            break
    return usable_link


def get_ib_hca_port_by_link_in_domain(name, password, link):
    """
    Purpose:
        Get the corresponding ib port of net link in root domain
    Arguments:
        name - Domain name
        password - Domain password
        link - IB link
    Return:
        (hca, port) - IB device and port
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    cmd = "dladm show-ib %s|grep -v LINK" % link
    output = domain.retsend(cmd)
    hcaid = output.split()[1].lower()
    ca_port = output.split()[3]

    cmd = "ibv_devices |grep %s" % hcaid
    output = domain.retsend(cmd)
    hca = output.split()[0]
    return hca, ca_port


def check_ib_pf_be_connected(rmt_host_dict, root_dict):
    """
    Purpose:
        Check the remote ib port has been connected
        to switch, thus, can be pingable from root domain
    Arguments:
        rmt_host_dict - Including remote host name, password, ib pf
        root_dict - Including root domain name, password, ib pf
    Return:
        local_connect_links - The domain and the corresponding net
                              link of ib pf
    """
    # Build host
    rmt_name = rmt_host_dict.keys()[0]
    rmt_password = rmt_host_dict[rmt_name]['password']
    rmt_int = rmt_host_dict[rmt_name]['link']
    rmt_host = Host.Host(rmt_name, rmt_password)

    # Check whether it is an IB device
    cmd = "dladm show-phys %s|grep -v LINK" % rmt_int
    output = rmt_host.return_command(cmd)
    if output.split()[1] != "Infiniband":
        raise Exception("Remote %s on %s was not over an IB device" %
                        (rmt_int, rmt_name))
    # Check whether it's state is up
    if output.split()[2] != "up":
        raise Exception("The physical state of corresponding IB port "
                        "of %s on %s was not up" % (rmt_int, rmt_name))

    # Check whether there is an chkpart0, if yes, delete it.
    rmt_part = 'ior_ckpart0'
    cmd = "dladm show-part %s" % rmt_part
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ifconfig %s" % rmt_part
        try:
            rmt_host.send_command(cmd)
        except ExecuteException:
            pass
        else:
            cmd = "ipadm delete-ip %s" % rmt_part
            rmt_host.send_command(cmd)
            cmd = "dladm delete-part %s" % rmt_part
            rmt_host.send_command(cmd)

    # Create part over the link
    cmd = "dladm create-part -l %s -P ffff %s" % (rmt_int, rmt_part)
    rmt_host.send_command(cmd)

    # Create ip
    cmd = "ipadm create-ip %s" % rmt_part
    rmt_host.send_command(cmd)
    rmt_ip = "11.11.2.2"
    cmd = "ipadm create-addr -T static -a %s/24 %s/static" % (rmt_ip, rmt_part)
    rmt_host.send_command(cmd)
    # Get the remote ib SM lid
    cmd = "dladm show-ib %s|grep -v LINK" % rmt_int
    output = rmt_host.return_command(cmd)
    ca_port = output.split()[3]
    hcaguid = output.split()[1].lower()

    cmd = "ibv_devices|grep -v device"
    output = rmt_host.return_command(cmd)
    hcas = re.findall(r'.*_\d+', output)
    for hca in hcas:
        hca = hca.strip()
        cmd = "ibstat %s |grep 'Node GUID'" % hca
        output = rmt_host.return_command(cmd)
        if re.search(hcaguid, output):
            match_hca = hca
            break
    cmd = "ibstat %s %s|grep 'SM lid'" % (match_hca, ca_port)
    output = rmt_host.return_command(cmd)
    rmt_sm_lid = output.split(':')[1].strip()

    ib_info_dict = {}   # Used to record the ib related info
    # Create part over local ib link
    for name, root_info in root_dict.items():
        password = root_info['password']
        pf = root_info['pf']
        port = get_domain_port(name)
        domain = Ldom.Ldom(name, password, port)
        ints = get_ib_pf_link_in_domain(name, password, pf)
        up_links = []
        pf_info_dict = {}  # Record the IB pf info
        port_dict = {}  # Record the ib port info
        for interface in ints:
            item_dict = {}
            cmd = "dladm show-ib %s|grep -v LINK" % interface
            output = domain.retsend(cmd)
            ca_port = output.split()[3]

            hcaid = output.split()[1]
            item_dict.update({'hcaid': hcaid})
            if not pf_info_dict.get('hcaid', None):
                pf_info_dict.update({'hcaid': hcaid})
            portid = output.split()[2]
            item_dict.update({'portid': portid})
            state = output.split()[4]
            if state == "up":
                up_links.append(interface)
            item_dict.update({'state': state})
            item_dict.update({'test': 'false'})

            port_dict.update({ca_port: item_dict})
        pf_info_dict.update({'ports': port_dict})
        # Check which port is connected to the same switch with remote
        local_connect_link = None
        if len(up_links) == 0:
            raise Exception("Local IB pf %s are not connected to switch" % pf)
        elif len(up_links) == 1:
            local_connect_link = up_links[0]
        else:
            for up_link in up_links:
                hca, ca_port = get_ib_hca_port_by_link_in_domain(
                    name,
                    password,
                    up_link)
                cmd = "ibstat %s %s|grep 'SM lid'" % (hca, ca_port)
                output = domain.retsend(cmd)
                sm_lid = output.split(':')[1].strip()
                if sm_lid == rmt_sm_lid:
                    local_connect_link = up_link
                    break
            if not local_connect_link:
                raise Exception("Local IB pf %s and remote IB pf are not "
                                "connected to the same switch" % pf)

        cmd = "dladm show-ib %s|grep -v LINK" % local_connect_link
        output = domain.retsend(cmd)
        ca_port = output.split()[3]
        port_dict[ca_port]['test'] = 'true'

        ib_info_dict.update({pf: pf_info_dict})

        # Create ip in root domain and ping remote ib part
        # First delete the ib part if exists
        part = 'ior_ckpart0'
        cmd = "dladm show-part %s" % part
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            cmd = "ifconfig %s" % part
            try:
                domain.sendcmd(cmd)
            except ExecuteException:
                pass
            else:
                cmd = "ipadm delete-ip %s" % part
                domain.sendcmd(cmd)
                cmd = "dladm delete-part %s" % part
                domain.sendcmd(cmd)

        # Create part over the link
        cmd = "dladm create-part -l %s -P ffff %s" % (
            local_connect_link,
            part)
        domain.sendcmd(cmd)

        # Create ip
        cmd = "ipadm create-ip %s" % part
        domain.sendcmd(cmd)
        ip = "11.11.2.1"
        cmd = "ipadm create-addr -T static -a %s/24 %s/static" % (
            ip,
            part)
        domain.sendcmd(cmd)

        # Ping remote from root domain
        check_remote_pingable_from_root_domain(
            name,
            password,
            rmt_ip)

        # Delete the part over ib
        cmd = "ipadm delete-ip %s" % part
        domain.sendcmd(cmd)
        cmd = "dladm delete-part %s" % part
        domain.sendcmd(cmd)

    # Record which port are connected to switch
    ib_info_xml = os.getenv("IB_INFO")
    save_ib_info_to_xml(ib_info_dict, ib_info_xml)

    # Delete the remote part
    cmd = "ipadm delete-ip %s" % rmt_part
    rmt_host.send_command(cmd)
    cmd = "dladm delete-part %s" % rmt_part
    rmt_host.send_command(cmd)


def check_ib_ior_enabled_in_iod(name, password):
    """
    Purpose:
        Check whether ib ior has been enabled in io domain,
        If not, enable it.
    Arguments:
        name - IO Domain name
        password - IO Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Check there is line with "ib_ior_enabled=1;" in
    # /etc/driver/drv/ib.conf
    try:
        cmd = "grep \"^ib_ior_enabled\" " \
              "/etc/driver/drv/ib.conf"
        domain.sendcmd(cmd)
    except ExecuteException:
        # Add a line with "ib_ior_enabled=1;"
        cmd = "gsed -i  '$ a\ib_ior_enabled=1;' " \
              "/etc/driver/drv/ib.conf"
        domain.sendcmd(cmd)
        time.sleep(3)
        domain.reboot()
        # Check the action success
        cmd = "grep \"^ib_ior_enabled=1;$\" " \
              "/etc/driver/drv/ib.conf"
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            raise Exception("Failed to enabled IB ior "
                            "in io domain [%s]" % name)
    else:
        cmd = "grep \"^ib_ior_enabled=1;$\" " \
              "/etc/driver/drv/ib.conf"
        try:
            domain.sendcmd(cmd)
        except ExecuteException:
            # Modify that line to "ib_ior_enabled=1;"
            warn_report("IB ior is not enabled in IO domain "
                        "[%s],trying to enabled" % name)
            cmd = "gsed -i  '/^ib_ior_enabled/ c\ib_ior_enabled=1;' " \
                  "/etc/driver/drv/ib.conf"
            domain.sendcmd(cmd)
            time.sleep(3)
            domain.reboot()

            # Check the action success
            cmd = "grep \"^ib_ior_enabled=1;$\" " \
                  "/etc/driver/drv/ib.conf"
            try:
                domain.sendcmd(cmd)
            except ExecuteException:
                raise Exception("Failed to enabled IB ior "
                                "in io domain [%s]" % name)


def get_ib_part_over_link_in_domain(name, password, link):
    """
    Purpose:
        Get the IB parttions over the IB link
    Arguments:
        name - IO Domain name
        password - IO Domain password
        link - IB link
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = "dladm show-part|grep %s|awk '{print $1}'" % link
    output = domain.retsend(cmd)
    parts = output.split()
    return parts


def delete_parts_over_link_in_domain(name, password, link):
    """
    Purpose:
        Get the IB parttions over the IB link
    Arguments:
        name - IO Domain name
        password - IO Domain password
        link - IB link
    Return:
        None
    """
    parts = get_ib_part_over_link_in_domain(name, password, link)
    if parts:
        port = get_domain_port(name)
        domain = Ldom.Ldom(name, password, port)
        for part in parts:
            cmd = "ifconfig %s" % part
            try:
                domain.sendcmd(cmd)
            except ExecuteException:
                pass
            else:
                # If there is ipmp over this link, unconfigure it
                cmd = "ipadm |grep '%s '" % part
                output = domain.retsend(cmd)
                if output.split()[3] != '--':
                    ipmp_group = output.split()[3]
                    unconfigure_ib_ipmp_in_domain(
                        name,
                        password,
                        ipmp_group)
                else:
                    cmd = "ipadm delete-ip %s" % part
                    domain.sendcmd(cmd)
                    cmd = "dladm delete-part %s" % part
                    domain.sendcmd(cmd)


def destroy_all_ib_vfs_on_pf(name, password, pf):
    """
    Purpose:
        Destroy all vfs created on the IB pf
    Arguments:
        name - IO Domain name
        password - IO Domain password
        pf - PF name
    Return:
        None
    """
    vfs_list = list_all_vfs_on_pf(pf)
    for vf in vfs_list:
        cmd = 'ldm list-io -l -p %s|grep %s' % (pf, vf)
        output = execute(cmd)
        # The vf has been bound to a domain,need to be removed
        domain = output.split('|')[4].split('=')[1]
        if domain != '':
            try:
                remove_vf_from_domain(vf, domain)
            except ExecuteException:
                if domain == name:
                    link = get_ib_vf_link_in_domain(name, password, vf)
                    if link:
                        delete_parts_over_link_in_domain(
                            name,
                            password,
                            link)
                else:
                    raise Exception("%s does is bound to %s "
                                    "and can not be removed" %
                                    (vf, domain))
                remove_vf_from_domain(vf, domain)
            time.sleep(5)

    # Destroy all the vfs created under the pf
    cmd = 'ldm destroy-vf -n max %s' % pf
    execute(cmd)


def create_ib_vf(pf):
    """
    Purpose:
        Create IB vf on pf
    Arguments:
        pf - Create vf on this pf
    Return:
        vf - The newly created vf
    """
    cmd = 'ldm create-vf %s' % pf
    output = execute(cmd)
    vf = output.split(':')[1].strip()
    return vf


def unconfigure_ib_ipmp_in_domain(name, password, ipmp):
    """
    Purpose:
        Delete ipmp group for the test interfaces in the IO domain
    Arguments:
        name - Domain name
        password - Domain password
        ipmp - IPMP group name
    Return:
        None
    """
    # Build domain
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the interface in IPMP group
    cmd = "ipmpstat -i -o INTERFACE,GROUP|grep %s|awk '{print $1}'" % \
          ipmp
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        cmd = "ipadm delete-ipmp %s" % ipmp
        domain.sendcmd(cmd, check=False)
    else:
        match = output.split()

        # Delete ipmp group
        for part in match:
            cmd = "ipadm remove-ipmp -i %s %s" % (part, ipmp)
            domain.sendcmd(cmd)

        cmd = "ipadm delete-ipmp %s" % ipmp
        domain.sendcmd(cmd)
        for part in match:
            cmd = "ipadm delete-ip %s" % part
            domain.sendcmd(cmd)
            cmd = "dladm delete-part %s" % part
            domain.sendcmd(cmd)


def configure_ib_vfs_ipmp_in_domain(
        name,
        password,
        ipmp,
        vf1,
        vf2,
        ip):
    """
    Purpose:
        Create ipmp group for the ib test interfaces in the IO domain,
        configure IP for the ipmp group and the remote interface
    Arguments:
        name - Domain name
        password - Domain password
        ipmp - IPMP group name
        vf1 - IB vf 1 in io domain
        vf2 - IB vf 2 in io domain
        ip - IP address
    Return:
        None
    """
    # Build domain by name, password, port
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Check ipmp whether exist, if yes, unconfigure it.
    cmd = "ipmpstat -o GROUP -P -g"
    output = domain.retsend(cmd)
    if re.search(ipmp, output):
        unconfigure_ib_ipmp_in_domain(name, password, ipmp)

    # Create IPMP
    cmd = "ipadm create-ipmp %s" % ipmp
    domain.sendcmd(cmd)
    parts = ['ior_part0', 'ior_part1']
    vfs = [vf1, vf2]
    for i in range(0, 2):
        vf = vfs[i]
        interface = get_ib_vf_link_in_domain(name, password, vf)
        part = parts[i]
        # If the part exists, delete first
        try:
            cmd = "dladm show-part %s" % part
            domain.sendcmd(cmd)
        except ExecuteException:
            pass
        else:
            try:
                cmd = "ifconfig %s" % part
                domain.sendcmd(cmd)
            except ExecuteException:
                pass
            else:
                cmd = "ipadm delete-ip %s" % part
                domain.sendcmd(cmd)
            cmd = "dladm delete-part %s" % part
            domain.sendcmd(cmd)

        cmd = "dladm create-part -l %s -P ffff %s" % (interface, part)
        domain.sendcmd(cmd)
        cmd = "ipadm create-ip %s" % part
        domain.sendcmd(cmd)
        cmd = "ipadm add-ipmp -i %s %s" % (part, ipmp)
        domain.sendcmd(cmd)

    # Create address for IPMP
    cmd = "ipadm create-addr -T static -a {0}/24 {1}/v4addr1".format(
        ip, ipmp)
    domain.sendcmd(cmd)

    # Check the ipmp group state, should be ok
    state = get_ipmp_state_in_domain(name, password, ipmp)
    if state != 'ok':
        raise Exception("The state of %s is not ok, "
                        "please make sure the test interfaces are "
                        "connected to a switch" % ipmp)


def configure_ib_ip_in_remote(hostname, password, link, ip):
    """
    Purpose:
        Create IB ip address for the interface in remote host
    Arguments:
        name - Domain name
        password - Domain password
        link - The IB link to be configured
        subnet - The interface will be configured to this ip address
    Return:
        None
    """
    # Build a Host
    rmt_host = Host.Host(hostname, password)

    # Check whether $part exists, if yes, unplumb
    part = 'ior_part0'
    try:
        cmd = "dladm show-part %s" % part
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        try:
            cmd = "ifconfig %s" % part
            rmt_host.send_command(cmd)
        except ExecuteException:
            pass
        else:
            cmd = "ipadm delete-ip %s" % part
            rmt_host.send_command(cmd)
        cmd = "dladm delete-part %s" % part
        rmt_host.send_command(cmd)

    cmd = "dladm create-part -l %s -P ffff %s" % (link, part)
    rmt_host.send_command(cmd)
    cmd = "ipadm create-ip %s" % part
    rmt_host.send_command(cmd)
    cmd = "ipadm create-addr -T static -a %s/24 %s/static" % (ip, part)
    rmt_host.send_command(cmd)


def get_ib_vf_hotplug_dev(name, password, vf):
    """
    Purpose:
        Get the IB vf hotplug dev
    Arguments:
        name - Domain name where vf resides
        password - Domain password
        vf - IB vf
    Return:
        hotplug_dev
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the IB vf link
    link = get_ib_vf_link_in_domain(name, password, vf)
    # Get the corresponding device of the link
    cmd = "dladm show-phys %s -o LINK,DEVICE|grep -v LINK" % link
    output = domain.retsend(cmd)
    device = str(output.split()[1])

    # Get the device driver
    drv = filter(str.isalpha, device)
    # Get the device num
    num = filter(str.isdigit, device)
    # Get the device path from /etc/path_to_inst
    cmd = "cat /etc/path_to_inst|grep '%s \"%s\"'" % (num, drv)
    output = domain.retsend(cmd)
    device_path = output.split()[0].strip('"')

    strip_char1 = '/' + device_path.split('/')[-1]
    strip_char2 = '/' + device_path.split('/')[-2]

    hotplug_dev = device_path.rstrip(strip_char1).rstrip(strip_char2)

    return hotplug_dev


def get_ib_vf_hotplug_path_port_status(name, password, vf, logfile=None):
    """
    Purpose:
        Get the hotplug path port and status of the ib vf in domain
    Arguments:
        name - Domain name where vf resides
        password - Domain password
        vf - VF name
        logfile - Get the info from this specified logfile
    Return:
        path_port_status_dict - The specified pcie device hotplug status
        e.g.{"hotplug_path":hotplug_path, "hotplug_port":hotplug_port,
            "hotplug_status":hotplug_status}
    """
    hotplug_dev = get_ib_vf_hotplug_dev(name, password, vf)
    hotplug_dev_format = hotplug_dev.replace('/', '\/')

    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    if logfile is None:
        safe, logfile = tempfile.mkstemp()
        cmd = "hotplug list -lv"
        output = domain.retsend(cmd, timeout=180)
        with open(logfile, 'r+') as fo:
            fo.write(output)

    # Get the line number of hotplug_dev from the logfile which stored the
    # hotplug info
    cmd = "sed -n '/^{0}.$/=' {1}".format(hotplug_dev_format, logfile)
    output = execute(cmd)
    dev_line_number = int(output)

    # Calculate the line number of hotplug_path_port_status
    path_port_status_line_number = dev_line_number - 1
    cmd = "sed -n '{0}p' {1}".format(
        path_port_status_line_number,
        logfile)
    output = execute(cmd)
    # Instance: /pci@380/pci@1/pci@0/pci@6  <pci.0,2>  ONLINE
    path_port_status = output
    hotplug_path = path_port_status.split()[0].strip().lstrip(
        "\r\n")  # The first element path_port_status
    # The second element of path_port_status
    hotplug_port = path_port_status.split()[1].strip('<>').strip()
    hotplug_status = path_port_status.split()[2].strip().rstrip(
        "\r\n")  # The last element of path_port_status
    path_port_status_dict = {
        'hotplug_path': hotplug_path,
        'hotplug_port': hotplug_port,
        'hotplug_status': hotplug_status}
    return path_port_status_dict


def get_ib_vf_hotplug_path(name, password, vf, logfile=None):
    """
    Purpose:
        Get hotplug path of the vf
    Arguments:
        name - Domain name
        password - Domain password
        vf - IB vf
        logfile - The file where record "hotplug list -lv" output
    Return:
        hotplug_path
    """
    dev_path_port_status_dict = get_ib_vf_hotplug_path_port_status(
        name,
        password,
        vf,
        logfile)
    hotplug_path = dev_path_port_status_dict['hotplug_path']
    return hotplug_path


def get_ib_vf_hotplug_port(name, password, vf, logfile=None):
    """
    Purpose:
        Get hotplug port of the vf
    Arguments:
        name - Domain name
        password - Domain password
        vf - IB vf
        logfile - The file where record "hotplug list -lv" output
    Return:
        hotplug_port
    """
    dev_path_port_status_dict = get_ib_vf_hotplug_path_port_status(
        name,
        password,
        vf,
        logfile)
    hotplug_port = dev_path_port_status_dict['hotplug_port']
    return hotplug_port


def get_ib_vf_hotplug_status(name, password, vf, logfile=None):
    """
    Purpose:
        Get current hotplug status of the vf
    Arguments:
        name - Domain name
        password - Domain password
        vf - IB vf
        logfile - The file where record "hotplug list -lv" output
    Return:
        hotplug_status
    """
    dev_path_port_status_dict = get_ib_vf_hotplug_path_port_status(
        name,
        password,
        vf,
        logfile)
    hotplug_status = dev_path_port_status_dict['hotplug_status']
    return hotplug_status


def get_ib_vf_hotplug_status_by_path_port(path, port, logfile):
    """
    Purpose:
        Get current hotplug status of the vf
    Arguments:
        path - Hotplug path
        port - Hotplug port
        logfile - The file where record "hotplug list -lv" output
    Return:
        hotplug_status
    """
    cmd = "grep {0} {1}|grep {2}".format(
        path,
        logfile,
        port)
    output = execute(cmd)
    hotplug_status = output.split()[2]
    return hotplug_status


def check_ib_vf_under_ipmp(name, password, vf):
    """
    Purpose:
        Check the part over the corresponding link of
        ib vf is under ipmp group in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - IB vf
    Return:
        True - Under IPMP group
        False - Not under IPMP group
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the corresponding link of the ib vf
    link = get_ib_vf_link_in_domain(name, password, vf)
    # Get the part over the link, this can be ensure only one parttion
    # had been created in previous procedure
    part = get_ib_part_over_link_in_domain(name, password, link)[0]
    hotplug_dev = get_ib_vf_hotplug_dev(name, password, vf)
    cmd = "ipadm |grep %s" % part
    output = domain.retsend(cmd)
    if output.split()[3] != '--':
        ipmp_group = output.split()[3]
        cmd = "ipmpstat -i|grep %s|grep -v %s" % (
            ipmp_group,
            part)
        output = domain.retsend(cmd)
        if output:
            another_part_under_ipmp = output.split()[0]
            cmd = "dladm show-part -po LINK,OVER|grep %s" % \
                  another_part_under_ipmp
            output = domain.retsend(cmd)
            another_link = output.split(':')[1]
            cmd = "dladm show-phys -p -o LINK,DEVICE|grep %s" \
                  % another_link
            output = domain.retsend(cmd)
            another_device = str(output.split(':')[1])
            another_driver = filter(
                str.isalpha,
                another_device)
            another_device_num = filter(
                str.isdigit,
                another_device)
            cmd = "cat /etc/path_to_inst|grep '%s \"%s\"'" % (
                another_device_num,
                another_driver)
            output = domain.retsend(cmd)
            another_link_hotplug_dev = output.split()[0].strip('"')
            pci_bus_path = another_link_hotplug_dev.split('/')[1]
            if pci_bus_path != hotplug_dev.split('/')[1]:
                return True
            else:
                return False
        else:
            return False
    else:
        return False


def get_ib_vf_ipmp_group(name, password, vf):
    """
    Purpose:
        Get the ipmp group where the part over the corresponding
        link of ib vf resides in io domain
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - IB vf
    Return:
        ipmp_group - IPMP group
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    # Get the corresponding link of the nic vf
    link = get_ib_vf_link_in_domain(name, password, vf)
    part = get_ib_part_over_link_in_domain(name, password, link)[0]
    cmd = "ipadm |grep %s" % part
    output = domain.retsend(cmd)
    ipmp_group = None
    if output.split()[3] != '--':
        ipmp_group = output.split()[3]
    return ipmp_group


def check_ib_vf_traffic_state(name, password, vf):
    """
    Purpose:
        Check whether there is traffic on the part over the
        corresponding link of the vf
    Arguments:
        name - IO domain name
        password - IO domain password
        vf - IB vf
    Return:
        True or False
    """
    # If the part over the corresponding link of the vf
    # is under IPMP group, check the ipmp group, else,
    # check the interface.
    link = get_ib_vf_link_in_domain(name, password, vf)
    part = get_ib_part_over_link_in_domain(name, password, link)[0]
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    if check_ib_vf_under_ipmp(name, password, vf):
        cmd = "ipadm |grep %s" % part
        output = domain.retsend(cmd)
        part_check = output.split()[3]
    else:
        part_check = part

    # Check the traffic on this interface
    if check_nic_ib_traffic_state_on_int_in_domain(
            name,
            password,
            part_check):
        return True
    else:
        return False


def save_ipadm_log(name, password, directory):
    """
    Purpose:
        Save the output of "ipadm" of the domain
    Arguments:
        directory - Directory to save the output
    Return:
        logfile - Path of the log
    """
    # Name the file as ipadm.{current time}
    now = time.strftime("%H%M%S")
    logfile = "%s/%s" % (directory, 'ipadm.' + now)
    cmd = 'touch %s' % logfile
    execute(cmd)

    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = "ipadm"
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        output = None
    if output is None:
        return logfile
    with open(logfile, 'r+') as fo:
        fo.write(output)
    return logfile


def save_ipmpstat_g_log(name, password, directory):
    """
    Purpose:
        Save the output of "ipmpstat" of the domain
    Arguments:
        directory - Directory to save the output
    Return:
        logfile - Path of the log
    """
    # Name the file as ipmpstat.{current time}
    now = time.strftime("%H%M%S")
    logfile = "%s/%s" % (directory, 'ipmpstatg.' + now)
    cmd = 'touch %s' % logfile
    execute(cmd)

    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = "ipmpstat -o GROUP,STATE -P -g"
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        output = None
    if output is None:
        return logfile
    with open(logfile, 'r+') as fo:
        fo.write(output)
    return logfile


def save_ipmpstat_i_log(name, password, directory):
    """
    Purpose:
        Save the output of "ipmpstat" of the domain
    Arguments:
        directory - Directory to save the output
    Return:
        logfile - Path of the log
    """
    # Name the file as ipmpstat.{current time}
    now = time.strftime("%H%M%S")
    logfile = "%s/%s" % (directory, 'ipmpstati.' + now)
    cmd = 'touch %s' % logfile
    execute(cmd)

    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = "ipmpstat -o INTERFACE,GROUP,STATE -P -i"
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        output = None
    if output is None:
        return logfile
    with open(logfile, 'r+') as fo:
        fo.write(output)
    return logfile


def get_interface_state_from_logfile(interface, logfile):
    """
    Purpose:
        Get the interface state from logfile
    Arguments:
        interface - Network interface
        logfile - The logfile where to get from
    Return:
        state - 'ok' or 'disabled'
    """
    cmd = "grep '%s ' %s|head -1" % (interface, logfile)
    output = execute(cmd)
    state = output.split()[2]
    return state


def get_ipmp_state_from_logfile(ipmp_group, logfile):
    """
    Purpose:
        Get the IPMP group state from logfile
    Arguments:
        ipmp_group - IPMP group
        logfile - The logfile where to get from
    Return:
        state - 'ok' or 'degraded'
    """
    cmd = "grep %s %s" % (ipmp_group, logfile)
    output = execute(cmd)
    state = output.split(':')[1].strip()
    return state


def save_all_vfs_info_to_xml(all_vfs_info_dict, all_vfs_info_xml):
    """
    Purpose:
        Save the information of test vfs to a xml file
    Arguments:
        all_vfs_info_dict - All the vfs information
        all_vfs_info_xml - Where the info to be saved
    Return:
        None
    """
    impl = xml.dom.minidom.getDOMImplementation()
    dom = impl.createDocument(None, 'NPRDs', None)
    root = dom.documentElement

    for nprd, rd_pfs_vfs_dict in all_vfs_info_dict.items():
        nprd_element = dom.createElement('NPRD')
        nprd_element.setAttribute('name', nprd)
        root.appendChild(nprd_element)

        for pf, pf_vfs_dict in rd_pfs_vfs_dict.items():
            pf_element = dom.createElement('PF')
            pf_element.setAttribute('alias', pf)
            pf_class = get_pf_class(pf)
            pf_element.setAttribute('class', pf_class)
            nprd_element.appendChild(pf_element)

            for vf, info_item in pf_vfs_dict.items():
                vf_element = dom.createElement('VF')
                vf_element.setAttribute('alias', vf)
                vf_class = info_item['class']
                vf_element.setAttribute('class', vf_class)
                pf_element.appendChild(vf_element)

                for each_vf_key, each_vf_value in info_item.items():
                    each_vf_ele = dom.createElement(each_vf_key)
                    each_vf_text = dom.createTextNode(each_vf_value)
                    each_vf_ele.appendChild(each_vf_text)
                    vf_element.appendChild(each_vf_ele)

    f = open(all_vfs_info_xml, 'a')
    dom.writexml(f, addindent='  ', newl='\n')
    f.close()


def get_all_vfs_info(iod_info_dict, all_vfs_dict):
    """
    Purpose:
        Get all test vfs information and save to a xml file
    Arguments:
        iod_info_dict - IO domain dict, including iod_name and iod_password
            e.g. ["fc_iod1":"nqa123"]
        all_vfs_dict - The vfs which will be tested
        all_vfs_info_xml - The xml file where to save the vfs information
    Return:
        None
    """
    path = os.getenv("TMPPATH")
    all_vfs_info_xml = os.getenv("VFS_INFO")

    iod_name = iod_info_dict.get('name')
    iod_port = get_domain_port(iod_name)
    iod_password = iod_info_dict.get('password')
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    hotplug_logfile = iod.save_hotplug_log(path)

    # Get all the vfs information
    all_vfs_info_dict = {}
    for nprd, pf_vfs in all_vfs_dict.items():
        each_pf_vfs_dict = {}
        for pf, vfs_iod_dict in pf_vfs.items():
            each_vfs_dict = {}
            pf_class = get_pf_class(pf)
            for vf, domain in vfs_iod_dict.items():
                each_vf_info_dict = {}
                if pf_class == 'FIBRECHANNEL':
                    hotplug_dev = get_vf_hotplug_dev(vf)
                    hotplug_path = get_vf_hotplug_path(vf)
                    hotplug_port = get_vf_hotplug_port(vf)
                    port_wwn = get_vf_port_wwn(vf)

                    if domain == iod_name:
                        hotplug_status = iod.get_vf_hotplug_status(
                            vf,
                            hotplug_logfile)
                        logical_path = iod.get_vf_logical_path(vf)
                        mpxio_flag = iod.check_vf_mpxio(vf)
                        io_state = iod.check_vf_io_workload_on(vf)
                    else:
                        new_iod_name = domain
                        new_iod_port = get_domain_port(new_iod_name)
                        new_iod = Ldom.Ldom(
                            new_iod_name,
                            iod_password,
                            new_iod_port)
                        new_hotplug_log = new_iod.save_hotplug_log(path)
                        hotplug_status = new_iod.get_vf_hotplug_status(
                            vf,
                            new_hotplug_log)
                        logical_path = new_iod.get_vf_logical_path(vf)
                        mpxio_flag = new_iod.check_vf_mpxio(vf)
                        io_state = new_iod.check_vf_io_workload_on(vf)
                    if not logical_path:
                        logical_path = 'none'
                    if mpxio_flag:
                        mpxio_flag = 'true'
                    else:
                        mpxio_flag = 'false'
                    if io_state:
                        io_state = 'true'
                    else:
                        io_state = 'false'
                    each_vf_info_dict.update(
                        {"hotplug_dev": hotplug_dev})
                    each_vf_info_dict.update(
                        {"hotplug_path": hotplug_path})
                    each_vf_info_dict.update(
                        {"hotplug_port": hotplug_port})
                    each_vf_info_dict.update(
                        {"port_wwn": port_wwn}) 
                    each_vf_info_dict.update(
                        {"hotplug_status": hotplug_status})
                    each_vf_info_dict.update(
                        {"logical_path": logical_path})
                    each_vf_info_dict.update(
                        {"mpxio_flag": mpxio_flag})
                    each_vf_info_dict.update(
                        {"io_state": io_state})
                elif pf_class == 'NETWORK':  # NIC VF
                    hotplug_dev = get_vf_hotplug_dev(vf)
                    hotplug_path = get_vf_hotplug_path(vf)
                    hotplug_port = get_vf_hotplug_port(vf)
                    hotplug_status = iod.get_vf_hotplug_status(
                        vf,
                        hotplug_logfile)
                    interface = get_nic_vf_interface_in_domain(
                        iod_name,
                        iod_password,
                        vf)
                    ipmp_flag = check_nic_vf_under_ipmp(
                        iod_name,
                        iod_password,
                        vf)
                    if ipmp_flag:
                        ipmp_group = get_nic_vf_ipmp_group(
                            iod_name,
                            iod_password,
                            vf)
                        ipmp_flag = 'true'
                    else:
                        ipmp_group = 'none'
                        ipmp_flag = 'false'
                    traffic_state = check_nic_vf_traffic_state(
                        iod_name,
                        iod_password,
                        vf)
                    if traffic_state:
                        traffic_state = 'true'
                    else:
                        traffic_state = 'false'
                    each_vf_info_dict.update(
                        {"hotplug_dev": hotplug_dev})
                    each_vf_info_dict.update(
                        {"hotplug_path": hotplug_path})
                    each_vf_info_dict.update(
                        {"hotplug_port": hotplug_port})
                    each_vf_info_dict.update(
                        {"hotplug_status": hotplug_status})
                    each_vf_info_dict.update(
                        {"interface": interface})
                    each_vf_info_dict.update(
                        {"ipmp_flag": ipmp_flag})
                    each_vf_info_dict.update(
                        {"ipmp_group": ipmp_group})
                    each_vf_info_dict.update(
                        {"traffic_state": traffic_state})
                else:  # IB VF
                    hotplug_dev = get_ib_vf_hotplug_dev(
                        iod_name,
                        iod_password,
                        vf)
                    path_port_status = get_ib_vf_hotplug_path_port_status(
                        iod_name,
                        iod_password,
                        vf,
                        hotplug_logfile)
                    hotplug_path = path_port_status['hotplug_path']
                    hotplug_port = path_port_status['hotplug_port']
                    hotplug_status = path_port_status['hotplug_status']
                    link = get_ib_vf_link_in_domain(
                        iod_name,
                        iod_password,
                        vf)
                    part = get_ib_part_over_link_in_domain(
                        iod_name,
                        iod_password,
                        link)[0]
                    ipmp_flag = check_ib_vf_under_ipmp(
                        iod_name,
                        iod_password,
                        vf)
                    if ipmp_flag:
                        ipmp_group = get_ib_vf_ipmp_group(
                            iod_name,
                            iod_password,
                            vf)
                        ipmp_flag = 'true'
                    else:
                        ipmp_group = 'none'
                        ipmp_flag = 'false'
                    traffic_state = check_ib_vf_traffic_state(
                        iod_name,
                        iod_password,
                        vf)
                    if traffic_state:
                        traffic_state = 'true'
                    else:
                        traffic_state = 'false'
                    each_vf_info_dict.update(
                        {"hotplug_dev": hotplug_dev})
                    each_vf_info_dict.update(
                        {"hotplug_path": hotplug_path})
                    each_vf_info_dict.update(
                        {"hotplug_port": hotplug_port})
                    each_vf_info_dict.update(
                        {"hotplug_status": hotplug_status})
                    each_vf_info_dict.update(
                        {"link": link})
                    each_vf_info_dict.update(
                        {"part": part})
                    each_vf_info_dict.update(
                        {"ipmp_flag": ipmp_flag})
                    each_vf_info_dict.update(
                        {"ipmp_group": ipmp_group})
                    each_vf_info_dict.update(
                        {"traffic_state": traffic_state})

                # All vfs have class, io_domain
                each_vf_info_dict.update(
                    {"class": pf_class})
                each_vf_info_dict.update(
                    {"io_domain": domain})
                each_vfs_dict.update({vf: each_vf_info_dict})
            each_pf_vfs_dict.update({pf: each_vfs_dict})
        all_vfs_info_dict.update({nprd: each_pf_vfs_dict})

    # If all_vfs_info_xml exists, delete it.
    if os.path.isfile(all_vfs_info_xml):
        os.remove(all_vfs_info_xml)
    # Save to the all_vfs_info_xml file
    save_all_vfs_info_to_xml(all_vfs_info_dict, all_vfs_info_xml)


class operate_domain_thread(threading.Thread):
    """
    Purpose:
        Since interrupt root domain is in a child thread, define the
        function thread here
    Arguments:
        threadName - The thread's name
        event - communication event between child thread and the main thread
        port - Root domain port
        password - Root domain password
        operate_type - Reboot or panic
        operate_count - Interrupt counts
    Return:
        None
    """
    def __init__(self, threadName, event, domain_dict):
        threading.Thread.__init__(self, name=threadName)
        self.threadEvent = event
        self.name = domain_dict.keys()[0]
        self.password = domain_dict[self.name].get('password')
        self.operate_type = domain_dict[self.name].get('operate_type')
        self.operate_count = domain_dict[self.name].get('operate_count')

    def run(self):
        port = get_domain_port(self.name)
        nprd = Ldom.Ldom(self.name, self.password, port)
        try:
            # When child thread start, set the event to notify main thread
            if not self.threadEvent.isSet():
                self.threadEvent.set()
            if self.operate_type == 'reboot':
                nprd.reboot(self.operate_count)
            else:
                nprd.panic(self.operate_count)
        except Exception as e:
            error_print_report(
                "Failed to %s root domain due to:\n%s" %
                (self.operate_type, e))
        else:
            # Only T7 platform, when root domain boot up,
            # the vf status in IO domain still OFFLINE,
            # so wait for 30 seconds to avoid the issue.
            time.sleep(30)
        finally:
            # No matter child thread finish with success or failure,
            # clear the event to notify the main thread
            self.threadEvent.clear()


def parse_all_vfs_info_from_xml(all_vfs_info_xml):
    """
    Purpose:
        Parse the information of test vfs from a xml file
    Arguments:
        all_vfs_info_xml - Where the info to be parsed
    Return:
        all_vfs_info_dict
    """
    test_vfs_info_dict = {}
    DOMTree = xml.dom.minidom.parse(all_vfs_info_xml)
    root = DOMTree.documentElement
    nprds = root.getElementsByTagName("NPRD")

    for nprd_ele in nprds:
        nprd = nprd_ele.getAttribute("name")
        pfs = nprd_ele.getElementsByTagName("PF")

        pfs_vfs_dict = {}
        for pf in pfs:
            pf_alias = pf.getAttribute("alias")
            pf_class = pf.getAttribute("class")
            vfs = pf.getElementsByTagName("VF")

            vfs_info_dict = {}
            for vf in vfs:
                vf_alias = vf.getAttribute("alias")
                vf_class = vf.getAttribute("class")

                io_domain_ele = vf.getElementsByTagName("io_domain")[0]
                io_domain = io_domain_ele.childNodes[0].nodeValue
                hotplug_dev_ele = vf.getElementsByTagName("hotplug_dev")[0]
                hotplug_dev = hotplug_dev_ele.childNodes[0].nodeValue
                hotplug_path_ele = vf.getElementsByTagName("hotplug_path")[0]
                hotplug_path = hotplug_path_ele.childNodes[0].nodeValue
                hotplug_port_ele = vf.getElementsByTagName("hotplug_port")[0]
                hotplug_port = hotplug_port_ele.childNodes[0].nodeValue
                hotplug_status_ele = vf.getElementsByTagName("hotplug_status")[0]
                hotplug_status = hotplug_status_ele.childNodes[0].nodeValue

                info_dict = {
                    "class": vf_class,
                    "io_domain": io_domain,
                    "hotplug_dev": hotplug_dev,
                    "hotplug_path": hotplug_path,
                    "hotplug_port": hotplug_port,
                    "hotplug_status": hotplug_status,
                }
                if pf_class == 'FIBRECHANNEL':
                    port_wwn_ele = vf.getElementsByTagName("port_wwn")[0]
                    port_wwn = port_wwn_ele.childNodes[0].nodeValue
                    logical_path_ele = vf.getElementsByTagName("logical_path")[0]
                    logical_path = logical_path_ele.childNodes[0].nodeValue
                    if logical_path == 'none':
                        logical_path = None
                    mpxio_flag_ele = vf.getElementsByTagName("mpxio_flag")[0]
                    mpxio_flag = mpxio_flag_ele.childNodes[0].nodeValue
                    if mpxio_flag == 'true':
                        mpxio_flag = True
                    else:
                        mpxio_flag = False
                    io_state_ele = vf.getElementsByTagName("io_state")[0]
                    io_state = io_state_ele.childNodes[0].nodeValue
                    if io_state == 'true':
                        io_state = True
                    else:
                        io_state = False
                    info_dict.update({"port_wwn": port_wwn})
                    info_dict.update({"logical_path": logical_path})
                    info_dict.update({"mpxio_flag": mpxio_flag})
                    info_dict.update({"io_state": io_state})
                elif pf_class == 'NETWORK':
                    interface_ele = vf.getElementsByTagName("interface")[0]
                    interface = interface_ele.childNodes[0].nodeValue

                    ipmp_flag_ele = vf.getElementsByTagName("ipmp_flag")[0]
                    ipmp_flag = ipmp_flag_ele.childNodes[0].nodeValue
                    if ipmp_flag == 'true':
                        ipmp_flag = True
                    else:
                        ipmp_flag = False
                    ipmp_group_ele = vf.getElementsByTagName("ipmp_group")[0]
                    ipmp_group = ipmp_group_ele.childNodes[0].nodeValue

                    traffic_state_ele = vf.getElementsByTagName("traffic_state")[0]
                    traffic_state = traffic_state_ele.childNodes[0].nodeValue
                    if traffic_state == 'true':
                        traffic_state = True
                    else:
                        traffic_state = False

                    info_dict.update({"interface": interface})
                    info_dict.update({"ipmp_flag": ipmp_flag})
                    info_dict.update({"ipmp_group": ipmp_group})
                    info_dict.update({"traffic_state": traffic_state})
                else:
                    link_ele = vf.getElementsByTagName("link")[0]
                    link = link_ele.childNodes[0].nodeValue
                    part_ele = vf.getElementsByTagName("part")[0]
                    part = part_ele.childNodes[0].nodeValue
                    ipmp_flag_ele = vf.getElementsByTagName("ipmp_flag")[0]
                    ipmp_flag = ipmp_flag_ele.childNodes[0].nodeValue
                    if ipmp_flag == 'true':
                        ipmp_flag = True
                    else:
                        ipmp_flag = False
                    ipmp_group_ele = vf.getElementsByTagName("ipmp_group")[0]
                    ipmp_group = ipmp_group_ele.childNodes[0].nodeValue

                    traffic_state_ele = vf.getElementsByTagName("traffic_state")[0]
                    traffic_state = traffic_state_ele.childNodes[0].nodeValue
                    if traffic_state == 'true':
                        traffic_state = True
                    else:
                        traffic_state = False

                    info_dict.update({"link": link})
                    info_dict.update({"part": part})
                    info_dict.update({"ipmp_flag": ipmp_flag})
                    info_dict.update({"ipmp_group": ipmp_group})
                    info_dict.update({"traffic_state": traffic_state})

                vfs_info_dict.update({vf_alias: info_dict})
            pfs_vfs_dict.update({pf_alias: vfs_info_dict})
        test_vfs_info_dict.update({nprd: pfs_vfs_dict})
    return test_vfs_info_dict


def get_domain_hotplug_info(name, password):
    """
    Purpose:
        Get output of "hotplug list -lv" in domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        output - output of the 'hotplug list -lv'
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = 'hotplug list -lv'
    output = domain.retsend(cmd)
    return output


def get_domain_test_vfs_hotplug_status(
        iod_name,
        iod_password,
        test_vfs_in_iod,
        log_dir):
    """
    Purpose:
        Get all the vfs hotplug_status
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        test_vfs_in_iod - Test vfs in io domain
        log_dir - Where to record the output of "hotplug list lv"
    Return:
        vfs_status_dict - All vfs hotplug status
    """
    vfs_status_dict = {}
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    hotplug_logfile = iod.save_hotplug_log(log_dir)

    for vf, vf_info in test_vfs_in_iod.items():
        hotplug_path = vf_info["hotplug_path"]
        hotplug_port = vf_info["hotplug_port"]
        hotplug_status = iod.get_vf_hotplug_status_by_path_port(
            hotplug_path,
            hotplug_port,
            hotplug_logfile)
        item_dict = {vf: [hotplug_status]}
        vfs_status_dict.update(item_dict)
    info_report(vfs_status_dict)
    return vfs_status_dict


def get_domain_ior_ralated_status(
        iod_name,
        iod_password,
        vfs_in_iod,
        log_dir):
    """
    Purpose:
        Get all the VFs information including hotplug_status,fc port,
        logical path in domain
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        vfs_in_iod - The test vfs in the domain
        log_dir - Where to record the output of "hotplug list lv"
    Return:
        vfs_related_status_dict - All the VFs related information
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    vfs_related_status_dict = {}

    # Save the related info in io domain by sending "hotplug list -lv"
    # "fcinfo hba-port|grep HBA" and "mpathadm list lu"
    hotplug_logfile = iod.save_hotplug_log(log_dir)

    vf_info = vfs_in_iod.values()[0]
    # If VF is fc
    if vf_info["class"] == "FIBRECHANNEL":
        fcinfo_logfile = iod.save_fcinfo_log(log_dir)
        path_logfile = iod.save_path_log(log_dir)
    else:
        ipadm_logfile = save_ipadm_log(
            iod_name,
            iod_password,
            log_dir)
        ipmpstatg_logfile = save_ipmpstat_g_log(
            iod_name,
            iod_password,
            log_dir)
        # NIC vf
        if vf_info["class"] == "NETWORK":
            pass
        else:
            pass

    # Parse and get the related info from the logfile
    for vf, vf_info in vfs_in_iod.items():
        hotplug_path = vf_info["hotplug_path"]
        hotplug_port = vf_info["hotplug_port"]
        each_vf_dict = {}

        # All vfs have hotplug status
        hotplug_status = iod.get_vf_hotplug_status_by_path_port(
                hotplug_path,
                hotplug_port,
                hotplug_logfile)  # Status: ONLINE, OFFLINE or others
        each_vf_dict.update({"hotplug_status": hotplug_status})

        # FC vfs
        if vf_info["class"] == "FIBRECHANNEL":
            port_wwn = vf_info["port_wwn"]
            logical_path = vf_info["logical_path"]

            port_whether_found = iod.check_vf_port_wwn_status(
                port_wwn,
                fcinfo_logfile)  # True or False
            each_vf_dict.update({"port_found": port_whether_found})
            logical_path_found = iod.check_vf_logical_path_status(
                logical_path,
                path_logfile)  # True or False
            each_vf_dict.update({"logical_path_found": logical_path_found})
        else:
            # NIC vfs
            if vf_info["class"] == "NETWORK":
                interface_state = get_interface_state_from_logfile(
                    vf_info["interface"], ipadm_logfile)
                each_vf_dict.update({"interface_state": interface_state})
                if vf_info["ipmp_flag"]:
                    ipmp_state = get_ipmp_state_from_logfile(
                        vf_info["ipmp_group"], ipmpstatg_logfile)
                    each_vf_dict.update({"ipmp_state": ipmp_state})
            else:
                # IB vfs
                part_state = get_interface_state_from_logfile(
                    vf_info["part"], ipadm_logfile)
                each_vf_dict.update({"interface_state": part_state})
                if vf_info["ipmp_flag"]:
                    ipmp_state = get_ipmp_state_from_logfile(
                        vf_info["ipmp_group"], ipmpstatg_logfile)
                    each_vf_dict.update({"ipmp_state": ipmp_state})

        item_dict = {vf: each_vf_dict}  # Build the dict to return
        vfs_related_status_dict.update(item_dict)
    info_report(vfs_related_status_dict)
    return vfs_related_status_dict


def get_domain_vfs_hotplug_status(
        status_dict,
        test_vfs_in_iod):
    """
    Purpose:
        Get VFs hotplug_status during the root domain interrupted
    Arguments:
        status_dicts - All VFs hotplug_status dict
        test_vfs_in_iod - Test vfs in IO domain
        test_class - Check FC/NIC/IB vfs status
    Return:
        hotplug_status - e.g."ONLINE"
    """
    offline_flag = 0
    maintenance_suspend_flag = 0

    for vf, vf_info in test_vfs_in_iod.items():
        if status_dict.get(vf)[0] != 'ONLINE':
            if status_dict.get(vf)[0] == 'OFFLINE':
                offline_flag += 1
            elif status_dict.get(vf)[0] == 'MAINTENANCE-SUSPENDED':
                maintenance_suspend_flag += 1
            else:
                pass

    # If all the vf are OFFLINE, the status can ensure to be OFFLINE
    if offline_flag == 0:
        hotplug_status = 'ONLINE'
    elif offline_flag == len(test_vfs_in_iod.keys()):
        hotplug_status = 'OFFLINE'
    else:
        hotplug_status = 'MIX-OFFLNE'
    if maintenance_suspend_flag == 0:
        pass
    elif maintenance_suspend_flag == len(test_vfs_in_iod.keys()):
        hotplug_status = 'MAINTENANCE-SUSPENDED'
    else:
        hotplug_status = 'MIX-MAINTENANCE-SUSPENDED'
    return hotplug_status


def check_domain_vfs_hotplug_status(
        ior_related_status,
        test_vfs_in_iod_name):
    """
    Purpose:
        Check all VFs hotplug status after root domain interrupted
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        ior_related_status -  All VFs information including
            hotplug status,fc port,logical path
        test_vfs_in_iod_name - The test vfs in io domain
    Return:
        status - 0 Pass
                 1 Fail
    """
    status = 0
    for vf in ior_related_status.keys():
        # After root domain interrupted, vf status in io domain
        # will be identical with the original status
        if ior_related_status[vf]["hotplug_status"] != \
                test_vfs_in_iod_name[vf]["hotplug_status"]:
            info_report("VF [%s] hotplug_status check results:Fail" % vf)
            status += 1
        else:
            info_report("VF [%s] hotplug_status check results:Pass" % vf)

    # Even one is not identical with original, the result should be Fail
    if status > 0:
        status = 1
    return status


def check_domain_disk_and_io(
        iod_name,
        iod_password,
        ior_related_status,
        root_domain_list,
        test_vfs_in_iod):
    """
    Purpose:
        Check whether the logical path exists and io workload status
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        ior_related_status - All VFs information including hotplug status,
            fc port,logical path
        root_domain_list - The root domain being interrupted
        test_vfs_in_iod - The test vfs in the domain
    Return:
        status - 0 Pass
                 1 Fail
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    status = 0
    # Float case, two root domains be interrupted
    if len(root_domain_list) > 1:
        for vf in ior_related_status.keys():
            # VF has no mapping to any logical path
            if test_vfs_in_iod[vf]["logical_path"] is None:
                # Found a logical path: Fail
                if ior_related_status[vf]["logical_path_found"]:
                    info_report("VF [%s] logical_path check results:Fail" % vf)
                    status += 1
                else:  # No logical path found: Pass
                    info_report("VF [%s] logical_path check results:Pass" % vf)
            else:
                # No logical path found: Fail
                if ior_related_status[vf]["logical_path_found"]:
                    info_report("VF [%s] logical_path check results:Pass" % vf)
                else:  # Found a logical path: Pass
                    info_report("VF [%s] logical_path check results:Fail" % vf)
                    status += 1
            # If suspend-client-grace-period in /kernel/dev/scsi_vhci.conf
            # is set as 600, IO may not be zero
            if iod.check_vf_io_workload_on(vf):  # VF has io workload on: Fail
                info_report("VF [%s] I/O check results:Fail" % vf)
                status += 1
            else:  # No io workload on VF: Pass
                info_report("VF [%s] I/O check results:Pass" % vf)
    else:  # Only one root domain be interrupted
        normal_status = ['ONLINE', 'OFFLINE']

        for vf, vf_info in test_vfs_in_iod.items():
            # If VF status is not ONLINE or OFFLINE, no need to check: Fail
            if ior_related_status[vf]["hotplug_status"] not in normal_status:
                status = 1
                break
            # This vf and another vf are multipath configured
            if vf_info.get("mpxio_flag"):
                # Found mapping logical path: Pass
                if ior_related_status[vf]["logical_path_found"]:
                    info_report("VF [%s] logical_path check results:Pass" % vf)
                    # The vf has io workload before root domain be interrupted
                    if vf_info.get("io_state"):
                        # IO workload on: Pass
                        if iod.check_vf_io_workload_on(vf):
                            info_report("VF [%s] I/O check results:Pass" % vf)
                        else:  # No io workload: Fail
                            info_report("VF [%s] I/O check results:Fail" % vf)
                            status += 1
                    # VF has no io workload before root domain be interrupted
                    else:
                        # IO workload on: Fail
                        if iod.check_vf_io_workload_on(vf):
                            info_report("VF [%s] I/O check results:Fail" % vf)
                            status += 1
                        else:  # No io workload: Pass
                            info_report("VF [%s] I/O check results:Pass" % vf)
                else:
                    info_report("VF [%s] logical_path check results:Fail" % vf)
                    status += 1
            else:  # Not multipath configured
                # VF status is 'ONLINE'
                if ior_related_status[vf]["hotplug_status"] == normal_status[0]:
                    # No mapping logical path before root domain be interrupted
                    if vf_info.get("logical_path") is None:
                        # Found mapping logical path: Fail
                        if ior_related_status[vf]["logical_path_found"]:
                            info_report(
                                "VF [%s] logical_path check results:Fail" % vf)
                            status += 1
                        else:  # No logical path found: Pass
                            info_report(
                                "VF [%s] logical_path check results:Pass" % vf)
                    # VF has a mapping logical path before root domain be
                    # interrupted
                    else:
                        # Found mapping logical path: Pass
                        if ior_related_status[vf]["logical_path_found"]:
                            info_report(
                                "VF [%s] logical_path check results:Pass" % vf)
                        else:  # No logical path found : Fail
                            info_report(
                                "VF [%s] logical_path check results:Fail" % vf)
                            status += 1
                else:  # VF status is 'OFFLINE'
                    # Found mapping logical path: Fail
                    if ior_related_status[vf]["logical_path_found"]:
                        info_report(
                            "VF [%s] logical_path check results:Fail" % vf)
                        status += 1
    if status > 0:
        status = 1
    return status


def check_domain_interface_and_traffic(
        iod_name,
        iod_password,
        ior_related_status,
        root_domain_list,
        test_vfs_in_iod):
    """
    Purpose:
        Check the nic interface state and io traffic state
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        ior_related_status - All VFs information including hotplug_status,
        interface_state, traffic state
        root_domain_list - The root domain being interrupted
        test_vfs_in_iod - The test vfs in the domain
    Return:
        status - 0 Pass
                 1 Fail
    """
    status = 0
    # Float case, two root domains be interrupted
    if len(root_domain_list) > 1:
        pass
    else:  # Only one root domain be interrupted
        normal_status = ['MAINTENANCE-SUSPENDED', 'ONLINE', 'MAINTENANCE']
        for vf, vf_info in test_vfs_in_iod.items():
            # If VF status is not ONLINE/MAINTENANCE-SUSPENDE/MAINTENANCE,
            # no need to check: Fail
            if ior_related_status[vf]["hotplug_status"] not in normal_status:
                status = 1
                break

            if ior_related_status[vf]["hotplug_status"] == normal_status[0]:
                if ior_related_status[vf]["interface_state"] != "failed":
                    status += 1
                    info_report("VF [%s] interface state check results:Fail" %
                                vf)
                if vf_info["ipmp_flag"]:
                    if ior_related_status[vf]["ipmp_state"] != "degraded":
                        info_report("VF [%s] ipmp state check results:Fail" %
                                    vf)
                        status += 1
                    else:
                        if vf_info["traffic_state"]:
                            if not check_nic_ib_traffic_state_on_int_in_domain(
                                    iod_name,
                                    iod_password,
                                    vf_info["ipmp_group"]):
                                info_report("VF [%s] traffic check results:Fail" %
                                            vf)
                                status += 1
                else:
                    if vf_info["traffic_state"]:
                        if check_nic_ib_traffic_state_on_int_in_domain(
                                iod_name,
                                iod_password,
                                vf_info["interface"]):
                            info_report("VF [%s] traffic check results:Fail" %
                                        vf)
                            status += 1
            else:
                if ior_related_status[vf]["interface_state"] != "ok":
                    status += 1
                    info_report("VF [%s] interface state check results:Fail" %
                                vf)
                if vf_info["ipmp_flag"]:
                    if ior_related_status[vf]["ipmp_state"] != "ok":
                        info_report("VF [%s] ipmp state check results:Fail" %
                                    vf)
                        status += 1
                    else:
                        if vf_info["traffic_state"]:
                            if not check_nic_ib_traffic_state_on_int_in_domain(
                                    iod_name,
                                    iod_password,
                                    vf_info["ipmp_group"]):
                                info_report("VF [%s] traffic check results:Fail" %
                                            vf)
                                status += 1
                else:
                    if vf_info["traffic_state"]:
                        if not check_nic_ib_traffic_state_on_int_in_domain(
                                iod_name,
                                iod_password,
                                vf_info["interface"]):
                            info_report("VF [%s] traffic check results:Fail" %
                                        vf)
                            status += 1
    if status > 0:
        status = 1
    return status


def check_ior_in_domain(iods_dict, root_domain_dict, event):
    """
    Purpose:
        Check ior whether works normally in io domain
    Argumets:
        iods_dict - IO domains info list including io domain
            info dict(name and password)
        root_domain_dict - Root domains info including name, password,
            operate_type and operate_count
    Return:
        2 - Unresolved
        1 - Fail
        0 - Success
    """
    log_dir = os.getenv("TMPPATH")
    status_changed = 0
    # status_changed = 0 : the status has not been changed
    # status_changed = 1 : the status has been changed to OFFLINE
    # status_changed = 2 : the status has been changed back to ONLINE
    vfs_hotplug_status_check_fail_after_interrupted = 0
    disk_or_io_check_fail_during_interrupted = 0
    disk_or_io_check_fail_after_interrupted = 0

    # Parse all_vfs_info from xml file
    all_vfs_info_xml = os.getenv("VFS_INFO")
    all_vfs_info_dict = parse_all_vfs_info_from_xml(all_vfs_info_xml)

    # Checkout the vfs which will be affected by the interrupted root
    # domains. These vfs are called test vfs
    test_vfs_info_dict = {}
    for root_domain_name in root_domain_dict.keys():
        each_rd_vfs_info_dict = {
            root_domain_name: all_vfs_info_dict[root_domain_name]}
        test_vfs_info_dict.update(each_rd_vfs_info_dict)
    info_report(test_vfs_info_dict)

    # Check whether this is a mix test with nic/fc/ib
    mix_flag = False
    for pfs_vfs_info in test_vfs_info_dict.values():
        for vfs_info in pfs_vfs_info.values():
            for vf_info in vfs_info.values():
                if vf_info["class"] != "FIBRECHANNEL":
                    mix_flag = True
                    break

    # Float case or multidom case, only check ior status after the
    # interruption of root domains.
    if len(root_domain_dict.keys()) > 1 or len(iods_dict.keys()) > 1:
        for iod_name in iods_dict.keys():
            name = iod_name
            password = iods_dict[iod_name]

            # Get all vfs info in io domain
            all_vfs_in_iod = {}
            for pfs_vfs_info in all_vfs_info_dict.values():
                for vfs_info in pfs_vfs_info.values():
                    for vf, vf_info in vfs_info.items():
                        if vf_info["io_domain"] == iod_name:
                            all_vfs_in_iod.update({vf: vf_info})

            info_report(
                "Getting all ior related information of io domain %s..." %
                name)
            ior_related_status = get_domain_ior_ralated_status(
                name,
                password,
                all_vfs_in_iod,
                log_dir)
            if check_domain_vfs_hotplug_status(
                    ior_related_status,
                    all_vfs_in_iod) == 1:
                error_print_report(
                    "VFs status in io domain %s are not all "
                    "back ONLINE after interruption of root domain:%s" %
                    (name, "Fail"))
                try:
                    output = get_domain_hotplug_info(name, password)
                except ReturnException as e:
                    warn_print_report(
                        "Failed to get hotplug list info after ior active:\n%s" %
                        e)
                else:
                    info_print_report(
                        "The status of the vf in the io domain %s:\n%s" %
                        (name, output))
                vfs_hotplug_status_check_fail_after_interrupted += 1
            else:
                info_print_report(
                    "VFs status in io domain %s are all "
                    "back ONLINE after interruption of root domain:%s" %
                    (name, "Pass"))
            if check_domain_disk_and_io(
                    name,
                    password,
                    ior_related_status,
                    root_domain_dict.keys(),
                    all_vfs_in_iod) == 1:
                error_print_report(
                    "Logical_path and I/O in io domain %s:%s" % (name, "Fail"))
                disk_or_io_check_fail_after_interrupted += 1
            else:
                info_print_report(
                    "Logical_path and I/O in io domain %s:%s" % (name, "Pass"))
        for root_domain in root_domain_dict.keys():
            if get_domain_status(root_domain) != 'active':
                error_print_report(
                    "Failed to boot root domain %s" % root_domain)
                return 2
        if vfs_hotplug_status_check_fail_after_interrupted != 0:
            if len(root_domain_dict.keys()) > 1:
                error_print_report("VFs in io domain are not changed back")
            else:
                error_print_report(
                    "VF in %s io domains are not changed back during %s %s" %
                    (vfs_hotplug_status_check_fail_after_interrupted,
                     root_domain_dict.values()[0]['operate_type'],
                     root_domain_dict.keys()[0]))
            return 1
        if disk_or_io_check_fail_after_interrupted != 0:
            if len(root_domain_dict.keys()) > 1:
                error_print_report("Disk or I/O workload failed in io domain")
            else:
                error_print_report(
                    "Disk or I/O workload failed in %s io domains after "
                    "VF change back" % disk_or_io_check_fail_after_interrupted)
            return 1
        return 0
    else:  # Check related status during interruption and post-interruption
        iod_name = iods_dict.keys()[0]
        iod_password = iods_dict[iod_name]
        root_domain_name = root_domain_dict.keys()[0]
        operate_type = root_domain_dict[root_domain_name].get('operate_type')
        operate_count = root_domain_dict[root_domain_name].get('operate_count')
        check_count = operate_count
        mix_offline_flag = False

        # Get all vfs info in io domain
        all_vfs_in_iod = {}
        for pfs_vfs_info in all_vfs_info_dict.values():
            for vfs_info in pfs_vfs_info.values():
                for vf, vf_info in vfs_info.items():
                    if vf_info["io_domain"] == iod_name:
                        all_vfs_in_iod.update({vf: vf_info})

        # Get the test vfs in io domain
        test_vfs_in_iod = {}
        fc_vfs_in_iod = {}
        nic_vfs_in_iod = {}
        ib_vfs_in_iod = {}
        for pfs_vfs in test_vfs_info_dict.values():
            for vfs_info in pfs_vfs.values():
                for vf, vf_info in vfs_info.items():
                    if vf_info["io_domain"] == iod_name:
                        test_vfs_in_iod.update({vf: vf_info})
                        if vf_info["class"] == "FIBRECHANNEL":
                            fc_vfs_in_iod.update({vf: vf_info})
                        elif vf_info["class"] == "NETWORK":
                            nic_vfs_in_iod.update({vf: vf_info})
                        else:
                            ib_vfs_in_iod.update({vf: vf_info})

        while event.isSet():
            # If the status has not change back to ONLINE,check the status
            if status_changed != 2:
                vfs_status_dict = get_domain_test_vfs_hotplug_status(
                    iod_name,
                    iod_password,
                    test_vfs_in_iod,
                    log_dir)
                # Just FC test, not with NIC/IB
                if not mix_flag:
                    status = get_domain_vfs_hotplug_status(
                        vfs_status_dict,
                        test_vfs_in_iod)
                    info_print_report(
                        "Root domain %s %sing:status of vf in io domain %s:%s" %
                        (root_domain_name, operate_type, iod_name, status))
                    if status_changed == 0:
                        if status == 'OFFLINE':
                            status_changed = 1
                            info_print_report(
                                "VF in io domain {0} changed to {1}".format(
                                    iod_name,
                                    status))
                            ior_related_status = get_domain_ior_ralated_status(
                                iod_name,
                                iod_password,
                                test_vfs_in_iod,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    test_vfs_in_iod) == 1:
                                info_print_report(
                                    "Logical_path and I/O in %s:%s" %
                                    (iod_name, "Fail"))
                                disk_or_io_check_fail_during_interrupted = 1
                            else:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Pass"))
                        elif re.search(r'(MAINTENANCE-SUSPENDED)', status):
                            status_changed = 1
                            info_print_report(
                                "VF in io domain {0} changed to {1}".format(
                                    iod_name,
                                    status))
                            ior_related_status = get_domain_ior_ralated_status(
                                iod_name,
                                iod_password,
                                test_vfs_in_iod,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    test_vfs_in_iod) == 1:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Fail"))
                                disk_or_io_check_fail_during_interrupted = 1
                            else:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Pass"))
                    # If the status has been changed to OFFLINE,expect it changes
                    # to ONLINE
                    else:
                        if status == 'ONLINE':
                            status_changed = 2
                            info_print_report(
                                "VF in io domain {0} changed back {1}".format(
                                    iod_name,
                                    status))
                            time.sleep(5)
                            ior_related_status = get_domain_ior_ralated_status(
                                iod_name,
                                iod_password,
                                all_vfs_in_iod,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    all_vfs_in_iod) == 1:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Fail"))
                                disk_or_io_check_fail_after_interrupted = 1
                            else:
                                info_print_report(
                                    "Logical_path and I/O in io domain [%s]:%s" %
                                    (iod_name, "Pass"))
                            # Check multiple times if interruption count is more
                            # than once
                            if check_count > 1:
                                status_changed = 0
                                check_count -= 1
                                time.sleep(15)
                                info_print_report(
                                    "Wait 15 seconds and begin the next loop test")
                            else:
                                info_print(
                                    "Waitting root domain %s boot up" %
                                    root_domain_name)
                                while event.isSet():
                                    time.sleep(1)
                        elif status == 'MIX-OFFLNE':
                            mix_offline_flag = True
                            info_print_report(
                                "VF in io domain {0} changed to {1}".format(
                                    iod_name,
                                    status))
                            ior_related_status = get_domain_ior_ralated_status(
                                iod_name,
                                iod_password,
                                all_vfs_in_iod,
                                log_dir)
                            if check_domain_vfs_hotplug_status(
                                    ior_related_status,
                                    all_vfs_in_iod) == 1:
                                info_print_report(
                                    "hotplug status in io domain %s:%s" %
                                    (iod_name, "Fail"))
                                vfs_hotplug_status_check_fail_after_interrupted = 1
                                # Wait the nprd boot up and could test panic case.
                                info_print(
                                    "Waitting root domain %s boot up" %
                                    root_domain_name)
                                while event.isSet():
                                    time.sleep(1)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    all_vfs_in_iod) == 1:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Fail"))
                                disk_or_io_check_fail_after_interrupted = 1
                                # Wait the nprd boot up and could test panic case.
                                info_print(
                                    "Waitting root domain %s boot up" %
                                    root_domain_name)
                                while event.isSet():
                                    time.sleep(1)
                            else:
                                info_print_report(
                                    "Logical_path and I/O in io domain %s:%s" %
                                    (iod_name, "Pass"))
                # Mix test with FC/NIC/IB test
                else:
                    nic_int_or_traffic_fail_during_interrupted = 0
                    ib_int_or_traffic_fail_during_interrupted = 0
                    nic_int_or_traffic_fail_after_interrupted = 0
                    ib_int_or_traffic_fail_after_interrupted = 0
                    status_changed_dict = {}
                    fc_status = None
                    nic_status = None
                    ib_status = None
                    if fc_vfs_in_iod:
                        fc_status = get_domain_vfs_hotplug_status(
                            vfs_status_dict,
                            fc_vfs_in_iod)
                        status_changed_dict.update({"fc_status": fc_status})
                    if nic_vfs_in_iod:
                        nic_status = get_domain_vfs_hotplug_status(
                            vfs_status_dict,
                            nic_vfs_in_iod)
                        status_changed_dict.update({"nic_status": nic_status})
                    if ib_vfs_in_iod:
                        ib_status = get_domain_vfs_hotplug_status(
                            vfs_status_dict,
                            ib_vfs_in_iod)
                        status_changed_dict.update({"ib_status": ib_status})
                    info_print_report(
                        "Root domain %s %sing: vfs status "
                        "in io domain %s: FC: %s|NIC: %s|IB: %s " % (
                            root_domain_name,
                            operate_type,
                            iod_name,
                            fc_status,
                            nic_status,
                            ib_status))

                    status_changed_correct = 0
                    if status_changed == 0:
                        for which_io, which_io_status in status_changed_dict.items():
                            if which_io == "fc_status":
                                if which_io_status == "OFFLINE":
                                    status_changed_correct += 1
                            if which_io == "nic_status" or which_io == "ib_status":
                                if which_io_status == "MAINTENANCE-SUSPENDED":
                                    status_changed_correct += 1
                        if status_changed_correct == len(status_changed_dict.keys()):
                            status_changed = 1
                            info_print_report(
                                "VFs status in io domain {0} changed: "
                                "FC:{1}|NIC:{2}|IB:{3}".format(
                                    iod_name,
                                    fc_status,
                                    nic_status,
                                    ib_status))
                            if fc_vfs_in_iod:
                                fc_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    fc_vfs_in_iod,
                                    log_dir)
                                if check_domain_disk_and_io(
                                        iod_name,
                                        iod_password,
                                        fc_ior_related_status,
                                        root_domain_dict.keys(),
                                        fc_vfs_in_iod) == 1:
                                    info_print_report(
                                        "Logical_path and I/O in %s:%s" %
                                        (iod_name, "Fail"))
                                    disk_or_io_check_fail_during_interrupted = 1
                                else:
                                    info_print_report(
                                        "Logical_path and I/O in io domain %s:%s" %
                                        (iod_name, "Pass"))
                            if nic_vfs_in_iod:
                                nic_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    nic_vfs_in_iod,
                                    log_dir)
                                if check_domain_interface_and_traffic(
                                        iod_name,
                                        iod_password,
                                        nic_ior_related_status,
                                        root_domain_dict.keys(),
                                        nic_vfs_in_iod) == 1:
                                    info_print_report(
                                        "NIC Interface state and traffic in %s:%s" %
                                        (iod_name, "Fail"))
                                    nic_int_or_traffic_fail_during_interrupted = 1
                                else:
                                    info_print_report(
                                        "NIC Interface state and traffic in %s:%s" %
                                        (iod_name, "Pass"))
                            if ib_vfs_in_iod:
                                ib_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    ib_vfs_in_iod,
                                    log_dir)
                                if check_domain_interface_and_traffic(
                                        iod_name,
                                        iod_password,
                                        ib_ior_related_status,
                                        root_domain_dict.keys(),
                                        ib_vfs_in_iod) == 1:
                                    info_print_report(
                                        "IB Interface state and traffic in %s:%s" %
                                        (iod_name, "Fail"))
                                    ib_int_or_traffic_fail_during_interrupted = 1
                                else:
                                    info_print_report(
                                        "IB Interface state and traffic in %s:%s" %
                                        (iod_name, "Pass"))
                    else:
                        for which_io, which_io_status in status_changed_dict.items():
                            if which_io_status == "ONLINE":
                                status_changed_correct += 1
                        if status_changed_correct == len(status_changed_dict.keys()):
                            status_changed = 2
                            info_print_report(
                                "VFs in io domain {0} changed back ONLINE".format(
                                    iod_name))
                            time.sleep(5)
                            if fc_vfs_in_iod:
                                fc_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    fc_vfs_in_iod,
                                    log_dir)
                                if check_domain_disk_and_io(
                                        iod_name,
                                        iod_password,
                                        fc_ior_related_status,
                                        root_domain_dict.keys(),
                                        fc_vfs_in_iod) == 1:
                                    info_print_report(
                                        "Logical_path and I/O in %s:%s" %
                                        (iod_name, "Fail"))
                                    disk_or_io_check_fail_during_interrupted = 1
                                else:
                                    info_print_report(
                                        "Logical_path and I/O in io domain %s:%s" %
                                        (iod_name, "Pass"))
                            if nic_vfs_in_iod:
                                nic_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    nic_vfs_in_iod,
                                    log_dir)
                                if check_domain_interface_and_traffic(
                                        iod_name,
                                        iod_password,
                                        nic_ior_related_status,
                                        root_domain_dict.keys(),
                                        nic_vfs_in_iod) == 1:
                                    info_print_report(
                                        "NIC Interface state and traffic in %s:%s" %
                                        (iod_name, "Fail"))
                                    nic_int_or_traffic_fail_after_interrupted = 1
                                else:
                                    info_print_report(
                                        "NIC Interface state and traffic in %s:%s" %
                                        (iod_name, "Pass"))
                            if ib_vfs_in_iod:
                                ib_ior_related_status = get_domain_ior_ralated_status(
                                    iod_name,
                                    iod_password,
                                    ib_vfs_in_iod,
                                    log_dir)
                                if check_domain_interface_and_traffic(
                                        iod_name,
                                        iod_password,
                                        ib_ior_related_status,
                                        root_domain_dict.keys(),
                                        ib_vfs_in_iod) == 1:
                                    info_print_report(
                                        "IB Interface state and traffic in %s:%s" %
                                        (iod_name, "Fail"))
                                    ib_int_or_traffic_fail_after_interrupted = 1
                                else:
                                    info_print_report(
                                        "IB Interface state and traffic in %s:%s" %
                                        (iod_name, "Pass"))
                            # Check multiple times if interruption count is more
                            # than once
                            if check_count > 1:
                                status_changed = 0
                                check_count -= 1
                                time.sleep(15)
                                info_print_report(
                                    "Wait 15 seconds and begin the next loop test")
                            else:
                                info_print(
                                    "Waitting root domain %s boot up" %
                                    root_domain_name)
                                while event.isSet():
                                    time.sleep(1)

            time.sleep(10)
        if get_domain_status(root_domain_name) != 'active':
            error_print_report(
                "Failed to boot root domain %s up in the ior test" %
                root_domain_name)
            return 2
        if status_changed == 0:
            error_print_report("VF in io domain %s is not changed during %s %s"
                               % (iod_name, operate_type, root_domain_name))
            try:
                output = get_domain_hotplug_info(iod_name, iod_password)
            except Exception as e:
                warn_print_report(
                    "Failed to get hotplug list info after ior active:\n%s" %
                    e)
            else:
                info_print_report(
                    "The status of the vf in the io domain:\n%s" %
                    output)
            return 1
        if status_changed == 1:
            status_not_changed_back_result = 1
            if mix_offline_flag:
                if vfs_hotplug_status_check_fail_after_interrupted == 1:
                    error_print_report(
                        "VF in io domain [%s] is not changed back during %s %s" %
                        (iod_name, operate_type, root_domain_name))
                else:
                    status_not_changed_back_result = 0
            else:
                error_print_report(
                    "VF in io domain [%s] is not changed back during %s [%s]" %
                    (iod_name, operate_type, root_domain_name))
                try:
                    output = get_domain_hotplug_info(iod_name, iod_password)
                except Exception as e:
                    warn_print_report(
                        "Failed to get hotplug list after ior active:\n%s" %
                        e)
                else:
                    info_print_report(
                        "The status of the vf in the io domain:\n%s" %
                        output)
            if status_not_changed_back_result != 0:
                return 1
        if not mix_flag:
            if disk_or_io_check_fail_during_interrupted == 1:
                error_print_report(
                    "Disk or I/O workload failed during root domain interrupted")
                return 1
            if disk_or_io_check_fail_after_interrupted == 1:
                error_print_report(
                    "Disk or I/O workload failed after VF change back ONLINE")
                return 1
        else:
            if fc_vfs_in_iod:
                if disk_or_io_check_fail_during_interrupted == 1:
                    error_print_report("Disk or I/O workload failed during "
                                       "root domain interrupted")
                    return 1
                if disk_or_io_check_fail_after_interrupted == 1:
                    error_print_report("Disk or I/O workload failed after VF"
                                       " change back ONLINE")
                    return 1
            if nic_vfs_in_iod:
                if nic_int_or_traffic_fail_during_interrupted == 1:
                    error_print_report("NIC interface or traffic check failed "
                                       "during root domain interrupted")
                    return 1
                if nic_int_or_traffic_fail_after_interrupted == 1:
                    error_print_report("NIC interface or traffic check failed"
                                       " after VF change back ONLINE")
                    return 1
            if ib_vfs_in_iod:
                if ib_int_or_traffic_fail_during_interrupted == 1:
                    error_print_report("IB interface or traffic check failed "
                                       "during root domain interrupted")
                    return 1
                if ib_int_or_traffic_fail_after_interrupted == 1:
                    error_print_report("IB interface or traffic check failed"
                                       " after VF change back ONLINE")
                    return 1
        return 0


def kill_run_io_process_in_domain(name, password):
    """
    Purpose:
        Kill the vdbench process in domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    check_run_io_process = "ps -ef|grep run_io.sh|grep -v grep"
    try:
        domain.sendcmd(check_run_io_process)
    except ExecuteException:
        info_report("No need to kill run_io.sh process")
    else:
        cmd = "ps -ef|grep run_io.sh|grep -v grep|awk '{print $2}'|xargs kill -9"
        domain.sendcmd(cmd)


def destroy_file_system_in_domain(name, password):
    """
    Purpose:
        Destroy the file system created on the raw disk in the domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = 'zpool status ior_pool'
    try:
        output = domain.retsend(cmd)
    except ReturnException:
        return 0
    if output.split(':')[1].strip() != 'ONLINE':
        cmd_clear = 'zpool clear ior_pool'
        domain.sendcmd(cmd_clear)
    cmd_list_fs = 'zfs list ior_pool/fs'
    try:
        domain.sendcmd(cmd_list_fs)
    except ExecuteException:
        pass
    else:
        cmd_destroy_fs = 'zfs destroy -f ior_pool/fs'
        domain.sendcmd(cmd_destroy_fs)
    cmd_destroy_pool = 'zpool destroy -f ior_pool'
    domain.sendcmd(cmd_destroy_pool)


def kill_vdbench_process_in_domain(name, password):
    """
    Purpose:
        Kill the vdbench process in domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    check_vdbench_process = "ps -ef|grep vdbench|grep -v grep"
    try:
        domain.sendcmd(check_vdbench_process)
    except ExecuteException:
        info_report("No need to kill vdbench process")
    else:
        cmd = "ps -ef|grep vdbench|grep -v grep|awk '{print $2}'|xargs kill -9"
        domain.sendcmd(cmd)


def kill_nic_ib_traffic_process_in_domain(name, password):
    """
    Purpose:
        Kill the nic or ib traffic process in domain
    Arguments:
        name - Domain name
        password - Domain password
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    check_run_traffic_process = "ps -ef|grep 'ping -s -R -r -v -i'|" \
                                "grep -v grep"
    try:
        domain.sendcmd(check_run_traffic_process)
    except ExecuteException:
        pass
    else:
        cmd = "ps -ef|grep 'ping -s -R -r -v -i'|grep -v grep|" \
              "awk '{print $2}'|xargs kill -9"
        domain.sendcmd(cmd)


def delete_nic_interface_in_domain(name, password, pfs):
    """
    Purpose:
        Delete the corresponding interface of the vf in domain
    Arguments:
        name - Domain name
        password - Domain password
        pfs - NIC pfs
    Return:
        None
    """
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)

    for pf in pfs:
        # Find all the vfs on pf
        cmd = "ldm list-io -p %s|grep type=VF|awk -F'|' '{print $3}'" % \
              pf
        output = execute(cmd)
        vfs_alias_str = re.findall(r'alias=.*', output)
        for vf_str in vfs_alias_str:
            vf = get_value_from_string(vf_str)
            # If vf has been bound to domain, need to deal with
            cmd = "ldm list-io -p|grep %s" % vf
            output = execute(cmd)
            bound_domain = get_value_from_string(output.split('|')[4])
            if bound_domain == name:
                interface = get_nic_vf_interface_in_domain(
                    name,
                    password,
                    vf)
                cmd = "ifconfig %s" % interface
                try:
                    domain.sendcmd(cmd)
                except ExecuteException:
                    continue
                else:
                    # If there is ipmp over this vf, unconfigure it
                    cmd = "ipadm |grep '%s '" % interface
                    output = domain.retsend(cmd)
                    if output.split()[3] != '--':
                        ipmp_group = output.split()[3]
                        unconfigure_nic_ipmp_in_domain(
                            name,
                            password,
                            ipmp_group)
                    else:
                        cmd = "ipadm delete-ip %s" % interface
                        domain.sendcmd(cmd)


def delete_remote_vnic(rmt_name, rmt_password):
    """
    Purpose:
        Delete the remote vnic created in remote host
    Arguments:
        name - Hostname or IP of the remote system
        password - Remote host password
        rmt_int - The remote nic interface
    Return:
        None
    """
    # Build host
    rmt_host = Host.Host(rmt_name, rmt_password)

    # Check whether $int_chkvnic0 exists, if yes, unplumb
    chkvnic = 'ior_chkvnic0'
    cmd = "ifconfig %s" % chkvnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd_unplumb = "ifconfig %s unplumb" % chkvnic
        rmt_host.send_command(cmd_unplumb)
    # Delete the existing $chkvnic
    cmd = "dladm show-vnic %s" % chkvnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "dladm delete-vnic %s" % chkvnic
        rmt_host.send_command(cmd)

    # Check whether $vnic exists, if yes, unplumb
    vnic = 'ior_vnic0'
    cmd = "ifconfig %s" % vnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd_unplumb = "ifconfig %s unplumb" % vnic
        rmt_host.send_command(cmd_unplumb)
    # Delete the existing $vnic
    cmd = "dladm show-vnic %s" % vnic
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "dladm delete-vnic %s" % vnic
        rmt_host.send_command(cmd)


def delete_ib_part_in_domain(name, password, pfs):
    """
    Purpose:
        Delete the corresponding interface of the vf in domain
    Arguments:
        name - Domain name
        password - Domain password
        pfs - IB pfs
    Return:
        None
    """
    for pf in pfs:
        # Find all the vfs on pf
        cmd = "ldm list-io -p %s|grep type=VF|awk -F'|' '{print $3}'" % \
              pf
        output = execute(cmd)
        vfs_alias_str = re.findall(r'alias=.*', output)
        for vf_str in vfs_alias_str:
            vf = get_value_from_string(vf_str)
            # If vf has been bound to domain, need to deal with
            cmd = "ldm list-io -p|grep %s" % vf
            output = execute(cmd)
            bound_domain = get_value_from_string(output.split('|')[4])
            if bound_domain == name:
                link = get_ib_vf_link_in_domain(name, password, vf)
                if link:
                    delete_parts_over_link_in_domain(
                        name,
                        password,
                        link)


def delete_remote_ib_part(rmt_name, rmt_password):
    """
    Purpose:
        Delete the remote ib link created in remote host
    Arguments:
        name - Hostname or IP of the remote system
        password - Remote host password
        rmt_link - The remote ib link
    Return:
        None
    """
    # Build host
    rmt_host = Host.Host(rmt_name, rmt_password)

    # Check whether $chkpart exists, if yes, unplumb
    chkpart = 'ior_chkpart0'
    cmd = "ifconfig %s" % chkpart
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ipadm delete-ip %s" % chkpart
        rmt_host.send_command(cmd)
    # Delete the existing $chkpart
    cmd = "dladm show-part %s" % chkpart
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "dladm delete-part %s" % chkpart
        rmt_host.send_command(cmd)

    # Check whether $ibpart exists, if yes, unplumb
    part = 'ior_part0'
    cmd = "ifconfig %s" % part
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "ipadm delete-ip %s" % part
        rmt_host.send_command(cmd)
    # Delete the existing $ibpart
    cmd = "dladm show-part %s" % part
    try:
        rmt_host.send_command(cmd)
    except ExecuteException:
        pass
    else:
        cmd = "dladm delete-part %s" % part
        rmt_host.send_command(cmd)


def create_path(path):
    """
    Purpose:
        Create a directory
    Arguments:
        path - The directory to be created
    Return:
        None
    """
    path = path.strip().rstrip("\\")
    flag = os.path.exists(path)
    if not flag:
        os.makedirs(path)


def save_related_logs(case):
    """
    Purpose:
        Save the logs created during the pexpect interaction with domain
        and the all_vfs_info_xml file
    Arguments:
        case - Different cases name
    Return:
        None
    """
    related_dir = os.getenv("CTI_LOGDIR") + "/related_logs"
    vfs_info_xml = os.getenv("VFS_INFO")
    interaction_log = os.getenv("INT_LOG")

    # Save the vfs_info_xml to the $CTI_LOGDIR
    target_vfs_info_xml = related_dir + '/' + case + '_vfs.xml'
    target_interaction_log = related_dir + '/' + case + '_interact.log'

    if not os.path.exists(related_dir):
        os.makedirs(related_dir)

    if os.path.isfile(vfs_info_xml):
        os.rename(vfs_info_xml, target_vfs_info_xml)

    if os.path.isfile(interaction_log):
        os.rename(interaction_log, target_interaction_log)

    if os.path.isfile(vfs_info_xml):
        os.remove(vfs_info_xml)

    if os.path.isfile(interaction_log):
        os.remove(interaction_log)


def delete_path(path):
    """
    Purpose:
        Remove the directory
    Arguments:
        path - The directory to remove
    Return:
        None
    """
    if os.path.exists(path):
        shutil.rmtree(path)
