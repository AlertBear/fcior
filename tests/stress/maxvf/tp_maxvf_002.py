#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       stress/maxvf/tp_maxvf_002
#
# DESCRIPTION:
#       Reboot root domain, IO domain with max VFs created from two root domain
#       is alive during the reboot period and the VFs is still ONLINE after reboot
#
# STRATEGY:
#   	- Create max VFs of a port from NPRD1 and max VFs of a port from NPRD2,
#         at least, 2 pairs are multi-path configured.
#       - Allocated these VFs to the IO domain, run vdbench on 2 VFs which are
#         multi-path configured.
#   	- Reboot NPRD1 by "echo 'roodir/W 0'|mdb -kw".
#       - During reboot NPRD1, IO domain should be alive.
#  		- During reboot, check VFs from NPRD1 by "hotplug list" in IO domain,
#         should be "OFFLINE". check the IO workload, still continue on the
#         alternative path.
#  		- During reboot, check VF created from NPRD2 by "hotplug list" in IO
#         domain, should be "ONLINE".
#   	- After reboot, check VFs state by "hotplug list" in IO domain, all
#         should be "ONLINE", check IO workload, should continue as nothing
#         happended.
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


def tp_maxvf_002():

    common.info_print_report("FC-IOR stress maxvf TP2: panic")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")
    all_vfs_info_xml = ctiutils.cti_getvar("VFS_INFO")

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
