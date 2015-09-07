#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import os
import time
import re
import commands


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
        pattern = re.compile(r'VDISK.*')
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
                    r'^{0}$'.format(disk_volume), vol)
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
        all_vd_services = execute(cmd_get_disk_service)
        pattern = re.compile(r'{0}.*'.format(disk_volume))
        all_vdsdev_list = pattern.findall(all_vd_services)
        for vdsdev_info in all_vdsdev_list:
            vol = vdsdev_info.split("|")[0]
            match_vdsdev_volume = re.match(r'^{0}$'.format(disk_volume), vol)
            if match_vdsdev_volume is not None:
                match_vdsdev_info = vdsdev_info
                break
        source_volume.append(
            match_vdsdev_info.split("|")[2].lstrip("dev=/dev/zvol/dsk/"))
    return source_volume


def destroy_domain(*ldom_list):
    '''
    Purpose:
        Destroy domains
    Arguments:
        *ldom_list - Domains to destroy
    Return:
        None
    '''
    for ldom in ldom_list:
        print "Destroying domain %s..." % ldom
        cmd_get_domain_status = 'ldm list {0}|grep {1}'.format(ldom, ldom)
        domain_status = execute(cmd_get_domain_status).split()[1]
        cmd_stop = 'ldm stop -f %s' % ldom
        cmd_unbind = 'ldm unbind %s' % ldom

        domain_cpu = execute(cmd_get_domain_status).split()[4].strip()
        cmd_remove_vcpu = 'ldm remove-vcpu %s %s' % (domain_cpu, ldom)

        domain_memory = execute(cmd_get_domain_status).split()[5].strip()
        cmd_remove_memory = 'ldm remove-memory %s %s' % (domain_memory, ldom)

        cmd_get_domain_vnet = 'ldm list-bindings -p %s|grep VNET' % ldom
        domain_vnet = execute(cmd_get_domain_vnet).split(
            '|')[1].split('=')[1].strip()
        cmd_remove_vnet = 'ldm remove-vnet {0} {1}'.format(domain_vnet, ldom)

        cmd_get_domain_vdisk = 'ldm list-bindings -p %s|grep VDISK' % ldom
        domain_vdisk = execute(cmd_get_domain_vdisk).split(
            '|')[1].split('=')[1].strip()
        cmd_remove_vdisk = 'ldm remove-vdisk {0} {1}'.format(
            domain_vdisk,
            ldom)

        cmd_get_domain_vds = "ldm list-services -p|grep VDS|awk -F'|' '{print $2}'"
        vds = execute(cmd_get_domain_vds).split("=")[1]
        cmd_remove_vdsdev = 'ldm remove-vdsdev {0}@{1}'.format(ldom, vds)

        cmd_destroy = 'ldm destroy %s' % ldom

        cmd_get_domain_vol = 'ldm list-bindings -p %s|grep VDISK' % ldom
        domain_vol = execute(cmd_get_domain_vol).split(
            '|')[2].split('@')[0].strip()
        cmd_get_domain_zfs = 'ldm list-services -p|grep %s' % domain_vol
        domain_zfs = 'rpool/' + \
            execute(cmd_get_domain_zfs).split('|')[3].split('=')[1].split('/')[5]
        cmd_destroy_volume = 'zfs destroy %s' % domain_zfs

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
        if domain_status != 'bound':
            pass
        else:
            cmd_destroy_domain_list.pop(0)
        for cmd in cmd_destroy_domain_list:
            execute(cmd)
        print "Done"


def check_domain_exists(ldom):
    cmd = 'ldm list %s' % ldom
    execute(cmd)


