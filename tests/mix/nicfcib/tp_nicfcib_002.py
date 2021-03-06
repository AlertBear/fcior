#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       mix/mix_nicfcib/tp_mix_nic_fc_ib_002
#
# DESCRIPTION:
#       Panic root domain, IO domain with two FC VFs configured with MPxIO,
#       two NIC VFs configured with IPMP and two IB VFs configured with IPMP
#       is alive during the panic period.
#       Besides, the two FC VFs where running IO workload are still ONLINE and
#       io workload continues after panic. The two NIC vfs where running IO
#       workload are still ONLINE and io workload continues after panic. The
#       two IB VFs where running io workload are still ONLINE and io workload
#       are continues after panic.
#
# STRATEGY:
#       - Create two FC VFs separately from two PFs in NPRD1 and NPRD2, create
#         two NIC VFs separately from two PFs in NPRD1 and NPRD2 and create two
#         two IB VFs separately from two PFs in NPRD1 and NPRD2.
#       - Allocated two FC VFs to the IO domain, run io workload on these two
#         VFs which are MPxIO configured.
#       - Allocated two NIC VFs configured with IPMP to the IO domain, run IO
#         workload on these two VFs.
#       - Allocated two IB VFs to the IO domain, create IPoIB interface on IB
#         VFs. Run io workload on these two VFs.
#       - Panic NPRD2 by "echo 'roodir/W 0'#mdb -kw".
#       - During panic NPRD2, IO domain should be alive.
#       - During panic, check FC VFs from NPRD2 by "hotplug list" in IO domain,
#         should be "OFFLINE". check the IO workload, still continues on the
#         alternative path. Check VF created from NPRD1 by "hotplug list" in IO
#         domain, should be "ONLINE".
#       - During panic, check NIC VF from NPRD2 by "hotplug list" in IO domain,
#         should be "MAINTENANCE-SUSPENDED". Ping the IPMP interface, should
#         successfully. Check ipmpstat with "ipmpstat -g" and "ipmpstat -i", the
#         state should be degraded/failed. Check io workload, still continues on
#         the alternative path. Check VF created from NPRD1 by "hotplug list" in
#         IO domain, should be "ONLINE".
#       - During panic, check IB VF from NPRD2 by "hotplug list" in IO domain,
#         should be "OFFLINE". Ping the IPMP interface, should successfully.
#         Check ipmpstat with "ipmpstat -g" and "ipmpstat -i", the state should
#         be degraded/failed. Check io workload, still continues on the
#         alternative path. Check VF created from NPRD1 by "hotplug list" in IO
#         domain, should be "ONLINE".
#       - After panic, check VFs state by "hotplug list" in IO domain, all
#         should be "ONLINE". Check io workload on FC/NIC/IB VFs separately,
#         should continue as nothing happened. ping NIC IPMP interface and IB
#         IPMP interface, should successfully. Check ipmpstat with "ipmpstat -g"
#         and "ipmpstat -i", the state should be normal.
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


def tp_nicfcib_002():

    common.info_print_report("FC-IOR mix nicfcib TP2: panic")

    nprd = ctiutils.cti_getvar("NPRD_B")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_B_PASSWORD")
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
