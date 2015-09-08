#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

import os
import traceback
import shutil
import re
import getopt
import sys

def info_print(string):
    print "INFO : %s" % string


def warn_print(string):
    print "WARN : %s" % string


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


if __name__ == "__main__":

    print "*********************************************************"
    print "                  FC-IOR TEST CLEANUP                    "
    print "*********************************************************"

    # test_cleanup will be always executed with several parameters
    # including "-r, -f, -e, -s, -S"
    # Get the runtime config file by "-e" parameter
    shortargs = 'r:f:e:s:S:'
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortargs)
    except getopt.GetoptError as e:
        warn_print(e)
        warn_print(traceback.print_exc())
        warn_print(
            "Failed to get the runtime config file in cleanup")
        exit(1)

    config_file = None
    for opt, value in opts:
        if opt in ('-e',):
            config_file = value

    if config_file is None:
        warn_print(
            "Failed to get the runtime config file in cleanup")
        exit(1)

    # Get by reading the config file instead of getting from
    # environment variable which is unable to access
    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'TMPPATH=.*', line):
                tmp_path = line.split('=')[1].strip()
                break

    with open(config_file, 'r+') as f:
        while 1:
            line = f.readline()
            if re.search(r'XMLPATH=.*', line):
                xml_path = line.split('=')[1].strip()
                break

    # Delete the xml path where to save the VFS_INFO.xml and TST_VFS.xml
    try:
        info_print("Trying to delete xml path %s" % xml_path)
        delete_path(xml_path)
    except Exception as e:
        warn_print(e)
        warn_print(traceback.print_exc())
        warn_print(
            "Failed to delete xml path used in tests" % xml_path)
        exit(1)
    else:
        info_print("Deleted done")

    # Delete the temporary logfile path
    try:
        info_print("Trying to delete temporary path %s" % tmp_path)
        delete_path(tmp_path)
    except Exception as e:
        warn_print(e)
        warn_print(traceback.print_exc())
        warn_print(
            "Failed to delete temporary path used in tests" % tmp_path)
        exit(1)
    else:
        info_print("Deleted done")

    exit(0)
