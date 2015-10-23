#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/test_03/tp_test03_001
#
# DESCRIPTION:
#       Reboot one root domain, IO domain with two VFs(one is ONLINE,the other
#       is OFFLINE) is alive during the period, the ONLINE VF is still ONLINE
#       and the OFFLINE VF is still OFFLINE after the period
#
# STRATEGY:
#   	- Create two VFs from the same root domains.
#       - Allocated these two VFs to the IO domain, keep VF0 as ONLINE and VF1
#         as OFFLINE.
#   	- Reboot root domain by "reboot" in root domain.
#       - During reboot,IO domain should be alive.
#  		- During reboot, check VF0 by "hotplug list" in IO domain,
#     	  should be "OFFLINE".
#  		- During reboot, check VF1 by "hotplug list" in IO domain,
#     	  should be "OFFLINE".
#   	- After reboot, check VFs state by "hotplug list" in IO domain, VF0 is
#         ONLINE, VF1 is OFFLINE.
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


def tp_test03_001():

    basic.info_print_report("FC-IOR functional test03 TP1: reboot")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

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