def main():
    source_domain_name = os.getenv("SOURCE_DOMAIN")
    root_domain_1_name = os.getenv("NPRD_A")
    root_domain_2_name = os.getenv("NPRD_B")
    io_domain_name = os.getenv("IOD")

    domain_list = [root_domain_1_name, root_domain_2_name]
    for ldom in domain_list:
        # Check the domain whether exists
        try:
            check_domain_exists(ldom)
        except Exception as e:
            print e
            continue
        cmd_get_bus = "ldm list-io|grep %s|grep BUS" % ldom
        try:
            ldom_bus = execute(cmd_get_bus).split()[0]
        except Exception:
            pass
        else:
            cmd_get_vfs = "ldm list-io|grep %s|grep '\.VF.*'|awk '{print $1}'" % \
                          ldom_bus
            try:
                vfs_string = execute(cmd_get_vfs)
            except Exception:
                pass
            else:
                print "Removing and destroying VFs if created under %s..." % \
                      ldom_bus
                time.sleep(3)
                pattern = re.compile('.*\.VF\d+')
                vfs_list = pattern.findall(vfs_string)
                affliated_pfs_dict = {}
                for vf in vfs_list:
                    cmd_get_single_vf = "ldm list-io|grep '%s '" % vf
                    vf_info = execute(cmd_get_single_vf)

                    pf = vf_info.split()[0].split(
                        '.')[0] + "." + vf_info.split()[0].split('.')[1]
                    if pf in affliated_pfs_dict:
                        affliated_pfs_dict.get(pf).append(vf)
                    else:
                        affliated_pfs_dict.update({pf: [vf]})
                    if len(vf_info.split()) == 4:
                        affiliated_domain = vf_info.split()[3]
                        cmd_remove_vf = 'ldm rm-io %s %s' % (
                            vf, affiliated_domain)
                        execute(cmd_remove_vf)
                for pf in affliated_pfs_dict.keys():
                    cmd_destroy_vfs_on_pf = 'ldm destroy-vf -n max %s' % pf
                    execute(cmd_destroy_vfs_on_pf)
                print "Done"
        try:
            destroy_domain(ldom)
        except Exception as e:
            print e
        time.sleep(1)
    try:
        check_domain_exists(io_domain_name)
        destroy_domain(io_domain_name)
    except Exception as e:
        print e
    time.sleep(1)

    print "-------------------------------"
    source_volume_list = get_volume_of_domain(source_domain_name)
    snapshot_list = []
    for source_volume in source_volume_list:
        cmd_snapshot_list_of_this_volume = "zfs list -t snapshot | grep %s| " \
                                           "awk '{print $1}'" % source_volume
        result = execute(cmd_snapshot_list_of_this_volume)
        if result is None:
            pass
        else:
            pattern = re.compile(r'{0}.*'.format(source_volume))
            snapshot_list_of_one_volume = pattern.findall(result)
            for one_snapshot in snapshot_list_of_one_volume:
                snapshot_list.append(one_snapshot)

    if len(snapshot_list) == 0:
        print "No snapshot found under volume of %s" % source_domain_name
    else:
        once_destroy_flag = False
        # Test user choose which snapshot to destroy
        while True:
            user_choose_num = 0
            destroy_snapshot_input_num = 0
            if once_destroy_flag:
                destroy_continue_input_flag_dict = {
                    "y": True,
                    "Y": True,
                    "": True,
                    "n": False,
                    "N": False}
                while True:
                    destroy_continue_input_flag = raw_input(
                        "Do you want to continue destroy other snapshot[y/n]?")
                    expect_list = ["y", "Y", "n", "N", ""]
                    flag = False
                    for expect in expect_list:
                        if destroy_continue_input_flag == expect:
                            flag = True
                            break
                    if flag:
                        break
                    else:
                        print 'Wrong input,please input "y" or "n"'
                if destroy_continue_input_flag_dict.get(
                        destroy_continue_input_flag):
                    pass
                else:
                    break

            if len(snapshot_list) == 1:
                pass
            else:
                for snapshot in snapshot_list:
                    print "[{0}]{1}".format(user_choose_num, snapshot)
                    user_choose_num += 1
                destroy_snapshot_input_flag = raw_input(
                    "Which snapshot do you want to destroy?")
                try:
                    destroy_snapshot_input_num = int(
                        destroy_snapshot_input_flag)
                except Exception:
                    print "Please input the number below"
                    once_destroy_flag = False
                    continue

            if not 0 <= destroy_snapshot_input_num <= len(snapshot_list):
                print "Please input the number below"
            else:
                cmd_destroy_snapshot = 'zfs destroy %s' % snapshot_list[
                    destroy_snapshot_input_num]
                print "Destroying snapshot %s ..." % \
                      snapshot_list[destroy_snapshot_input_num]
                time.sleep(1)
                try:
                    execute(cmd_destroy_snapshot)
                except Exception as e:
                    print e
                    if len(snapshot_list) == 1:
                        time.sleep(3)
                        break
                else:
                    print "Done"
                    snapshot_list.pop(destroy_snapshot_input_num)
                if len(snapshot_list) == 0:
                    break
                else:
                    once_destroy_flag = True


if __name__ == "__main__":
    main()
