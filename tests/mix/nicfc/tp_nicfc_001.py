#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       mix/nicfc/tp_nicfc_001
#
# DESCRIPTION:
#       Reboot root domain, IO domain with two FC VFs configured with MPxIO
#       and two NIC VFs configured with IPMP is alive during the reboot period.
#       Besides, the two FC VFs where running IO workload is still ONLINE and
#       IO workload continues after reboot. Meanwhile, the NIC vfs are still
#       ONLINE after reboot.
#
# STRATEGY:
#       - Create two FC VFs separately from two PFs in NPRD1 and NPRD2, and
#         create two NIC VFs separately from two PFs in NPRD1 and NPRD2.
#       - Allocated two FC VFs to the IO domain, run io workload on these two
#         VFs which are MPxIO configured.
#       - Allocated two NIC VFs configured with IPMP to the IO domain.
#       - Reboot NPRD1 by "reboot".
#       - During reboot NPRD1, IO domain should be alive.
#       - During reboot, check FC VFs from NPRD1 by "hotplug list" in IO domain,
#         should be "OFFLINE". check the IO workload, still continues on the
#         alternative path. Check VF created from NPRD2 by "hotplug list" in IO
#         domain, should be "ONLINE".
#       - During reboot, check NIC VF from NPRD1 by "hotplug list" in IO domain,
#         should be "MAINTENANCE-SUSPENDED". Ping the IPMP interface, should
#         successfully. Check NIC VF created from NPRD2 by "hotplug list" in IO
#         domain, should be "ONLINE". Check ipmp state with "ipmpstat -g" and
#         "ipmpstat -i", the stat should be degraded/failed.
#       - After reboot, check VFs state by "hotplug list" in IO domain, all
#         should be "ONLINE". Check IO workload on FC VFs, should continue as
#         nothing happened. Ping IPMP interface, should successfully.Check ipmp
#         state with "ipmpstat -g" and "ipmpstat -g", the state should be normal.
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


def tp_nicfc_001():

    common.info_print_report("FC-IOR mix nicfc TP1: reboot")

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
