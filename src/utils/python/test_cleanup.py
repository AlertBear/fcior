#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import sys
import os
import traceback
import commands
import time
import shutil
import re


def info_print(string):
    print "INFO : %s" % string


def warn_print(string):
    print "WARN : %s" % string


def error_print(string):
    print "ERROR: %s" % string


def execute(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        raise Exception(
            "Execution of [%s] failed:\n%s" %
            (cmd, output))
    return output


def remove_vf_from_domain(vf, domain):
    """
    Purpose:
        Remove vf from ldom
    Arguments:
        vf - The specified vf to remove
        domain - The specified domain to remove from
    Return:
        None
    """
    cmd = 'ldm rm-io %s %s' % (vf, domain)
    execute(cmd)


def destroy_all_vfs_on_pf(pf):
    """
    Purpose:
        Destroy all the vfs that pf has created
    Arguments:
        pf - The pf where to destroy vfs
    Return:
        None
    """
    vfs_list = list_all_vfs_on_pf(pf)
    for vf in vfs_list:
        cmd = 'ldm list-io -l -p %s|grep %s' % (pf, vf)
        output = execute(cmd)
        # The vf has been bound to a domain,need to be removed
        domain = output.split('|')[4].split('=')[1]
        if domain != '':
            try:
                remove_vf_from_domain(vf, domain)
            except Exception as e:
                raise e
            else:
                time.sleep(3)

    # Destroy all the vfs created under the pf
    cmd_destroy = 'ldm destroy-vf -n max %s' % pf
    execute(cmd_destroy)


def list_all_vfs_on_pf(pf):
    """
    Purpose:
        List all vfs that pf has created
    Arguments:
        pf - PF name
    Return:
        vfs_list - All vfs that pf has created
    """
    cmd = 'ldm list-io | grep %s' % pf
    output = execute(cmd)
    pattern = re.compile(r'{0}\.VF\d+'.format(pf))
    match = pattern.findall(output)
    if match is None:
        return None
    vfs_list = match
    return vfs_list


def delete_path(path):
    """
    Purpose:
        Remove the directory
    Arguments:
        path - The directory to remove
    Return:
        None
    """
    if os.path.exists(path):
        shutil.rmtree(path)


def main():
    # Get all the variables
    # Get by reading the config file instead of getting from
    # environment variable which is unable to access
    cti_suite_path = os.getenv("CTI_SUITE")
    config_file = cti_suite_path + '/config/test_config'

    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'TMPPATH=.*', line):
                tmp_path = line.split('=')[1]
                break

    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'XMLPATH=.*', line):
                xml_path = line.split('=')[1]
                break

    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'PF_A=.*', line):
                pf_1 = line.split('=')[1]
                break

    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'PF_B=.*', line):
                pf_2 = line.split('=')[1]
                break

    # destroy all the vf that has created on the pf
    pf_list = [pf_1, pf_2]
    for pf in pf_list:
        try:
            info_print(
                "Destroying the VFs created on %s" % pf)
            destroy_all_vfs_on_pf(pf)
        except Exception as e:
            warn_print("Failed due to:\n%s" % e)
        else:
            info_print("Done")

    # Delete the xml path where to save the VFS_INFO.xml and TST_VFS.xml
    try:
        info_print("Trying to delete xml path %s" % xml_path)
        delete_path(xml_path)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print(
            "Failed to delete xml path used in tests" % xml_path)
        return 1
    else:
        info_print("Deleted done")

    # Delete the temporary logfile path
    try:
        info_print("Trying to delete temporary path %s" % tmp_path)
        delete_path(tmp_path)
    except Exception as e:
        error_print(e)
        error_print(traceback.print_exc())
        error_print(
            "Failed to delete temporary path used in tests" % tmp_path)
        return 1
    else:
        info_print("Deleted done")

    return 0

if __name__ == "__main__":
    print "*********************************************************"
    print "                  FC-IOR TEST CLEANUP                    "
    print "*********************************************************"
    if main() == 0:
        print "*********************************************************"
        exit(0)
    else:
        print "*********************************************************"
        exit(1)
