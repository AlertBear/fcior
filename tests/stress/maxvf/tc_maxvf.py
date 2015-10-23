#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import traceback
import os
import time
from common import *
from basic import *

# test purposes
from tp_maxvf_001 import tp_maxvf_001
from tp_maxvf_002 import tp_maxvf_002


def startup():

    info_print_report("FC-IOR stress maxvf:  startup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # check vdbench whether exists in io domain
    try:
        info_print_report(
            "Checking vdbench file whether exists in io domain [%s]" % iod_name)
        check_vdbench_exists(iod_name, iod_password)
    except Exception as e:
        error_print_report(
            "Vdbench file doesn't exist in io domain [%s], "
            "please refer to 'Distribute vdbench' in README " % iod_name)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall(
            "Vdbench file doesn't exist in io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report(
            "Vdbench file already exists in io domain [%s]" % iod_name)

    # check the pf whether has created vf, if yes,destroyed
    pf_list = [pf_1, pf_2]
    for pf_item in pf_list:
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
                    "Destroy all the vfs created on PF [%s] done" % pf_item)
        else:
            info_print_report(
                "No vf has been created on the PF [%s]" % pf_item)
        time.sleep(3)

    # create vf by manually assign port-wwn and node-wwn
    maxvf_num_1 = int(get_pf_maxvf_number(pf_1))
    vfs_list = []
    a_vfs_list = []
    info_print_report("Creating vf on PF [%s]" % pf_1)
    for i in range(0, 3):
        port_wwn = ctiutils.cti_getvar("PORT_WWN_PF_A_VF{0}".format(i))
        node_wwn = ctiutils.cti_getvar("NODE_WWN_PF_A_VF{0}".format(i))
        try:
            vf = create_vf_in_manual_mode(pf_1, port_wwn, node_wwn)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_1)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_1))
            vfs_list.append(vf)
            a_vfs_list.append(vf)
            time.sleep(10)
    for i in range(3, maxvf_num_1):
        try:
            vf = create_vf_in_dynamic_mode(pf_1)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_1)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_1))
            vfs_list.append(vf)
            a_vfs_list.append(vf)
            time.sleep(10)

    maxvf_num_2 = int(get_pf_maxvf_number(pf_2))
    b_vfs_list = []
    info_print_report("Creating vf on PF [%s]" % pf_2)
    for i in range(0, 3):
        port_wwn = ctiutils.cti_getvar("PORT_WWN_PF_B_VF{0}".format(i))
        node_wwn = ctiutils.cti_getvar("NODE_WWN_PF_B_VF{0}".format(i))
        try:
            vf = create_vf_in_manual_mode(pf_2, port_wwn, node_wwn)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_2)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_2))
            vfs_list.append(vf)
            b_vfs_list.append(vf)
            time.sleep(10)
    for i in range(3, maxvf_num_2):
        try:
            vf = create_vf_in_dynamic_mode(pf_2)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_2)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_2))
            vfs_list.append(vf)
            b_vfs_list.append(vf)
            time.sleep(10)

    # allocate vfs to the io domain
    for vf in vfs_list:
        try:
            info_print_report(
                "Allocating vf [%s] to io domain [%s]" % (vf, iod_name))
            assign_vf_to_domain(vf, iod_name)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to assign the vf [%s] to domain [%s] " % (vf, iod_name))
            return 1
        else:
            info_print_report(
                "VF [%s] has been allocated to io domain [%s]" % (vf, iod_name))
            time.sleep(3)

    # reboot io domain
    try:
        info_print_report(
            "Rebooting io domain [%s] after allocated vfs ..." % iod_name)
        reboot_domain(iod_name, iod_password)
    except Exception as e:
        error_print_report(e)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall("Failed to reboot io domain [%s]" % iod_name)
        return 1

    # io workload operate
    for i in range(0, 3):
        try:
            info_print_report(
                "Run vdbench on VF [%s] in io domain [%s]" %
                (vfs_list[i], iod_name))
            run_vdbench_on_vf_in_domain(iod_name, iod_password, vfs_list[i])
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to run vdbench on [%s] in io domain [%s]" %
                (vfs_list[i], iod_name))
            return 1
        else:
            info_print_report(
                "Run vdbench on [%s] in io domain [%s] success" %
                (vfs_list[i], iod_name))

    # Get the test vfs info dict
    iod_info_dict = {"name": iod_name, "password": iod_password}
    pf_1_vfs_dict = {}
    pf_2_vfs_dict = {}
    for vf in a_vfs_list:
        pf_1_vfs_dict.update({vf: iod_name})

    for vf in b_vfs_list:
        pf_2_vfs_dict.update({vf: iod_name})
    all_vfs_dict = {
        nprd1_name: {
            pf_1: pf_1_vfs_dict
        },
        nprd2_name: {
            pf_2: pf_2_vfs_dict
        }
    }

    try:
        info_print_report(
            "Getting all vfs information...")
        get_all_vfs_info(iod_info_dict, all_vfs_dict)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed to add all vfs information")
        return 1
    else:
        info_print_report("Done")

    return 0


def cleanup():

    info_print_report("FC-IOR stress maxvf:  cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')

    # if vdbench process is still running, kill it
    try:
        info_print_report(
            "Killing the vdbench process in io domain [%s]" % iod_name)
        kill_vdbench_process_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to kill vdbench process in [%s] due to:\n%s" %
            (iod_name, e))
    else:
        info_print_report("Killed vdbench process in [%s] success" % iod_name)
    time.sleep(5)

    # destroy all the vf that has created on the pf
    pf_list = [pf_1, pf_2]
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

    # save the related logs created in this test case
    try:
        info_print_report(
            "Saving related log files of this test case")
        save_related_logs("maxvf")
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
test_list[1] = tp_maxvf_001
test_list[2] = tp_maxvf_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
