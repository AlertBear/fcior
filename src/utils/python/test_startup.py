#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import os
import time
import traceback
from common import *


if __name__ == "__main__":
    print "*********************************************************"
    print "                  FC-IOR TEST STARTUP                    "
    print "*********************************************************"
    # Get all the variables
    tmp_path = os.getenv("TMPPATH")
    xml_path = os.getenv("XMLPATH")

    root_domain_1_name = os.getenv("NPRD_A")
    root_domain_2_name = os.getenv("NPRD_B")
    iod_name = os.getenv("IOD")

    root_domain_1_password = os.getenv("NPRD_A_PASSWORD")
    root_domain_2_password = os.getenv("NPRD_B_PASSWORD")
    iod_password = os.getenv("IOD_PASSWORD")

    pf_1 = os.getenv("PF_A")
    pf_2 = os.getenv("PF_B")

    # Create temporary logfile path
    try:
        info_print("Trying to create temporary path [%s]" % tmp_path)
        create_path(tmp_path)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print(
            "Failed to create temporary path used in tests" % tmp_path)
        exit(1)
    else:
        info_print("Created done")

    # Check the io domain whether support ior test
    try:
        info_print(
            "Checking IO domain [%s] whether support ior test" % iod_name)
        check_io_domain_runmode(iod_name, iod_password)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print("IO domain [%s] doesn't support ior test" % iod_name)
        exit(1)
    else:
        info_print("IO domain [%s] support ior test" % iod_name)

    # Check the root domains whether support ior test
    nprd_name = [root_domain_1_name, root_domain_2_name]
    try:
        info_print(
            "Checking ROOT domain [%s] whether support ior test" % nprd_name)
        check_root_domain_runmode(*nprd_name)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print("Root domain [%s] doesn't support ior test" % nprd_name)
        exit(1)
    else:
        info_print("Root domain [%s] support ior test" % nprd_name)

    # Check the pf whether support ior test
    pf_list = [pf_1, pf_2]
    try:
        info_print(
            "Checking PF [%s] whether support ior test" % pf_list)
        check_pf_support_ior(*pf_list)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print("PF [%s] doesn't support ior test" % pf_list)
        exit(1)
    else:
        info_print("PF [%s] support ior test" % pf_list)

    # Check whether pf_1 belong to nprd1 and pf_2 belong to nprd2
    ldom_pf_dict = {root_domain_1_name: pf_1, root_domain_2_name: pf_2}
    try:
        info_print(
            "Checking PFs whether belong to the root domains")
        check_pfs_domains_relation(ldom_pf_dict)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        exit(1)
    else:
        info_print("Done")

    # Check the pf whether has created vf, if yes,destroyed
    for pf_item in pf_list:
        info_print("Checking PF [%s] whether has created vf" % pf_item)
        if check_whether_pf_has_created_vf(pf_item):
            info_print(
                "VF has been created on PF [%s], trying to destroy..." %
                pf_item)
            try:
                destroy_all_vfs_on_pf(pf_item)
            except Exception as e:
                error_print(e)
                error_print(traceback.print_exc())
                error_print(
                    "Failed to destroy all the vfs created on the PF [%s]" %
                    pf_item)
                exit(1)
            else:
                info_print(
                    "Destroyed all the vfs created on PF [%s]" % pf_item)
        else:
            info_print("No vf has been created on PF [%s]" % pf_item)
        time.sleep(3)

    # Create vf by manually assign port-wwn and node-wwn
    vfs1_list = []

    for i in range(0, 3):
        port_wwn = os.getenv("PORT_WWN_PF_A_VF{0}".format(i))
        node_wwn = os.getenv("NODE_WWN_PF_A_VF{0}".format(i))
        try:
            info_print("Creating vf on PF [%s]" % pf_1)
            vf = create_vf_in_manual_mode(pf_1, port_wwn, node_wwn)
        except Exception as e:
            error_print(e)
            error_print(traceback.print_exc())
            error_print("Failed to create vf on the PF [%s]" % pf_1)
            exit(1)
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_1))
            vfs1_list.append(vf)
            time.sleep(3)

    vfs2_list = []
    for i in range(0, 3):
        port_wwn = os.getenv("PORT_WWN_PF_B_VF{0}".format(i))
        node_wwn = os.getenv("NODE_WWN_PF_B_VF{0}".format(i))
        try:
            info_print("Creating vf on PF [%s]" % pf_2)
            vf = create_vf_in_manual_mode(pf_2, port_wwn, node_wwn)
        except Exception as e:
            error_print(e)
            error_print(traceback.print_exc())
            error_print("Failed to create vf on the PF [%s]" % pf_2)
            exit(1)
        else:
            info_print("Created vf [%s] on pf [%s]" % (vf, pf_2))
            vfs2_list.append(vf)
            time.sleep(3)

    # Create xml path where to save the VFS_INFO.xml and TST_VFS.xml
    try:
        info_print("Trying to create xml path [%s]" % xml_path)
        create_path(xml_path)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print(
            "Failed to create xml path used in tests" % xml_path)
        exit(1)
    else:
        info_print("Created done")

    # Get all created vfs info and save to xml file
    vfs_info_log = os.getenv("VFS_INFO")
    vfs_dict = {pf_1: vfs1_list, pf_2: vfs2_list}
    try:
        info_print("Getting all above vfs info...")
        save_init_vfs_info_to_xml(vfs_dict, vfs_info_log)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print("Failed to get all above vfs info")
        exit(1)
    else:
        info_print("Done")

    exit(0)

