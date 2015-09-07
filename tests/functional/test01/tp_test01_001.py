#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_01/tp_test01_001
#
# DESCRIPTION:
#       Reboot one root domain, IO domain with two paris of VFs. One pair is
#       from one port of the FC device, and the other one is from the remainning
#       one port of the FC device. IO domain is alive during the reboot period
#       and the two paris of VFs are still ONLINE after the period.
#
# STRATEGY:
#   	- Create two VFs from PF0, two VFs from PF1, they are affliated to NPRD1.
#       - Allocated these four VFs to the IO domain.
#   	- Reboot root domain NPRD1 by "reboot" in NPRD1.
#       - During reboot NPRD1,IO domain should be alive.
#  	    - During reboot, check all VFs by "hotplug list" in IO domain, all
#         should be "OFFLINE", Check the logical paths from the two VFs,
#         should be none.
#   	- After reboot, check VFs state by "hotplug list" in IO domain,
#         all should be "ONLINE"
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

import ctiutils
import threading
import common
import time


def tp_test01_001():

    common.info_print_report("FC-IOR functional test01 TP1: reboot")

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
