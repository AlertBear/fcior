#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#


import ctiutils
import time
import os

from common import *

# test purposes
from tp_test01_001 import tp_test01_001
from tp_test01_002 import tp_test01_002


def startup():

    info_print_report("FC-IOR functional test01:  startup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_3 = get_pf_another_port(pf_1)

    # get the root domain and io domain from configuration file
    nprd_name = ctiutils.cti_getvar("NPRD_A")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # check the pf whether has created vf, if yes,destroyed
    info_print_report("Checking PF [%s] whether has created vf" % pf_3)
    if check_whether_pf_has_created_vf(pf_3):
        info_print_report(
            "VF has been created on PF [%s], trying to destroy..." %
            pf_3)
        try:
            destroy_all_vfs_on_pf(pf_3)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to destroy all the vfs created on the PF [%s]" %
                pf_3)
            return 1
        else:
            info_print_report(
                "Destroyed all the vfs created on PF [%s]" % pf_3)
    else:
        info_print_report("No vf has been created on PF [%s]" % pf_3)
    time.sleep(3)

    vfs_list = []
    pf_1_vfs_list = []
    for i in range(0, 2):
        vf = pf_1 + '.VF{0}'.format(i)
        pf_1_vfs_list.append(vf)
        vfs_list.append(vf)

    pf_3_vfs_list = []
    # create vf on pf_3 in manual mode
    info_print_report("Creating vf on PF [%s]" % pf_3)
    for i in range(0, 2):
        try:
            vf = create_vf_in_dynamic_mode(pf_3)
        except Exception as e:
            error_print_report(e)
            error_report(ctiutils.cti_traceback())
            ctiutils.cti_deleteall(
                "Failed to create vf on the PF [%s]" % pf_3)
            return 1
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_3))
            pf_3_vfs_list.append(vf)
            vfs_list.append(vf)
            time.sleep(30)

    for vf in vfs_list:
        try:
            info_print_report(
                "Allocating vf [%s] to io domain [%s]" %
                (vf, iod_name))
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

    # Get the test vfs info dict
    iod_info_dict = {"name": iod_name, "password": iod_password}
    pf_1_vfs_dict = {}
    for vf in pf_1_vfs_list:
        pf_1_vfs_dict.update({vf: iod_name})
    pf_3_vfs_dict = {}
    for vf in pf_3_vfs_list:
        pf_3_vfs_dict.update({vf: iod_name})

    test_vfs_dict = {
        nprd_name: {
            pf_1: pf_1_vfs_dict,
            pf_3: pf_3_vfs_dict
        }
    }
    test_vfs_info_log = os.getenv("TST_VFS")

    try:
        info_print_report(
            "Getting test vfs information...")
        get_test_vfs_info(iod_info_dict, test_vfs_dict, test_vfs_info_log)
    except Exception as e:
        error_print_report(e)
        error_report(ctiutils.cti_traceback())
        ctiutils.cti_deleteall("Failed")
        return 1
    else:
        info_print_report("Done")

    return 0


def cleanup():

    info_print_report("FC-IOR functional test01:  cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_3 = get_pf_another_port(pf_1)
    iod_name = ctiutils.cti_getvar("IOD")
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact"

    # remove all the pf_1 vf that has been bound to the io domain
    for i in range(0, 2):
        vf = pf_1 + '.VF{0}'.format(i)
        try:
            info_print_report(
                "Removing %s from %s..." % (vf, iod_name))
            remove_vf_from_domain(vf, iod_name)
        except Exception as e:
            warn_print_report("Failed due to:\n%s" % e)
        else:
            info_print_report("Remove done")
            time.sleep(5)

    # destroy all the vf that has created on the pf_3
    try:
        info_print_report(
            "Destroying the VFs created on [%s] in this test case" % pf_3)
        destroy_all_vfs_on_pf(pf_3)
    except Exception as e:
        warn_print_report(
            "Failed to destroy all the vfs created due to:\n%s" % e)
    else:
        info_print_report(
            "Destroyed all the VFs created in this test case")

    # copy the pexpect interaction logfile with io domain to "$CTI_DIR" for
    # review , prevent being removed.
    if os.path.isfile(interaction_log):
        try:
            info_print_report(
                "Saving the interaction logfile of this test case")
            now = time.strftime("%Y%m%d%H%M%S")
            save_pexpect_interaction_logfile(
                "{0}/func01.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print_report(
                "Failed to save pexpect interaction logfile due to:\n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/func01.{1}".format(
                    interaction_dir, now))

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_test01_001
test_list[2] = tp_test01_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
