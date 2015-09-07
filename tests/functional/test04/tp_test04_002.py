#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_04/tp_test04_002
#
# DESCRIPTION:
#       Panic one root domain, IO domain with two paris of VFs, both are
#       configured with multipath. IO domain is alive during the reboot period
#       and the two paris of VFs is still ONLINE after the period
#
# STRATEGY:
#   	- Create two VFs from NPRD1,two VFs from NPRD2.
#       - Allocated these four VFs to the IO domain, VF0 from NPRD1 and VF0 from
#         NPRD2 are multipath configured. VF1 from NPRD1 and VF1 from NPRD2 are
#         multipath configured.
#   	- Panic root domain NPRD1 by 'echo "rootdir/W 0"|mdb -kw' in NPRD1.
#       - During panic NPRD1,IO domain should be alive.
#  		- During panic, check VF0 and VF1 created from NPRD1 by "hotplug list"
#         in IO domain, should be "OFFLINE". Check the logical paths from the
#         two VFs, should be seen.
#  		- During panic, check VF0 and VF1 created from NPRD2 by "hotplug list"
#         in IO domain, should be "ONLINE".
#   	- After panic, check VFs state by "hotplug list" in IO domain, all
#         should be "ONLINE"
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


def tp_test04_002():

    common.info_print_report("FC-IOR functional test04 TP2: panic")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")
    test_vfs_info_log = ctiutils.cti_getvar("TST_VFS")

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
