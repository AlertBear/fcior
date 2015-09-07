#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_02/tp_test02_001
#
# DESCRIPTION:
#       Reboot one root domain, IO domain with two VFs from this single root domain
#       is alive during the period and the two VFs is still ONLINE after the period
#
# STRATEGY:
#   	- Create two VFs from a single domain.
#       - Allocated these two VFs to the IO domain.
#       - Reboot root domain by "reboot" in this domain.
#       - During reboot root domain,IO domain should be alive.
#  		- During reboot, check VFs state by "hotplug list" in IO domain,
#     	  should be "OFFLINE". Check the logical path from VF, should be None.
#  		- During reboot, check VFs state by "hotplug list" in IO domain,
#     	  should be "ONLINE".
#   	- After reboot, check VFs state by "hotplug list" in IO domain,
#         both should be "ONLINE"
#
# TESTABILITY: implicit
#
# AUTHOR: daijie.x.guo@oracle.com
#
# REVIEWERS:
#
# TEST AUTOMATION LEVEL: automated
#
# CODING_STATUS:  COMPLETED
#
# __stc_assertion_end
#
##########################################################################

import threading
import ctiutils
import common
import time


def tp_test02_001():

    common.info_print_report("FC-IOR functional test02 TP1: reboot")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")
    test_vfs_info_log = ctiutils.cti_getvar("TST_VFS")

    operate_type = 'reboot'
    nprd_dict = {
        nprd: {
            'password': nprd_password,
            'operate_type': operate_type,
            'operate_count': 1}}
    iods_dict = {iod: iod_password}
    # reboot root domain, check the io domain status
    event = threading.Event()

    root_domain_thread = common.operate_domain_thread(
        'Thread-' +
        nprd,
        event,
        nprd_dict)
    root_domain_thread.start()

    time.sleep(3)
    try:
        result = common.check_ior_in_domain(
            iods_dict,
            nprd_dict,
            test_vfs_info_log,
            event)
    except Exception as e:
        common.error_print_report(e)
        common.error_report(ctiutils.cti_traceback())
        ctiutils.cti_unresolved()
    else:
        if result == 0:
            ctiutils.cti_pass("pass")
        elif result == 1:
            ctiutils.cti_fail("fail")
        else:
            ctiutils.cti_unresolved()
