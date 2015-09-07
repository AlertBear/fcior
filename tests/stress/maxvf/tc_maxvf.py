#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import ctiutils
import pytet
import traceback
import os
import time
from common import *

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

    # create vf by manually assign port-wwn and node-wwn
    vfs_list = []
    a_vfs_list = []
    b_vfs_list = []

    for i in range(0, 2):
        vf = pf_1 + '.VF{0}'.format(i)
        vfs_list.append(vf)
        a_vfs_list.append(vf)

    maxvf_num_1 = int(get_pf_maxvf_number(pf_1))
    for i in range(3, maxvf_num_1):
        try:
            info_print_report("Creating vf on PF [%s]" % pf_1)
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
            time.sleep(15)

    for i in range(0, 2):
        vf = pf_2 + '.VF{0}'.format(i)
        vfs_list.append(vf)
        b_vfs_list.append(vf)

    maxvf_num_2 = int(get_pf_maxvf_number(pf_2))
    for i in range(3, maxvf_num_2):
        try:
            info_print_report("Creating vf on PF [%s]" % pf_2)
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
            time.sleep(15)

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
    for vf in a_vfs_list:
        pf_1_vfs_dict.update({vf: iod_name})

    test_vfs_dict = {
        nprd1_name: {
            pf_1: pf_1_vfs_dict
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

    info_print_report("FC-IOR stress maxvf:  cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact"

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

    # remove all the test vfs that has been bound to the io domain
    maxvf_num_1 = int(get_pf_maxvf_number(pf_1))
    for i in range(0, maxvf_num_1):
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

    maxvf_num_2 = int(get_pf_maxvf_number(pf_2))
    for i in range(0, maxvf_num_2):
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

    # destroy all the vf that has created in this test case
    maxvf_num_1 -= 1
    for i in range(maxvf_num_1, 2, -1):
        vf = pf_1 + '.VF{0}'.format(i)
        try:
            info_print_report(
                "Destroying %s" % vf)
            destroy_vf(vf)
        except Exception as e:
            warn_print_report("Failed due to:\n%s" % e)
            return 1
        else:
            info_print_report("Destroyed done")
            time.sleep(15)

    maxvf_num_2 -= 1
    for i in range(maxvf_num_2, 2, -1):
        vf = pf_2 + '.VF{0}'.format(i)
        try:
            info_print_report(
                "Destroying %s" % vf)
            destroy_vf(vf)
        except Exception as e:
            warn_print_report("Failed due to:\n%s" % e)
            return 1
        else:
            info_print_report("Destroyed done")
            time.sleep(15)

    # copy the pexpect interaction logfile with io domain to "$CTI_LOGDIR" for
    # review , prevent being removed.
    if os.path.isfile(interaction_log):
        try:
            info_print_report(
                "Saving the interaction logfile of this test case")
            now = time.strftime("%Y%m%d%H%M%S")
            save_pexpect_interaction_logfile(
                "{0}/maxvf.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print(
                "Failed to save pexpect interaction logfile due to:\n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/maxvf.{1}".format(interaction_dir, now))

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_maxvf_001
test_list[2] = tp_maxvf_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
