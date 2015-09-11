#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import time
import pytet
import os
import traceback
from common import *

# test purposes
from tp_mix_nic_fc_001 import tp_mix_nic_fc_001
from tp_mix_nic_fc_002 import tp_mix_nic_fc_002


def startup():

    info_print_report("FC-IOR mix nicfc:  startup")

    # get the pfs from configuration file
    fc_pf_1 = ctiutils.cti_getvar("PF_A")
    fc_pf_2 = ctiutils.cti_getvar("PF_B")
    nic_pf_1 = ctiutils.cti_getvar("NIC_PF_A")
    nic_pf_2 = ctiutils.cti_getvar("NIC_PF_B")
    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

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
        nic_a_vf = create_vf_in_dynamic_mode(nic_pf_1)
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
        nic_b_vf = create_vf_in_dynamic_mode(nic_pf_2)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % nic_pf_2)
        return 1
    else:
        info_print_report("Created vf [%s] on pf [%s]" % (nic_b_vf, nic_pf_2))
        time.sleep(30)

    # allocate vfs to the io domain
    vfs_list = [a_vf, b_vf]
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

    # io workload operate
    info_print_report(
        "Checking the io workload file whether exists in io domain [%s]" %
        iod_name)
    if check_io_workload_exists(iod_name, iod_password):
        info_print_report(
            "IO workload file alerady exists in io domain [%s]" % iod_name)
    else:
        info_print_report(
            "IO workload file doesn't exist in io domain [%s]" % iod_name)
        try:
            info_print_report(
                "Trying to distribute the io workload file to io domain [%s]" %
                iod_name)
            distribute_io_workload_files_to_domain(iod_name, iod_password)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to distribute io workload to io domain [%s]" %
                iod_name)
            return 1
    try:
        info_print_report(
            "Run I/O workload on VF [%s] in io domain [%s]" %
            (a_vf, iod_name))
        run_io_workload_on_vf_in_domain(iod_name, iod_password, a_vf)
    except Exception as e:
        error_print_report(e)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall(
            "Failed to run io workload on [%s] in io domain [%s]" %
            (a_vf, iod_name))
        return 1

    # Get the test vfs info dict
    a_vfs_list = [a_vf]
    b_vfs_list = [b_vf]
    iod_info_dict = {"name": iod_name, "password": iod_password}
    fc_pf_1_vfs_dict = {}
    fc_pf_2_vfs_dict = {}
    for vf in a_vfs_list:
        fc_pf_1_vfs_dict.update({vf: iod_name})
    for vf in b_vfs_list:
        fc_pf_2_vfs_dict.update({vf: iod_name})
    all_vfs_dict = {
        nprd1_name: {
            fc_pf_1: fc_pf_1_vfs_dict
        },
        nprd2_name: {
            fc_pf_2: fc_pf_2_vfs_dict
        }
    }
    all_vfs_info_xml = os.getenv("VFS_INFO")

    try:
        info_print_report(
            "Getting test vfs information...")
        get_all_vfs_info(iod_info_dict, all_vfs_dict, all_vfs_info_xml)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to add test vfs information")
        return 1
    else:
        info_print_report("Done")

    return 0


def cleanup():

    info_print_report("FC-IOR mix nicfc:  cleanup")

    fc_pf_1 = ctiutils.cti_getvar("PF_A")
    fc_pf_2 = ctiutils.cti_getvar("PF_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')
    all_vfs_info_xml = ctiutils.cti_getvar("VFS_INFO")
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact_logs"

    # if test_vfs_info_xml exists, delete it.
    if os.path.isfile(all_vfs_info_xml):
        os.remove(all_vfs_info_xml)

    # if run_io.sh process is still running, kill it
    try:
        info_print_report(
            "Killing the run_io.sh process in io domain [%s]" % iod_name)
        kill_run_io_process_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to kill run_io.sh process in [%s] due to:\n%s" %
            (iod_name, e))
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
    else:
        info_print_report("Destroyed file system in [%s] success" % iod_name)

    # destroy all the vf that has created on the pf
    pf_list = [fc_pf_1, fc_pf_2]
    for pf in pf_list:
        try:
            info_print_report(
                "Destroying the VFs created on [%s] in this test case" % pf)
            destroy_all_vfs_on_pf(pf)
        except Exception as e:
            warn_print_report(
                "Failed to destroy all the vfs created due to:\n%s" % e)
        else:
            info_print_report(
                "Destroyed all the VFs created in this test case")

    # copy the pexpect interaction logfile with io domain to "$CTI_LOGDIR" for
    # review , prevent being removed.
    if not os.path.exists(interaction_dir):
        os.makedirs(interaction_dir)
    if os.path.isfile(interaction_log):
        try:
            info_print_report(
                "Saving the interaction logfile of this test case")
            now = time.strftime("%Y%m%d%H%M%S")
            save_pexpect_interaction_logfile(
                "{0}/mix_nicfc.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print_report(
                "Failed to save pexpect interaction logfile due to: \n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/mix_nicfc.{1}".format(
                    interaction_dir, now))

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_mix_nic_fc_001
test_list[2] = tp_mix_nic_fc_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
