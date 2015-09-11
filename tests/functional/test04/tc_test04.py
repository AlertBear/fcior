#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import pytet
import time
import os
import traceback
from common import *

# test purposes
from tp_test04_001 import tp_test04_001
from tp_test04_002 import tp_test04_002


def startup():

    info_print_report("FC-IOR functional test04:  startup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")

    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

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
                    "Destroy all the vfs created on PF [%s]" % pf_item)
        else:
            info_print_report(
                "No vf has been created on the PF [%s]" % pf_item)
        time.sleep(3)

    # create vfs
    vfs_list = []
    a_vfs_list = []

    info_print_report("Creating vf on PF [%s]" % pf_1)
    for i in range(0, 2):
        port_wwn = os.getenv("PORT_WWN_PF_A_VF{0}".format(i))
        node_wwn = os.getenv("NODE_WWN_PF_A_VF{0}".format(i))
        try:
            vf = create_vf_in_manual_mode(pf_1, port_wwn, node_wwn)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to create vf on the PF [%s]" % pf_1)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_1))
            vfs_list.append(vf)
            a_vfs_list.append(vf)
            time.sleep(30)

    b_vfs_list = []
    info_print_report("Creating vf on PF [%s]" % pf_2)
    for i in range(0, 2):
        port_wwn = os.getenv("PORT_WWN_PF_B_VF{0}".format(i))
        node_wwn = os.getenv("NODE_WWN_PF_B_VF{0}".format(i))
        try:
            vf = create_vf_in_manual_mode(pf_2, port_wwn, node_wwn)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to create vf on the PF [%s]" % pf_2)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_2))
            vfs_list.append(vf)
            b_vfs_list.append(vf)
            time.sleep(30)

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
            time.sleep(5)

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
    else:
        info_print_report("Created done")

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

    info_print_report("FC-IOR functional test04:  cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    all_vfs_info_xml = ctiutils.cti_getvar("VFS_INFO")
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact_logs"

    # if test_vfs_info_log exists, delete it.
    if os.path.isfile(all_vfs_info_xml):
        os.remove(all_vfs_info_xml)

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
                "{0}/func04.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print_report(
                "Failed to save pexpect interaction logfile due to:\n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/func04.{1}".format(
                    interaction_dir, now))


#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_test04_001
test_list[2] = tp_test04_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
