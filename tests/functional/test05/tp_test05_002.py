#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_05/tp_test05_002
#
# DESCRIPTION:
#       Panic one root domain, IO domain with two VFs configured with Multipath
#       is alive during the period and the two VFs with IO workload is still
#       ONLINE after the period.
#
# STRATEGY:
#   	- Create two VFs from two root domains seperately.
#       - Allocated these two VFs to the IO domain, they are multipath configured.
#       - Run IO workload on the two VFs link.
#       - Panic root domain NPRD1 by "echo 'rootdir/W 0|mdb -kw'" in NPRD1.
#       - During panic NPRD1,IO domain should be alive.
#  		- During panic, check VF created from NPRD1 by "hotplug list" in
#         IO domain, should be "OFFLINE", check the logical path from VF,
#         should be seen, check the IO workload, still continue on the
#         alternative path.
#  		- During panic, check VF created from NPRD2 by "hotplug list" in
#         IO domain, should be "ONLINE".
#   	- After panic, check VFs state by "hotplug list" in IO domain,both
#         should be "ONLINE", check the logical path from VF, should be seen,
#         check the IO workload, should continue as nothing happended.
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


def tp_test05_002():

    common.info_print_report("FC-IOR functional test05 TP1: panic")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")
    all_vfs_info_xml = ctiutils.cti_getvar("VFS_INFO")

    operate_type = 'panic'
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
            all_vfs_info_xml,
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
