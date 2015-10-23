#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_01/tp_panic
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
#   	- Panic root domain NPRD1 by "echo 'roodir/W 0'|mdb -kw" in NPRD1.
#       - During panic NPRD1,IO domain should be alive.
#       - During panic, check all VFs by "hotplug list" in IO domain,
#         all should be "OFFLINE", Check the logical paths from the two VFs,
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
import basic


def tp_test01_002():

    basic.info_print_report("FC-IOR functional test01 TP2: panic")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

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
            event)
    except Exception as e:
        basic.error_print_report(e)
        basic.error_report(ctiutils.cti_traceback())
        ctiutils.cti_unresolved()
    else:
        if result == 0:
            ctiutils.cti_pass("pass")
        elif result == 1:
            ctiutils.cti_fail("fail")
        else:
            ctiutils.cti_unresolved()
