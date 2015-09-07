#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#


import os
import threading
import Ldom
import time
import re
import commands
import shutil
import error
import xml.dom.minidom
import ctiutils


def info_print(string):
    print "INFO : %s" % string


def info_report(string):
    ctiutils.cti_report("%s" % string)


def info_print_report(string):
    info_print(string)
    info_report(string)


def error_print(string):
    print "ERROR: %s" % string


def error_report(string):
    ctiutils.cti_report("%s" % string)


def error_print_report(string):
    error_print(string)
    error_report(string)


def warn_print(string):
    print "WARN : %s" % string


def warn_report(string):
    ctiutils.cti_report("%s" % string)


def warn_print_report(string):
    warn_print(string)
    warn_report(string)


def get_value_from_string(string):
    """
    Purpose:
        get the value from a format string
        e.g. failure-policy=ignore
    Arguments:
        string -
    Return:
        value - the value in the string
    """
    value = string.split("=")[1].strip().rstrip('\r\n')
    return value


def execute(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        raise error.ExecuteException(
            "Execution of [%s] failed:\n%s" %
            (cmd, output))
    return output


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
    except error.ExecuteException:
        raise error.NoneException("%s doesn't exist" % ldm)


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
    except error.NoneException:
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
        except error.ExecuteException:
            return

    # Check and update "mpxio_disable=false" in Solaris11
    cmd = "sed -n '/^mpxio-disable=.*;$/p' /etc/driver/drv/fp.conf"
    output = iod.retsend_one_line(cmd)
    if re.search(r'no', output) is None:
        warn_print(
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
        except error.NoneException:
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
        except error.ExecuteException:
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
        except error.ExecuteException:
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
    if match is None:
        return None
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
    cmd = "ldm list-io|grep %s|grep -v %s" % (pcie, pcie)
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
            raise error.NoneException("%s does not exist" % ldom)

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
            try:
                remove_vf_from_domain(vf, domain)
            except Exception as e:
                raise e
            else:
                time.sleep(3)

    # Destroy all the vfs created under the pf
    cmd_destroy = 'ldm destroy-vf -n max %s' % pf
    execute(cmd_destroy)


def create_vf_in_dynamic_mode(pf):
    """
    Purpose:
        Create vf in dynamic mode: assign port-wwn and node_wwn dynamiclly
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
    if domain != '':
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
    vdbench_path = os.getenv("VDBENCH_PATH")
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
    except error.ExecuteException as e:
        return False
    else:
        return True


def configure_ip_of_domain(name, password, ip_addr):
    """
    Purpose:
        Configure the vnet of domain
    Arguments:
        name - domain name
        password - domain password
        ip_addr - IP address
    Return:
        None
    """
    need_delete_ip = False
    port = get_domain_port(name)
    domain = Ldom.Ldom(name, password, port)
    cmd = 'ipadm show-addr|grep net0/v4'
    try:
        domain.sendcmd(cmd)
    except error.ExecuteException as e:
        pass
    else:
        need_delete_ip = True

    if need_delete_ip:
        cmd_delete_ip = "ipadm delete-ip net0"
        domain.sendcmd(cmd_delete_ip)

    output1 = execute(cmd)
    primary_ip = output1.split()[3].split("/")[0]
    sub = primary_ip.split(
        '.')[0] + '.' + primary_ip.split('.')[1] + '.' + primary_ip.split('.')[2]

    if ip_addr is None:
        raise Exception(
            "The IP address provided is None, please check configuration file")
    if len(ip_addr.split('.')) != 4:
        raise Exception(
            "The IP address provided is %s, please correct in "
            "configuration file" % ip_addr)
    conf_sub = ip_addr.split(
        '.')[0] + '.' + ip_addr.split('.')[1] + '.' + ip_addr.split('.')[2]
    if conf_sub != sub:
        raise Exception(
            "The IP address [%s] provided can not be pingable from "
            "primary domain, check the configuration file" % ip_addr)

    cmd_create_ip = "ipadm create-ip net0"
    domain.sendcmd(cmd_create_ip)
    cmd_create_addr = "ipadm create-addr -T static -a %s/24 net0/v4" % ip_addr
    domain.sendcmd(cmd_create_addr)
    cmd_check_route = "netstat -rn | grep default"
    try:
        output_check_route = domain.retsend_one_line(cmd_check_route)
    except error.ReturnException as e:
        cmd_add_route = "route add default %s.1" % sub
        domain.sendcmd(cmd_add_route)
    else:
        add_default_route = sub + '.1'
        if output_check_route.split()[1] != add_default_route:
            cmd_delete_route = "route delete default %s" % \
                               output_check_route.split()[1]
            domain.sendcmd(cmd_delete_route, check=False)
            cmd_add_route = "route add default %s.1" % sub
            domain.sendcmd(cmd_add_route)
    time.sleep(5)
    if not check_domain_pingable(name, password):
        raise Exception("Failed to get %s be pingable" % name)


def distribute_vdbench_files_to_domain(iod_name, iod_password, ip_addr):
    """
    Purpose:
        Distribute the vdbench I/O workload files to the domain
    Arguments:
        iod - IO domain name
    Return:
        None
    """
    if not check_domain_pingable(iod_name, iod_password):
        info_report(
            "%s is not pingable, trying to configure ip of vnet in the domain")
        configure_ip_of_domain(iod_name, iod_password, ip_addr)
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    cmd = 'echo "+ +" >> ~/.rhosts'
    iod.sendcmd(cmd)
    cmd1 = " svcadm enable -r -s svc:/network/shell:default"
    iod.sendcmd(cmd1)
    time.sleep(3)
    vdbench_path = "/export/home/vdbench"
    cmd2 = 'rcp -r {0} root@{1}:{2}'.format(
        vdbench_path,
        ip_addr,
        vdbench_path)
    execute(cmd2)
    time.sleep(3)
    cmd3 = 'test -d %s' % vdbench_path
    try:
        iod.sendcmd(cmd3)
    except error.ExecuteException as e:
        raise Exception(
            "Failed to distribuite vdbench file to domain [%s]" % iod_name)
    cmd3 = 'svcadm disable svc:/network/shell:default'
    execute(cmd3)
    cmd4 = 'rm ~/.rhosts'
    iod.sendcmd(cmd4)
    cmd5 = 'ipadm delete-ip net0'
    iod.sendcmd(cmd5)


def distribute_io_workload_files_to_domain(iod_name, iod_password):
    """
    Purpose:
        Distribute the I/O workload files to the domain
    Arguments:
        iod - IO domain name
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

    port = hotplug_dev.split('@')[1]
    hotplug_port = 'pci.' + port
    return hotplug_port


def save_init_vfs_info_to_xml(vfs_dict, logfile):
    """
    Purpose:
        Save the information of vfs created in startup phase
        to a xml file
    Arguments:
        vfs_dict - The vfs which will be used
        logfile - Where the info to be saved
    Return:
        None
    """
    pf_info_dict = {}
    vf_info_dict = {}
    for pf, vfs_list in vfs_dict.items():
        for vf in vfs_list:
            hotplug_dev = get_vf_hotplug_dev(vf)
            hotplug_path = get_vf_hotplug_path(vf)
            hotplug_port = get_vf_hotplug_port(vf)
            port_wwn = get_vf_port_wwn(vf)
            info_item = {
                "port_wwn": port_wwn,
                "hotplug_dev": hotplug_dev,
                "hotplug_path": hotplug_path,
                "hotplug_port": hotplug_port
            }
            vf_info_dict.update({vf: info_item})
        pf_info_dict.update({pf: vf_info_dict})

    impl = xml.dom.minidom.getDOMImplementation()
    dom = impl.createDocument(None, 'PFs', None)
    root = dom.documentElement

    for pf, vf_info_dict in pf_info_dict.items():
        pf_element = dom.createElement('PF')
        pf_element.setAttribute('alias', pf)
        pf_class = get_pf_class(pf)
        pf_element.setAttribute('class', pf_class)
        root.appendChild(pf_element)

        for vf, info_item in vf_info_dict.items():
            vf_element = dom.createElement('VF')

            vf_element.setAttribute('alias', vf)
            vf_element.setAttribute('class', pf_class)
            pf_element.appendChild(vf_element)

            wwn_element = dom.createElement('port_wwn')
            port_wwn = info_item['port_wwn']
            wwn_text = dom.createTextNode(port_wwn)
            wwn_element.appendChild(wwn_text)
            vf_element.appendChild(wwn_element)

            dev_element = dom.createElement('hotplug_dev')
            hotplug_dev = info_item['hotplug_dev']
            dev_text = dom.createTextNode(hotplug_dev)
            dev_element.appendChild(dev_text)
            vf_element.appendChild(dev_element)

            path_element = dom.createElement('hotplug_path')
            hotplug_path = info_item['hotplug_path']
            path_text = dom.createTextNode(hotplug_path)
            path_element.appendChild(path_text)
            vf_element.appendChild(path_element)

            port_element = dom.createElement('hotplug_port')
            hotplug_port = info_item['hotplug_port']
            port_text = dom.createTextNode(hotplug_port)
            port_element.appendChild(port_text)
            vf_element.appendChild(port_element)

    f = open(logfile, 'a')
    dom.writexml(f, addindent='  ', newl='\n')
    f.close()


def parse_init_vfs_from_xml(init_vfs_info_xml):
    """
    Purpose:
        Parse the information of vfs created in startup phase
        from a xml file
    Arguments:
        init_vfs_info_xml - Where the info to be parsed
    Return:
        init_vfs_info_dict
    """
    init_vfs_info_dict = {}
    DOMTree = xml.dom.minidom.parse(init_vfs_info_xml)
    pfs_root = DOMTree.documentElement
    pfs = pfs_root.getElementsByTagName("PF")

    each_pf_vfs_info_dict = {}
    for pf in pfs:
        pf_alias = pf.getAttribute("alias")
        pf_class = pf.getAttribute("class")

        vfs = pf.getElementByTagName("VF")
        for vf in vfs:
            vf_alias = vf.getAttribute("alias")
            vf_class = vf.getAttribute("class")
            port_wwn_ele = vf.getElementByTagName("port_wwn")[0]
            port_wwn = port_wwn_ele.childNodes[0].nodeValue
            hotplug_dev_ele = vf.getElementByTagName("hotplug_dev")[0]
            hotplug_dev = hotplug_dev_ele.childNodes[0].nodeValue
            hotplug_path_ele = vf.getElementByTagName("hotplug_path")[0]
            hotplug_path = hotplug_path_ele.childNodes[0].nodeValue
            hotplug_port_ele = vf.getElementByTagName("hotplug_port")[0]
            hotplug_port = hotplug_port_ele.childNodes[0].nodeValue
            vf_info_dict = {
                "class": vf_class,
                "port_wwn": port_wwn,
                "hotplug_dev": hotplug_dev,
                "hotplug_path": hotplug_path,
                "hotplug_port": hotplug_port,
            }
            each_pf_vfs_info_dict.update({vf_alias: vf_info_dict})
        init_vfs_info_dict.update({pf_alias: each_pf_vfs_info_dict})

    return init_vfs_info_dict


def save_test_vfs_info_to_xml(test_vfs_info_dict, test_vfs_info_xml):
    """
    Purpose:
        Save the information of test vfs to a xml file
    Arguments:
        test_vfs_info_dict - The vfs information
        test_vfs_info_xml - Where the info to be saved
    Return:
        None
    """
    impl = xml.dom.minidom.getDOMImplementation()
    dom = impl.createDocument(None, 'NPRDs', None)
    root = dom.documentElement

    for nprd, rd_pfs_vfs_dict in test_vfs_info_dict.items():
        nprd_element = dom.createElement('NPRD')
        nprd_element.setAttribute('name', nprd)
        root.appendChild(nprd_element)

        for pf, pf_vfs_dict in rd_pfs_vfs_dict:
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

                for each_vf_key,each_vf_value in info_item.items():
                    each_vf_ele = dom.createElement(each_vf_key)
                    each_vf_text = each_vf_value
                    each_vf_ele.appendChild(each_vf_text)
                    vf_element.appendChild(each_vf_ele)

            '''
            for vf, info_item in pf_vfs_dict.items():
                vf_element = dom.createElement('VF')
                vf_element.setAttribute('alias', vf)
                pf_element.appendChild(vf_element)

                dev_element = dom.createElement('hotplug_dev')
                hotplug_dev = info_item['hotplug_dev']
                dev_text = dom.createTextNode(hotplug_dev)
                dev_element.appendChild(dev_text)
                vf_element.appendChild(dev_element)

                path_element = dom.createElement('hotplug_path')
                hotplug_path = info_item['hotplug_path']
                path_text = dom.createTextNode(hotplug_path)
                path_element.appendChild(path_text)
                vf_element.appendChild(path_element)

                port_element = dom.createElement('hotplug_port')
                hotplug_port = info_item['hotplug_port']
                port_text = dom.createTextNode(hotplug_port)
                port_element.appendChild(port_text)
                vf_element.appendChild(port_element)

                status_element = dom.createElement('hotplug_status')
                hotplug_status = info_item['hotplug_status']
                status_text = dom.createTextNode(hotplug_status)
                status_element.appendChild(status_text)
                vf_element.appendChild(status_element)

                vf_class = info_item['class']
                if vf_class == 'FIBRECHANNEL':
                    wwn_element = dom.createElement('port_wwn')
                    port_wwn = info_item['port_wwn']
                    wwn_text = dom.createTextNode(port_wwn)
                    wwn_element.appendChild(wwn_text)
                    vf_element.appendChild(wwn_element)

                    logical_element = dom.createElement('logical_path')
                    logical_path = info_item['logical_path']
                    logical_text = dom.createTextNode(logical_path)
                    logical_element.appendChild(logical_text)
                    vf_element.appendChild(logical_element)

                    mpxio_element = dom.createElement('mpxio_flag')
                    mpxio_flag = info_item['mpxio_flag']
                    mpxio_text = dom.createTextNode(mpxio_flag)
                    mpxio_element.appendChild(mpxio_text)
                    vf_element.appendChild(mpxio_element)

                    io_element = dom.createElement('io_state')
                    io_state = info_item['io_state']
                    io_text = dom.createTextNode(io_state)
                    io_element.appendChild(io_text)
                    vf_element.appendChild(io_element)
                elif pf_class == 'INFINIBAND':
                    pass
                else:
                    pass
                '''

    f = open(test_vfs_info_xml, 'a')
    dom.writexml(f, addindent='  ', newl='\n')
    f.close()


def add_test_vfs_info(iod_info_dict, test_vfs_dict, test_vfs_info_xml):
    """
    Purpose:
        Get all test vfs information and save to a xml file
    Arguments:
        iod_info_dict - IO domain dict, including iod_name and iod_password
            e.g. ["fc_iod1":"nqa123"]
        test_vfs_dict - The vfs which will be tested
            e.g.
            {
                "fc-nprd1": {
                    "/SYS/MB/PCIE2/IOVFC.PF1.PF0":[
                        "/SYS/MB/PCIE2/IOVFC.PF1.PF0.VF0",
                        "/SYS/MB/PCIE2/IOVFC.PF1.PF0.VF1",
                        "/SYS/MB/PCIE2/IOVFC.PF1.PF0.VF2"
                    ]
                "/SYS/MB/PCIE7/IOVFC.PF1.PF0":[
                        "/SYS/MB/PCIE7/IOVFC.PF1.PF0.VF0",
                        "/SYS/MB/PCIE7/IOVFC.PF1.PF0.VF1",
                        "/SYS/MB/PCIE7/IOVFC.PF1.PF0.VF2"
                    ]
                }
            }
        test_vfs_info_xml - The xml file where to save the vfs information
    Return:
        None
    """
    # Get the vfs_info.xml file which be saved in test_startup phase
    init_vfs_info_xml = os.getenv("INIT_VFS")
    path = os.getenv("TMPPATH")

    iod_name = iod_info_dict.get('name')
    iod_port = get_domain_port(iod_name)
    iod_password = iod_info_dict.get('password')
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    hotplug_logfile = iod.save_hotplug_log(path)

    # Get the initial vfs info from xml file
    init_vfs_info_dict = parse_init_vfs_from_xml(init_vfs_info_xml)

    # Get all the test vfs information
    test_vfs_info_dict = {}
    for nprd, pf_vfs in test_vfs_dict.items():
        each_pf_vfs_dict = {}
        for pf, vfs_iod_dict in pf_vfs.items():
            each_vfs_dict = {}
            pf_class = get_pf_class(pf)
            for vf, domain in vfs_iod_dict.items():
                each_vf_info_dict = {}
                if pf_class == 'FIBRECHANNEL':
                    if init_vfs_info_dict[pf][vf]:
                        each_vf_info_dict = init_vfs_info_dict[pf][vf]
                        if domain == iod_name:
                            hotplug_status = iod.get_vf_hotplug_status(
                                vf,
                                hotplug_logfile)
                            logical_path = iod.get_vf_logical_path(vf)
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
                            io_state = new_iod.check_vf_io_workload_on(vf)
                    else:
                        port_wwn = get_vf_port_wwn(vf)
                        hotplug_dev = get_vf_hotplug_dev(vf)
                        hotplug_path = get_vf_hotplug_path(vf)
                        hotplug_port = get_vf_hotplug_port(vf)
                        if domain == iod_name:
                            hotplug_status = iod.get_vf_hotplug_status(
                                vf,
                                hotplug_logfile)
                            logical_path = iod.get_vf_logical_path(vf)
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
                            io_state = new_iod.check_vf_io_workload_on(vf)
                        each_vf_info_dict.update(
                            {"port_wwn": port_wwn})
                        each_vf_info_dict.update(
                            {"hotplug_dev": hotplug_dev})
                        each_vf_info_dict.update(
                            {"hotplug_path": hotplug_path})
                        each_vf_info_dict.update(
                            {"hotplug_port": hotplug_port})
                    each_vf_info_dict.update(
                        {"io_domain": domain})
                    each_vf_info_dict.update(
                        {"hotplug_status": hotplug_status})
                    each_vf_info_dict.update(
                        {"logical_path": logical_path})
                    each_vf_info_dict.update(
                        {"io_state": io_state})
                    each_vf_info_dict.update(
                        {"class": pf_class})
                elif pf_class == 'NETWORK':
                    pass
                else:
                    pass
                each_vfs_dict.update({vf: each_vf_info_dict})
            each_pf_vfs_dict.update({pf: each_vfs_dict})
        test_vfs_info_dict.update({nprd: each_pf_vfs_dict})

    # If test_vfs_info_log exists, delete it.
    if os.path.isfile(test_vfs_info_xml):
        os.remove(test_vfs_info_xml)
    # Save to the test_vfs_info_log xml file
    save_test_vfs_info_to_xml(test_vfs_info_dict, test_vfs_info_dict)


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


def parse_test_vfs_info_from_xml(test_vfs_info_xml):
    """
    Purpose:
        Parse the information of test vfs from a xml file
    Arguments:
        test_vfs_info_xml - Where the info to be parsed
    Return:
        test_vfs_info_dict
    """
    test_vfs_info_dict = {}
    DOMTree = xml.dom.minidom.parse(test_vfs_info_xml)
    root = DOMTree.documentElement
    nprds = root.getElementsByTagName("NPRD")

    each_nprd_pfs_vfs_dict = {}
    for nprd_ele in nprds:
        nprd = nprd_ele.getAttribute("name")
        pfs = nprd_ele.getElementByTagName("PF")

        each_pf_vfs_dict = {}
        for pf in pfs:
            pf_alias = pf.getAttribute("alias")
            pf_class = pf.getAttribute("class")
            vfs = pf.getElementByTagName("VF")

            each_vf_info_dict = {}
            for vf in vfs:
                vf_alias = vf.getAttribute("alias")
                vf_class = vf.getAttribute("class")

                io_domain_ele = vf.getElementByTagName("io_domain")[0]
                io_domain = io_domain_ele.childNodes[0].nodeValue
                hotplug_dev_ele = vf.getElementByTagName("hotplug_dev")[0]
                hotplug_dev = hotplug_dev_ele.childNodes[0].nodeValue
                hotplug_path_ele = vf.getElementByTagName("hotplug_path")[0]
                hotplug_path = hotplug_path_ele.childNodes[0].nodeValue
                hotplug_port_ele = vf.getElementByTagName("hotplug_port")[0]
                hotplug_port = hotplug_port_ele.childNodes[0].nodeValue
                hotplug_status_ele = vf.getElementByTagName("hotplug_status")[0]
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
                    port_wwn_ele = vf.getElementByTagName("port_wwn")[0]
                    port_wwn = port_wwn_ele.childNodes[0].nodeValue
                    logical_path_ele = vf.getElementByTagName("logical_path")[0]
                    logical_path = logical_path_ele.childNodes[0].nodeValue
                    mpxio_flag_ele = vf.getElementByTagName("mpxio_flag")[0]
                    mpxio_flag = mpxio_flag_ele.childNodes[0].nodeValue
                    io_state_ele = vf.getElementByTagName("io_state")[0]
                    io_state = io_state_ele.childNodes[0].nodeValue
                    info_dict.update({"port_wwn": port_wwn})
                    info_dict.update({"logical_path": logical_path})
                    info_dict.update({"mpxio_flag": mpxio_flag})
                    info_dict.update({"io_statue": io_state})
                elif pf_alias == 'NETWORK':
                    pass
                else:
                    pass

                each_vf_info_dict.update({vf_alias: info_dict})
            each_pf_vfs_dict.update({pf_alias: each_vf_info_dict})
        each_nprd_pfs_vfs_dict.update({nprd: each_pf_vfs_dict})
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


def get_domain_all_vfs_status(
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
        e.g. {"/SYS/MB/PCIE2/IOVFC.PF1.VF0": {'hotplug_status': ONLINE}
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
        test_vfs_in_iod,
        log_dir):
    """
    Purpose:
        Get all the VFs information including hotplug_status,fc port,
        logical path in domain
    Arguments:
        iod_name - Domain name
        iod_password - Domain password
        test_vfs_in_iod - The test vfs in the domain
        log_dir - Where to record the output of "hotplug list lv"
    Return:
        vfs_related_status_dict - All the VFs related information
        format: {"VF":(hotplug_status,port_exists,logical_path_alive)
                "VF":(.....)}
        e.g. {"/SYS/MB/PCIE2/IOVFC.PF1.VF0":(ONLINE,True,True)}
    """
    iod_port = get_domain_port(iod_name)
    iod = Ldom.Ldom(iod_name, iod_password, iod_port)
    vfs_related_status_dict = {}

    # Save the related info in io domain by sending "hotplug list -lv"
    # "fcinfo hba-port|grep HBA" and "mpathadm list lu"
    hotplug_logfile = iod.save_hotplug_log(log_dir)
    fcinfo_logfile = iod.save_fcinfo_log(log_dir)
    path_logfile = iod.save_path_log(log_dir)

    # Parse and get the related info from the logfile
    for vf, vf_info in test_vfs_in_iod.items():
        hotplug_path = vf_info["hotplug_path"]
        hotplug_port = vf_info["hotplug_port"]
        port_wwn = vf_info["port_wwn"]
        logical_path = vf_info["logical_path"]
        hotplug_status = iod.get_vf_hotplug_status_by_path_port(
            hotplug_path,
            hotplug_port,
            hotplug_logfile)  # Status: ONLINE, OFFLINE or others
        port_whether_found = iod.check_vf_port_wwn_status(
            port_wwn,
            fcinfo_logfile)  # True or False
        logical_path_whether_found = iod.check_vf_logical_path_status(
            logical_path,
            path_logfile)  # True or False
        item_dict = {
            vf: [
                hotplug_status,
                port_whether_found,
                logical_path_whether_found]}  # Build the dict to return
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
    hotplug_status = 'ONLINE'

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
        if ior_related_status[vf][0] != test_vfs_in_iod_name.get(
                vf).get("hotplug_status"):
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
            if test_vfs_in_iod.get(vf).get("logical_path") is None:
                if ior_related_status.get(vf)[2]:  # Found a logical path: Fail
                    info_report("VF [%s] logical_path check results:Fail" % vf)
                    status += 1
                else:  # No logical path found: Pass
                    info_report("VF [%s] logical_path check results:Pass" % vf)
            else:
                # No logical path found: Fail
                if ior_related_status.get(vf)[2]:
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

        for vf, vf_info in test_vfs_in_iod.keys():
            # If VF status is not ONLINE or OFFLINE, no need to check: Fail
            if ior_related_status.get(vf)[0] not in normal_status:
                status = 1
                break

            # This vf and another vf are multipath configured
            if vf_info.get("mpxio_flag"):
                # Found mapping logical path: Pass
                if ior_related_status.get(vf)[2]:
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
                if ior_related_status.get(vf)[0] == normal_status[0]:
                    # No mapping logical path before root domain be interrupted
                    if vf_info.get("logical_path") is None:
                        # Found mapping logical path: Fail
                        if ior_related_status.get(vf)[2]:
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
                        if ior_related_status.get(vf)[2]:
                            info_report(
                                "VF [%s] logical_path check results:Pass" % vf)
                        else:  # No logical path found : Fail
                            info_report(
                                "VF [%s] logical_path check results:Fail" % vf)
                            status += 1
                else:  # VF status is 'OFFLINE'
                    # Found mapping logical path: Fail
                    if ior_related_status.get(vf)[2]:
                        info_report(
                            "VF [%s] logical_path check results:Fail" % vf)
                        status += 1
    if status > 0:
        status = 1
    return status


def check_ior_in_domain(iods_dict, root_domain_dict, test_vfs_info_xml, event):
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

    # Parse the test_vfs_info from xml file
    test_vfs_info_dict = parse_test_vfs_info_from_xml(test_vfs_info_xml)
    mix_flag = False
    # Check whether this is a mix test with nic/fc/ib
    for each_pf_vfs in test_vfs_info_dict.values():
        for vf, each_vf_info in each_pf_vfs.items():
            if each_vf_info["class"] == "NETWORK":
                mix_flag = True
                break

    # Float case or multidom case, only check ior status after the
    # interruption of root domains.
    if len(root_domain_dict.keys()) > 1 or len(iods_dict.keys()) > 1:
        for iod_name in iods_dict.keys():
            name = iod_name
            password = iods_dict[iod_name]

            # Get the  test vfs in iod_name
            test_vfs_in_iod_name = {}
            for each_pf_vfs in test_vfs_info_dict.values():
                for vf, each_vf_info in each_pf_vfs.items():
                    if each_vf_info["io_domain"] == iod_name:
                        test_vfs_in_iod_name.update({vf, each_vf_info})

            info_report(
                "Getting all ior related information of io domain %s..." %
                name)
            ior_related_status = get_domain_ior_ralated_status(
                name,
                password,
                test_vfs_in_iod_name,
                log_dir)
            if check_domain_vfs_hotplug_status(
                    ior_related_status,
                    test_vfs_in_iod_name) == 1:
                error_print_report(
                    "VFs status in io domain %s are not all "
                    "back ONLINE after interruption of root domain:%s" %
                    (name, "Fail"))
                try:
                    output = get_domain_hotplug_info(name, password)
                except error.ReturnException as e:
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
                    test_vfs_in_iod_name) == 1:
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
                error_print_report(
                    "VF in %s are not changed back during %s %s" %
                    (vfs_hotplug_status_check_fail_after_interrupted,
                     root_domain_dict[root_domain], root_domain))
                return 1
            if disk_or_io_check_fail_after_interrupted != 0:
                error_print_report(
                    "Disk or I/O workload failed in %s io domains after "
                    "VF change back" % disk_or_io_check_fail_after_interrupted)
                return 1
        return 0
    else:  # Check related status during interruption and post-interruption
        iod_name = iods_dict.keys()[0]
        iod_password = iods_dict[iod_name]
        iod_port = get_domain_port(iod_name)
        root_domain_name = root_domain_dict.keys()[0]
        operate_type = root_domain_dict[root_domain_name].get('operate_type')
        operate_count = root_domain_dict[root_domain_name].get('opeate_count')
        check_count = operate_count
        mix_offline_flag = False

        # Get the  test vfs in iod_name
        test_vfs_in_iod_name = {}
        fc_vfs_in_iod_name = {}
        nic_vfs_in_iod_name = {}
        ib_vfs_in_iod_name = {}
        for each_pf_vfs in test_vfs_info_dict.values():
            for vf, each_vf_info in each_pf_vfs.items():
                if each_vf_info["io_domain"] == iod_name:
                    test_vfs_in_iod_name.update({vf: each_vf_info})
                    if each_vf_info["class"] == "FIBRECHANNEL":
                        fc_vfs_in_iod_name.update({vf: each_vf_info})
                    elif each_vf_info["class"] == "NETWORK":
                        nic_vfs_in_iod_name.update({vf: each_vf_info})
                    else:
                        ib_vfs_in_iod_name.update({vf: each_vf_info})

        while event.isSet():
            # If the status has not change back to ONLINE,check the status
            if status_changed != 2:
                vfs_status_dict = get_domain_all_vfs_status(
                    iod_name,
                    iod_password,
                    test_vfs_in_iod_name,
                    log_dir)
                # Just FC test, not with NIC/IB
                if not mix_flag:
                    status = get_domain_vfs_hotplug_status(
                        vfs_status_dict,
                        test_vfs_in_iod_name)
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
                                test_vfs_in_iod_name,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    test_vfs_in_iod_name) == 1:
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
                                test_vfs_in_iod_name,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    test_vfs_in_iod_name) == 1:
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
                                test_vfs_in_iod_name,
                                log_dir)
                            if check_domain_disk_and_io(
                                    iod_name,
                                    iod_password,
                                    ior_related_status,
                                    root_domain_dict.keys(),
                                    test_vfs_in_iod_name) == 1:
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
                                test_vfs_in_iod_name,
                                log_dir)
                            if check_domain_vfs_hotplug_status(
                                    ior_related_status,
                                    test_vfs_in_iod_name) == 1:
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
                                    test_vfs_in_iod_name) == 1:
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
                    pass

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
            if operate_type == 'reboot':
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
        if disk_or_io_check_fail_during_interrupted == 1:
            error_print_report(
                "Disk or I/O workload failed during root domain interrupted")
            return 1
        if disk_or_io_check_fail_after_interrupted == 1:
            error_print_report(
                "Disk or I/O workload failed after VF change back ONLINE")
            return 1
        return 0


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
    except error.ReturnException:
        return 0
    if output.split(':')[1].strip() != 'ONLINE':
        cmd_clear = 'zpool clear ior_pool'
        domain.sendcmd(cmd_clear)
    cmd_list_fs = 'zfs list ior_pool/fs'
    try:
        domain.sendcmd(cmd_list_fs)
    except error.ExecuteException:
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
    except error.ExecuteException:
        info_report("No need to kill vdbench process")
    else:
        cmd = "ps -ef|grep vdbench|grep -v grep|awk '{print $2}'|xargs kill -9"
        domain.sendcmd(cmd)


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


def save_pexpect_interaction_logfile(target_name):
    """
    Purpose:
        Save the logs created during the pexpect interaction with domain
    Arguments:
        target_name - This could be reviewed by the tester to check the
            interaction during IOR test
    Return:
        None
    """
    source = os.getenv("INT_LOG")
    target = target_name
    cmd = 'mv {0} {1}'.format(source, target)
    execute(cmd)


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
