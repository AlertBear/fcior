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
from tp_nicib_001 import tp_nicib_001
from tp_nicib_002 import tp_nicib_002


def startup():

    info_print_report("FC-IOR mix nicib:  startup")

    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd1_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    nprd2_password = ctiutils.cti_getvar("NPRD_B_PASSWORD")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # get the nic and ib pfs related variables in configuration file
    nic_pf_1 = ctiutils.cti_getvar("NIC_PF_A")
    nic_pf_2 = ctiutils.cti_getvar("NIC_PF_B")
    ib_pf_1 = ctiutils.cti_getvar("IB_PF_A")
    ib_pf_2 = ctiutils.cti_getvar("IB_PF_B")
    subnet = ctiutils.cti_getvar("VF_SUBNET")

    # get remote host variables in configuration file
    remote_nic_link = ctiutils.cti_getvar("REMOTE_NIC_LINK")
    nic_remote_host = ctiutils.cti_getvar("NIC_REMOTE_HOST")
    nic_remote_password = ctiutils.cti_getvar("NIC_REMOTE_HOST_PASSWORD")
    remote_ib_link = ctiutils.cti_getvar("REMOTE_IB_LINK")
    ib_remote_host = ctiutils.cti_getvar("IB_REMOTE_HOST")
    ib_remote_password = ctiutils.cti_getvar("IB_REMOTE_HOST_PASSWORD")

    # check the mix_test flag has been set
    mix_test_flag = ctiutils.cti_getvar("MIX_TEST")
    nic_switch_connection = ctiutils.cti_getvar("NIC_SWITCH_CONNECTION")
    ib_switch_connection = ctiutils.cti_getvar("IB_SWITCH_CONNECTION")
    if mix_test_flag != "yes":
        error_print_report("If want to test mix_nicfc case, be ensure to "
                           "define MIX_TEST=yes in test_config file")
        ctiutils.cti_deleteall("Not supported")
        return 1
    if nic_switch_connection != "yes" or ib_switch_connection != "yes":
        error_print_report("If want to test mix_nicib case, be ensure to "
                           "connect all NIC and IB cards to the related "
                           "switches. Meanwhile, define "
                           "NIC_SWITCH_CONNECTION=yes, "
                           "IB_SWITCH_CONNECTION=yes in test_config file")
        ctiutils.cti_deleteall("Not supported")
        return 1

    # check whether remote nic pf has been connected to switch and
    # could be pingable from local test system
    info_print_report("Checking all nic pfs have been "
                      "connected to switch")
    remote_host_dict = {nic_remote_host: {"password": nic_remote_password,
                                      "link": remote_nic_link}}
    root_dict = {nprd1_name: {"password": nprd1_password,
                              "pf": nic_pf_1},
                 nprd2_name: {"password": nprd2_password,
                              "pf": nic_pf_2}}
    try:
        check_nic_pf_be_connected(remote_host_dict, root_dict)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Not all nic pfs are connected to switch")
        return 1
    else:
        info_print_report("All nic pfs are connected to switch")

    # check whether remote ib pf has been connected to switch and
    # could be pingable from local test system
    info_print_report("Checking all ib pfs have been "
                      "connected to switch")
    ib_remote_host_dict = {ib_remote_host: {"password": ib_remote_password,
                                            "link": remote_ib_link}}
    root_dict = {nprd1_name: {"password": nprd1_password,
                              "pf": ib_pf_1},
                 nprd2_name: {"password": nprd2_password,
                              "pf": ib_pf_2}}
    try:
        check_ib_pf_be_connected(ib_remote_host_dict, root_dict)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Not all IB pfs are connected to switch")
        return 1
    else:
        info_print_report("All IB pfs are connected to switch")

    # check ib ior has been enabled in io domain
    info_print_report("Checking ib ior has been enabled in [%s]" % iod_name)
    try:
        check_ib_ior_enabled_in_iod(iod_name, iod_password)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("IB ior has not been enabled in "
                               "[%s]" % iod_name)
        return 1
    else:
        info_print_report("IB ior has been enabled in [%s]" % iod_name)

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

    # check the ib pf whether has created vf, if yes,destroyed
    ib_pf_list = [ib_pf_1, ib_pf_2]
    for pf_item in ib_pf_list:
        info_print_report("Checking PF [%s] whether has created vf" % pf_item)
        if check_whether_pf_has_created_vf(pf_item):
            info_print_report(
                "VF has been created on PF [%s], trying to destroy..." %
                pf_item)
            try:
                destroy_all_ib_vfs_on_pf(iod_name, iod_password, pf_item)
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

    # create ib vfs on two pfs
    try:
        info_print_report("Creating vf on PF [%s]" % ib_pf_1)
        ib_a_vf = create_ib_vf(ib_pf_1)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % ib_pf_1)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (ib_a_vf, ib_pf_1))
        time.sleep(30)

    try:
        info_print_report("Creating vf on PF [%s]" % ib_pf_2)
        ib_b_vf = create_ib_vf(ib_pf_2)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % ib_pf_2)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (ib_b_vf, ib_pf_2))
        time.sleep(30)

    # allocate vfs to the io domain
    vfs_list = [nic_a_vf, nic_b_vf, ib_a_vf, ib_b_vf]
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
        "Configuring the corresponding nic interfaces to be "
        "IPMP in io domain [%s]" % iod_name)
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

    # configure remote nic interface to be pingable from nic ipmp in io domain
    info_print_report("Configuring NIC interface in remote host")
    rmt_ip_addr = subnet + '.11.2'
    try:
        configure_nic_ip_in_remote(
            nic_remote_host,
            nic_remote_password,
            remote_nic_link,
            rmt_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to configure nic interface "
                               "on remote host [%s]" % nic_remote_host)
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
        ctiutils.cti_deleteall("Failed to get remote nic interface be "
                               "pingable from io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Done")

    # configure IB vfs ipmp in io domain
    info_print_report(
        "Configuring the corresponding IB links to be "
        "IPMP in io domain [%s]" % iod_name)
    ipmp = 'ior_ipmp1'
    ib_ip_addr = subnet + '.12.1'
    try:
        configure_ib_vfs_ipmp_in_domain(
            iod_name,
            iod_password,
            ipmp,
            ib_a_vf,
            ib_b_vf,
            ib_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to configure IB vfs links"
                               " to be IPMP io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Configured done")

    # configure remote IB link to be pingable from ib ipmp in io domain
    info_print_report("Configuring IB link in remote host")
    rmt_ib_ip_addr = subnet + '.12.2'
    try:
        configure_ib_ip_in_remote(
            ib_remote_host,
            ib_remote_password,
            remote_ib_link,
            rmt_ib_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to configure IB link "
                               "on remote host [%s]" % ib_remote_host)
        return 1
    else:
        info_print_report("Configured done")

    # check whether remote ib link can be pingable from io domain
    info_print_report("Checking remote ib link is pingable from [%s]" %
                      iod_name)
    try:
        check_remote_pingable_from_io_domain(
            iod_name,
            iod_password,
            rmt_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to get remote ib link be pingable "
                               "from io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Done")

    # run io traffic on ib ipmp interface, io traffic is just ping.
    try:
        info_print_report(
            "Run traffic between remote interface and "
            "ipmp group in io domain [%s]" % iod_name)
        run_ping_traffic_in_domain(
            iod_name,
            iod_password,
            ib_ip_addr,
            rmt_ib_ip_addr)
    except Exception as e:
        error_print_report(e)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall(
            "Failed to run traffic between remote ib link"
            " and ib ipmp in io domain [%s]" % iod_name)
        return 1

    # Get the test vfs info dict
    iod_info_dict = {"name": iod_name, "password": iod_password}
    nic_pf_1_vfs_dict = {}
    nic_pf_2_vfs_dict = {}
    nic_pf_1_vfs_dict.update({nic_a_vf: iod_name})
    nic_pf_2_vfs_dict.update({nic_b_vf: iod_name})

    ib_pf_1_vfs_dict = {}
    ib_pf_2_vfs_dict = {}
    ib_pf_1_vfs_dict.update({ib_a_vf: iod_name})
    ib_pf_2_vfs_dict.update({ib_b_vf: iod_name})
    all_vfs_dict = {
        nprd1_name: {
            nic_pf_1: nic_pf_1_vfs_dict,
            ib_pf_2: ib_pf_1_vfs_dict
        },
        nprd2_name: {
            nic_pf_2: nic_pf_2_vfs_dict,
            ib_pf_2: ib_pf_2_vfs_dict
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

    info_print_report("FC-IOR mix nicib:  cleanup")

    nic_pf_1 = ctiutils.cti_getvar("NIC_PF_A")
    nic_pf_2 = ctiutils.cti_getvar("NIC_PF_B")
    ib_pf_1 = ctiutils.cti_getvar("IB_PF_A")
    ib_pf_2 = ctiutils.cti_getvar("IB_PF_B")
    nic_rmt_name = ctiutils.cti_getvar("NIC_REMOTE_HOST")
    nic_rmt_password = ctiutils.cti_getvar("NIC_REMOTE_HOST_PASSWORD")
    ib_rmt_name = ctiutils.cti_getvar("IB_REMOTE_HOST")
    ib_rmt_password = ctiutils.cti_getvar("IB_REMOTE_HOST_PASSWORD")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')

    # if nic or ib traffic process is still running, kill it
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

    # delete the nic ipmp group and interfaces in io domain
    nic_pf_list = [nic_pf_1, nic_pf_2]
    try:
        info_print_report("Deleting the NIC ipmp group and interfaces "
                          "in io domain [%s]" % iod_name)
        delete_nic_interface_in_domain(iod_name, iod_password, nic_pf_list)
    except Exception as e:
        warn_print_report(
            "Failed to delete the NIC ipmp and interfaces in [%s]"
            " due to:\n%s" % (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the NIC ipmp and interfaces "
                          "in [%s] success" % iod_name)

    # delete the vnic in remote host
    try:
        info_print_report("Deleting the vnic in remote host [%s]" % nic_rmt_name)
        delete_remote_vnic(nic_rmt_name, nic_rmt_password)
    except Exception as e:
        warn_print_report(
            "Failed to delete the vnic in remote host [%s] due to:\n%s" %
            (nic_rmt_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the vnic in remote host "
                          "[%s] success" % nic_rmt_name)

    # delete the ib ipmp group and links in io domain
    ib_pf_list = [ib_pf_1, ib_pf_2]
    try:
        info_print_report("Deleting the IB ipmp group and links "
                          "in io domain [%s]" % iod_name)
        delete_ib_part_in_domain(iod_name, iod_password, ib_pf_list)
    except Exception as e:
        warn_print_report(
            "Failed to delete the IB ipmp and links in [%s] "
            "due to:\n%s" % (iod_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the IB ipmp and interfaces "
                          "in [%s] success" % iod_name)

    # delete the IB links in remote host
    try:
        info_print_report("Deleting the ib links in "
                          "remote host [%s]" % ib_rmt_name)
        delete_remote_ib_part(ib_rmt_name, ib_rmt_password)
    except Exception as e:
        warn_print_report(
            "Failed to delete the ib links in remote host [%s] "
            "due to:\n%s" % (nic_rmt_name, e))
        error_report(traceback.print_exc())
    else:
        info_print_report("Deleted the ib links in remote host "
                          "[%s] success" % ib_rmt_name)

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

    # destroy all the vfs that has been created on ib pfs
    for pf in ib_pf_list:
        try:
            info_print_report(
                "Destroying the VFs created on [%s] in this test case" % pf)
            destroy_all_ib_vfs_on_pf(iod_name, iod_password, pf)
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
        save_related_logs("nicib")
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
test_list[1] = tp_nicib_001
test_list[2] = tp_nicib_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
