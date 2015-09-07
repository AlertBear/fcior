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
from tp_multidom_001 import tp_multidom_001
from tp_multidom_002 import tp_multidom_002


def startup():

    info_print_report("FC-IOR stress multidom:  startup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    # get the root domain and io domain from configuration file
    nprd1_name = ctiutils.cti_getvar("NPRD_A")
    nprd2_name = ctiutils.cti_getvar("NPRD_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    # before create the other test io domains, check the vdbench files whether
    # exists
    try:
        info_print_report(
            "Checking vdbench file whether exists in io domain [%s]" % iod_name)
        check_vdbench_exists(iod_name, iod_password)
    except Exception as e:
        error_print_report(
            "Vdbench file doesn't exist in io domain [%s]" % iod_name)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall(
            "Vdbench file doesn't exist in io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report(
            "Vdbench file already exists in io domain [%s]" % iod_name)

    # create the other created io domains by cloning the io domain above
    maxvf_num_1 = int(get_pf_maxvf_number(pf_1))
    maxvf_num_2 = int(get_pf_maxvf_number(pf_2))
    if maxvf_num_2 > maxvf_num_1:
        support_maxvf_num = maxvf_num_1
    else:
        support_maxvf_num = maxvf_num_2

    iods_list = []
    for i in range(1, support_maxvf_num):
        iod_name_new = ctiutils.cti_getvar("IOD_{0}".format(i))
        iods_list.append(iod_name_new)

    iod_volume_list = []
    try:
        info_print_report("Trying to snapshot io domain [%s]" % iod_name)
        iod_volume_list = get_volume_of_domain(iod_name)
        if len(iod_volume_list) > 1:
            error_print_report(
                "IO domain [%s] has more than one volume, cancel snapshot" %
                iod_name)
            ctiutils.cti_deleteall(
                "IO domain [%s] has more than one volume" % iod_name)
            return 1
        else:
            iod_volume = iod_volume_list[0]
            iod_volume_snapshot = snapshot_volume(iod_volume)
    except Exception as e:
        error_print_report(e)
        error_report(traceback.print_exc())
        ctiutils.cti_deleteall("Failed to snapshot io domain [%s]" % iod_name)
        return 1
    else:
        info_print_report("Snapshot Done")

    for creating_iod in iods_list:
        try:
            info_print_report("Trying to create io domain [%s]" % creating_iod)
            create_domain_by_clone_snapshot(iod_volume_snapshot, creating_iod)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to create io domain [%s]" % creating_iod)
            return 1
        else:
            info_print_report("Create Done")

    # wait the created io domains to boot up
    info_print_report("Waitting all the new created io domains to boot up...")
    time.sleep(360)
    for creating_iod in iods_list:
        try:
            check_domain_boot_up(creating_iod, iod_password)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "IO domain [%s] is not up and not able to login" % creating_iod)
            return 1
    info_print_report("All the created io domains are up and be able to test")

    # create vf by manually assign port-wwn and node-wwn
    vfs_list = []

    a_vfs_list = []
    for i in range(0, 3):
        vf = pf_1 + '.VF{0}'.format(i)
        vfs_list.append(vf)
        a_vfs_list.append(vf)

    for i in range(3, support_maxvf_num):
        try:
            info_print_report("Creating vf on PF [%s]" % pf_1)
            vf = create_vf_in_dynamic_mode(pf_1)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_1)
            return 1
        else:
            info_print("Created [%s] done" % vf)
            a_vfs_list.append(vf)
            time.sleep(15)

    b_vfs_list = []
    for i in range(0, 3):
        vf = pf_2 + '.VF{0}'.format(i)
        vfs_list.append(vf)
        b_vfs_list.append(vf)

    for i in range(3, support_maxvf_num):
        try:
            info_print_report("Creating vf on PF [%s]" % pf_2)
            vf = create_vf_in_dynamic_mode(pf_2)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall("Failed to create vf on the PF [%s]" % pf_2)
            return 1
        else:
            info_print_report("Created [%s] done" % vf)
            b_vfs_list.append(vf)
            time.sleep(15)

    # allocate vfs to the io domain
    iods_list = [iod_name]
    for i in range(1, support_maxvf_num):
        iods_list.append(ctiutils.cti_getvar("IOD_{0}".format(i)))
    a_vfs_iod_dict = {}
    for i in range(0, support_maxvf_num):
        a_vf = a_vfs_list[i]
        assigned_iod_name = iods_list[i]
        try:
            info_print_report(
                "Allocating vf [%s] to io domain [%s]" %
                (a_vf, assigned_iod_name))
            assign_vf_to_domain(a_vf, assigned_iod_name)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to assign the vf [%s] to domain [%s] " %
                (a_vf, assigned_iod_name))
            return 1
        else:
            info_print_report(
                "VF [%s] has been allocated to io domain [%s]" %
                (a_vf, assigned_iod_name))
            time.sleep(5)
            a_vfs_iod_dict.update({a_vf: assigned_iod_name})

        b_vf = b_vfs_list[i]
        try:
            info_print_report(
                "Allocating vf [%s] to io domain [%s]" %
                (b_vf, assigned_iod_name))
            assign_vf_to_domain(b_vf, assigned_iod_name)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "Failed to assign the vf [%s] to domain [%s] " %
                (b_vf, assigned_iod_name))
            return 1
        else:
            info_print_report(
                "VF [%s] has been allocated to io domain [%s]" %
                (b_vf, assigned_iod_name))
            time.sleep(5)

    # reboot all io domains

    threads_list = []
    for rebooting_iod in iods_list:
        thread_rebooting_iod = threading.Thread(
            target=reboot_domain,
            args=(
                rebooting_iod,
                iod_password))
        threads_list.append(thread_rebooting_iod)
    info_print_report("Rebooting all io domains after allocated vfs ...")

    for thread_rebooting_iod in threads_list:
        thread_rebooting_iod.start()
    for thread_rebooting_iod in threads_list:
        thread_rebooting_iod.join()

    for rebooting_iod in iods_list:
        try:
            check_domain_boot_up(rebooting_iod, iod_password)
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
            ctiutils.cti_deleteall(
                "IO domain [%s] is not up and not able to login" %
                rebooting_iod)
            return 1

    # io workload operate
    for i in range(0, 3):
        info_print_report("Run vdbench in io domain [%s]..." % iods_list[i])
        try:
            run_vdbench_on_vf_in_domain(
                iods_list[i],
                iod_password,
                vfs_1_list[i])
        except Exception as e:
            error_print_report(e)
            error_report(traceback.print_exc())
        else:
            info_print_report("Done")
        time.sleep(5)

    # Get the test vfs info dict
    iod_info_dict = {"name": iod_name, "password": iod_password}
    pf_1_vfs_dict = {}
    for vf, affiliated_iod in a_vfs_iod_dict.items():
        pf_1_vfs_dict.update({vf: affiliated_iod})

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

    info_print_report("FC-IOR stress multidom: cleanup")

    pf_1 = ctiutils.cti_getvar("PF_A")
    pf_2 = ctiutils.cti_getvar("PF_B")
    iod_name = ctiutils.cti_getvar("IOD")
    iod_password = ctiutils.cti_getvar('IOD_PASSWORD')
    interaction_log = os.getenv("INT_LOG")
    interaction_dir = os.getenv("CTI_LOGDIR") + "/interact"

    iods_destroy = []
    for i in range(1, 15):
        check_iod = ctiutils.cti_getvar("IOD_{0}".format(i))
        try:
            check_domain_exists(check_iod)
        except Exception as e:
            pass
        else:
            iods_destroy.append(check_iod)

    # destroy all the io domains created in the case
    try:
        info_print_report(
            "Destroying all the io domains created in this test case")
        destroy_domain(*iods_destroy)
    except Exception as e:
        warn_print_report(
            "Failed to destroy [%s] created in this case, destroy manually" %
            iods_destroy)
    else:
        info_print_report("Destroy done")

    # destroy the snapshot of the io domain
    info_print_report(
        "Destroying the snapshot created on [%s] in this test case" %
        iod_name)
    try:
        destroy_snapshot_of_domain(iod_name)
    except Exception as e:
        warn_print_report(
            "Failed to destroy the snapshot created on [%s], destroy manually" %
            iod_name)
    else:
        info_print_report("Destroyed the snapshot done")

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

    # destroy all the vf that has created in this test case
    maxvf_num_1 = int(get_pf_maxvf_number(pf_1))
    maxvf_num_2 = int(get_pf_maxvf_number(pf_2))
    if maxvf_num_2 > maxvf_num_1:
        support_maxvf_num = maxvf_num_1
    else:
        support_maxvf_num = maxvf_num_2

    a_support_maxvf_num = support_maxvf_num - 1
    for i in range(a_support_maxvf_num, 2, -1):
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

    b_support_maxvf_num = support_maxvf_num - 1
    for i in range(b_support_maxvf_num, 2, -1):
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
                "{0}/multidom.{1}".format(interaction_dir, now))
        except Exception as e:
            warn_print_report(
                "Failed to save pexpect interaction logfile due to:\n%s" % e)
        else:
            info_print_report(
                "Test user could review the interaction "
                "logfile {0}/interaction.multidom.{1}".format(
                    interaction_dir, now))

#
# construct the test list
# NOTE:  The values in this dictionary are functions, not strings
#
test_list = {}
test_list[1] = tp_multidom_001
test_list[2] = tp_multidom_002

# Initialize the test
ctiutils.cti_init(test_list, startup, cleanup)
