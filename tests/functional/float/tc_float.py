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
from tp_float_reboot_reboot_001 import tp_float_reboot_reboot_001
from tp_float_panic_panic_002 import tp_float_panic_panic_002
from tp_float_reboot_panic_003 import tp_float_reboot_panic_003


def startup():

    info_print_report("FC-IOR functional float:  startup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # allocate vfs to the io domain
    a_vf = pf_1 + '.VF0'
    b_vf = pf_2 + '.VF0'
    vfs_list = [a_vf, b_vf]

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

    # io workload operate
    info_print_report(
        "Checking the io workload file whether exists in io domain [%s]" %
        iod_name)
    if check_io_workload_exists(iod_name, iod_password):
        info_report(
            "IO workload file alerady exists in io domain [%s]" % iod_name)
    else:
        info_report(
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
            "Run I/O workload on VF [%s] in io domain [%s]" % (a_vf, iod_name))
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
    pf_1_vfs_dict = {}
    for vf in a_vfs_list:
        pf_1_vfs_dict.update({vf: iod_name})
    pf_2_vfs_dict = {}
    for vf in b_vfs_list:
        pf_2_vfs_dict.update({vf: iod_name})
    test_vfs_dict = {
        nprd1_name: {
            pf_1: pf_1_vfs_dict
        },
        nprd2_name: {
            pf_2: pf_2_vfs_dict
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

    info_print_report("FC-IOR functional float:  cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact"

    # if zfs file system has been created in this case, destroy it
    try:
        info_print_report("Cleanup file system in io domain [%s]" % iod_name)
        destroy_file_system_in_domain(iod_name, iod_password)
    except Exception as e:
        warn_print_report(
            "Failed to destroy the file system in io domain [%s] due to:\n%s" %
            (iod_name, e))
    else:
        info_print_report("Destroyed the file system success")

    # remove all the test vfs that has been bound to the io domain
    for i in range(0, 1):
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

    for i in range(0, 1):
        vf = pf_2 + '.VF{0}'.format(i)
        try:
            info_print_report(
                "Removing %s from %s..." % (vf, iod_name))
            remove_vf_from_domain(vf, iod_name)
        except Exception as e:
            warn_print_report("Failed due to:\n%s" % e)
        else:
            info_print_report("Remove done")
            time.sleep(5)

    # copy the pexpect interaction logfile with io domain to "$CTI_LOGDIR" for
    # review , prevent being removed.
    if os.path.isfile(interaction_log):
        try:
            info_print_report(
                "Saving the interaction logfile of this test case")
            now = time.strftime("%Y%m%d%H%M%S")
            save_pexpect_interaction_logfile(
                "{0}/float.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print_report(
                "Failed to save pexpect interaction logfile due to:\n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/float.{1}".format(
                    interaction_dir, now))

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_float_reboot_reboot_001
test_list[2] = tp_float_panic_panic_002
test_list[3] = tp_float_reboot_panic_003

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
