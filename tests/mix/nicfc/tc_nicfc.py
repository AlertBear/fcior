#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import time
import os
import traceback
from basic import *
from common import *

# test purposes
from tp_nicfc_001 import tp_nicfc_001
from tp_nicfc_002 import tp_nicfc_002


def startup():

    info_print_report("FC-IOR mix nicfc:  startup")

    # get the pfs from configuration file
    fc_pf_1 = ctiutils.cti_getvar("PF_A")
    fc_pf_2 = ctiutils.cti_getvar("PF_B")

    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd1_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    nprd2_password = ctiutils.cti_getvar("NPRD_B_PASSWORD")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # get the nic pfs related variables in configuration file
    nic_pf_1 = ctiutils.cti_getvar("NIC_PF_A")
    nic_pf_2 = ctiutils.cti_getvar("NIC_PF_B")
    subnet = ctiutils.cti_getvar("VF_SUBNET")

    # get remote host variables in configuration file
    remote_nic_link = ctiutils.cti_getvar("REMOTE_NIC_LINK")
    remote_host = ctiutils.cti_getvar("NIC_REMOTE_HOST")
    remote_password = ctiutils.cti_getvar("NIC_REMOTE_HOST_PASSWORD")

    # check the mix_test flag has been set
    mix_test_flag = ctiutils.cti_getvar("MIX_TEST")
    nic_switch_connection = ctiutils.cti_getvar("NIC_SWITCH_CONNECTION")
    if mix_test_flag != "yes":
        error_print_report("If want to test mix_nicfc case, be ensure to "
                           "define MIX_TEST=yes in test_config file")
        ctiutils.cti_deleteall("Not supported")
        return 1
    if nic_switch_connection != "yes":
        error_print_report("If want to test mix_nicfc case, be ensure "
                           "to connect all NIC cards to the network "
                           "switch and define NIC_SWITCH_CONNECTION=yes"
                           "in test_config file")
        ctiutils.cti_deleteall("Not supported")
        return 1

    # check whether remote pf has been connected to switch and
    # could be pingable from local test system
    info_print_report("Checking all NIC pfs have been connected to switch ")
    remote_host_dict = {remote_host: {"password": remote_password,
                                      "link": remote_nic_link}}
    root_dict = {nprd1_name: {"password": nprd1_password,
                              "pf": nic_pf_1},
                 nprd2_name: {"password": nprd2_password,
                              "pf": nic_pf_2}}
    try:
        check_nic_pf_be_connected(remote_host_dict,
                                  root_dict)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Not all nic pfs have been connected to switch")
        return 1
    else:
        info_print_report("All nic pfs have been connected to switch")

    # check the fc pf whether has created vf, if yes,destroyed
    fc_pf_list = [fc_pf_1, fc_pf_2]
    for pf_item in fc_pf_list:
        info_print_report("Checking PF [%s] whether has created vf" % pf_item)
        if check_whether_pf_has_created_vf(pf_item):
            info_print_report(
                "VF has been created on PF [%s], trying to destroy..." %
                pf_item)
            try:
                destroy_all_vfs_on_pf(pf_item)
            except Exception as e:
                error_print_report(e)
                error_report(traceback.print_exc())
                ctiutils.cti_deleteall(
                    "Failed to destroy all the vfs created on the PF [%s]" %
                    pf_item)
                return 1
            else:
                info_print_report(
                    "Destroy all the vfs created on PF [%s]" % pf_item)
        else:
            info_print_report(
                "No vf has been created on the PF [%s]" % pf_item)
        time.sleep(3)

    # check the nic pf whether has created vf, if yes,destroyed
    nic_pf_list = [nic_pf_1, nic_pf_2]
    for pf_item in nic_pf_list:
        info_print_report("Checking PF [%s] whether has created vf" % pf_item)
        if check_whether_pf_has_created_vf(pf_item):
            info_print_report(
                "VF has been created on PF [%s], trying to destroy..." %
                pf_item)
            try:
                destroy_all_nic_vfs_on_pf(iod_name, iod_password, pf_item)
            except Exception as e:
                error_print_report(e)
                error_report(traceback.print_exc())
                ctiutils.cti_deleteall(
                    "Failed to destroy all the vfs created on the PF [%s]" %
                    pf_item)
                return 1
            else:
                info_print_report(
                    "Destroy all the vfs created on PF [%s]" % pf_item)
        else:
            info_print_report(
                "No vf has been created on the PF [%s]" % pf_item)
        time.sleep(3)

    # create fc vfs by manually assign port-wwn and node-wwn
    a_port_wwn_0 = ctiutils.cti_getvar("PORT_WWN_PF_A_VF0")
    a_node_wwn_0 = ctiutils.cti_getvar("NODE_WWN_PF_A_VF0")
    try:
        info_print_report("Creating vf on PF [%s]" % fc_pf_1)
        a_vf = create_vf_in_manual_mode(fc_pf_1, a_port_wwn_0, a_node_wwn_0)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % fc_pf_1)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (a_vf, fc_pf_1))
        time.sleep(30)

    b_port_wwn_0 = ctiutils.cti_getvar("PORT_WWN_PF_B_VF0")
    b_node_wwn_0 = ctiutils.cti_getvar("NODE_WWN_PF_B_VF0")

    try:
        info_print_report("Creating vf on PF [%s]" % fc_pf_2)
        b_vf = create_vf_in_manual_mode(fc_pf_2, b_port_wwn_0, b_node_wwn_0)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % fc_pf_2)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (b_vf, fc_pf_2))
        time.sleep(30)

    # create nic vfs on two pfs
    try:
        info_print_report("Creating vf on PF [%s]" % nic_pf_1)
        nic_a_vf = create_nic_vf(nprd1_name, nprd1_password, nic_pf_1)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % nic_pf_1)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (nic_a_vf, nic_pf_1))
        time.sleep(30)

    try:
        info_print_report("Creating vf on PF [%s]" % nic_pf_2)
        nic_b_vf = create_nic_vf(nprd2_name, nprd2_password, nic_pf_2)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % nic_pf_2)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (nic_b_vf, nic_pf_2))
        time.sleep(30)

    # allocate vfs to the io domain
    vfs_list = [a_vf, b_vf, nic_a_vf, nic_b_vf]
    for vf in vfs_list:
        try:
            info_print_report(
                "Allocating vf [%s] to io domain [%s]" % (vf, iod_name))
            assign_vf_to_domain(vf, iod_name)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to assign the vf [%s] to domain [%s] " % (vf, iod_name))
            return 1
        else:
            info_print_report(
                "VF [%s] has been allocated to io domain [%s]" % (vf, iod_name))
            time.sleep(5)

    # reboot io domain
    try:
        info_print_report(
            "Rebooting io domain [%s] after allocated vfs ..." % iod_name)
        reboot_domain(iod_name, iod_password)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to reboot io domain [%s]" % iod_name)
        return 1

    # configure nic vfs ipmp in io domain
    info_print_report(
        "Configuring NIC vf interfaces to be IPMP in io domain [%s]" %
        iod_name)
    ipmp = 'ior_ipmp0'
    ip_addr = subnet + '.11.1'
    try:
        configure_nic_vfs_ipmp_in_domain(
            iod_name,
            iod_password,
            ipmp,
            nic_a_vf,
            nic_b_vf,
            ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to configure nic vfs interface"
                               " to be IPMP io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Configured done")

    # configure remote interface to be pingable from ipmp in io domain
    info_print_report("Configuring interface in remote host")
    rmt_ip_addr = subnet + '.11.2'
    try:
        configure_nic_ip_in_remote(
            remote_host,
            remote_password,
            remote_nic_link,
            rmt_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to configure pf ip address "
                               "on remote host [%s]" % remote_host)
        return 1
    else:
        info_print_report("Configured done")

    # check whether remote interface can be pingable from io domain
    info_print_report("Checking remote interface is pingable from [%s]" %
                      iod_name)
    try:
        check_remote_pingable_from_io_domain(
            iod_name,
            iod_password,
            rmt_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to get remote host be pingable "
                               "from io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Done")

    # fc io workload operate
    info_print_report(
        "Checking the FC io workload file whether exists in io domain [%s]" %
        iod_name)
    if check_io_workload_exists(iod_name, iod_password):
        info_print_report(
            "FC io workload file alerady exists in io domain [%s]" % iod_name)
    else:
        info_print_report(
            "FC io workload file doesn't exist in io domain [%s]" % iod_name)
        try:
            info_print_report(
                "Distributing the FC io workload file to io domain [%s]" %
                iod_name)
            distribute_io_workload_files_to_domain(iod_name, iod_password)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to distribute FC io workload to io domain [%s]" %
                iod_name)
            return 1
    try:
        info_print_report(
            "Run FC io workload on VF [%s] in io domain [%s]" %
            (a_vf, iod_name))
        run_io_workload_on_vf_in_domain(iod_name, iod_password, a_vf)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall(
            "Failed to run FC io workload on [%s] in io domain [%s]" %
            (a_vf, iod_name))
        return 1

    # run io traffic on ipmp interface, io traffic is just ping.
    try:
        info_print_report(
            "Run traffic between remote interface and "
            "ipmp group in io domain [%s]" % iod_name)
        run_ping_traffic_in_domain(iod_name, iod_password, ip_addr, rmt_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall(
            "Failed to run traffic between remote interface"
            " and ipmp in io domain [%s]" % iod_name)
        return 1

    # Get the test vfs info dict
    iod_info_dict = {"name": iod_name, "password": iod_password}
    fc_pf_1_vfs_dict = {}
    fc_pf_2_vfs_dict = {}
    nic_pf_1_vfs_dict = {}
    nic_pf_2_vfs_dict = {}

    fc_pf_1_vfs_dict.update({a_vf: iod_name})
    fc_pf_2_vfs_dict.update({b_vf: iod_name})
    nic_pf_1_vfs_dict.update({nic_a_vf: iod_name})
    nic_pf_2_vfs_dict.update({nic_b_vf: iod_name})
    all_vfs_dict = {
        nprd1_name: {
            fc_pf_1: fc_pf_1_vfs_dict,
            nic_pf_1: nic_pf_1_vfs_dict
        },
        nprd2_name: {
            fc_pf_2: fc_pf_2_vfs_dict,
            nic_pf_2: nic_pf_2_vfs_dict
        }
    }

    try:
        info_print_report(
            "Getting all vfs information...")
        get_all_vfs_info(iod_info_dict, all_vfs_dict)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to get all vfs information")
        return 1
    else:
        info_print_report("Done")

    return 0


def cleanup():

    info_print_report("FC-IOR mix nicfc:  cleanup")

    fc_pf_1 = ctiutils.cti_getvar("PF_A")
    fc_pf_2 = ctiutils.cti_getvar("PF_B")
    nic_pf_1 = ctiutils.cti_getvar("NIC_PF_A")
    nic_pf_2 = ctiutils.cti_getvar("NIC_PF_B")
    rmt_name = ctiutils.cti_getvar("NIC_REMOTE_HOST")
    rmt_password = ctiutils.cti_getvar("NIC_REMOTE_HOST_PASSWORD")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')

    # if run_io.sh process is still running, kill it
    try:
        info_print_report(
            "Killing the run_io.sh process in io domain [%s]" % iod_name)
        kill_run_io_process_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to kill run_io.sh process in [%s] due to:\n%s" %
            (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Killed run_io.sh process in [%s] success" % iod_name)
    time.sleep(30)

    # if zfs file system has been created in this case, destroy it
    try:
        info_print_report("Cleanup file system in io domain [%s]" % iod_name)
        destroy_file_system_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to destroy file system in [%s] due to:\n%s" %
            (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Destroyed file system in [%s] success" % iod_name)

    # if nic traffic process is still running, kill it
    try:
        info_print_report(
            "Killing the nic or ib traffic"
            " process in io domain [%s]" % iod_name)
        kill_nic_ib_traffic_process_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to kill nic or ib traffic process in [%s] due to:\n%s" %
            (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Killed the nic or ib traffic process "
                          "in [%s] success" % iod_name)
    time.sleep(30)

    # delete the ipmp group and interfaces in io domain
    nic_pf_list = [nic_pf_1, nic_pf_2]
    try:
        info_print_report("Deleting the ipmp group and interfaces "
                          "in io domain [%s]" % iod_name)
        delete_nic_interface_in_domain(iod_name, iod_password, nic_pf_list)
    except Exception as e:
        warn_print_report(
            "Failed to delete the ipmp and interfaces in [%s] due to:\n%s" %
            (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the ipmp and interfaces "
                          "in [%s] success" % iod_name)

    # delete the remote vnic in remote host
    try:
        info_print_report("Deleting the vnic in remote host [%s]" % rmt_name)
        delete_remote_vnic(rmt_name, rmt_password)
    except Exception as e:
        warn_print_report(
            "Failed to delete the vnic in remote host [%s] due to:\n%s" %
            (rmt_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the vnic in remote host "
                          "in [%s] success" % rmt_name)

    # destroy all the vfs that has created on the fc pfs
    fc_pf_list = [fc_pf_1, fc_pf_2]
    for pf in fc_pf_list:
        try:
            info_print_report(
                "Destroying the VFs created on [%s] in this test case" % pf)
            destroy_all_vfs_on_pf(pf)
        except Exception as e:
            warn_print_report(
                "Failed to destroy all the vfs created on [%s] due to:\n%s" % (
                    pf, e))
            error_report(traceback.print_exc())
        else:
            info_print_report(
                "Destroyed all the VFs created on [%s] in this test case" % pf)

    # destroy all the vfs that has been created on nic pfs
    for pf in nic_pf_list:
        try:
            info_print_report(
                "Destroying the VFs created on [%s] in this test case" % pf)
            destroy_all_nic_vfs_on_pf(iod_name, iod_password, pf)
        except Exception as e:
            warn_print_report(
                "Failed to destroy all the vfs created on [%s] due to:\n%s" % (
                    pf, e))
            error_report(traceback.print_exc())
        else:
            info_print_report(
                "Destroyed all the VFs created on [%s] in this test case" % pf)

    # save the related logs created in this test case
    try:
        info_print_report(
            "Saving related log files of this test case")
        save_related_logs("nicfc")
    except Exception as e:
        warn_print_report(
            "Failed to save related log files due to:\n%s" % e)
    else:
        info_print_report('Test user could review the "related_logs" '
                          'in result path')

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_nicfc_001
test_list[2] = tp_nicfc_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
