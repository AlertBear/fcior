#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       functional/float/tp_float_panic_panic_002
#
# DESCRIPTION:
#       Panic two root domains simutaneously, IO domain with two VFs configured
#       with Multipath is alive during the period and the two VFs with IO
#       workload is still ONLINE after the period.
#
# STRATEGY:
#   	- Create two VFs from two root domains seperately.
#       - Allocated these two VFs to the IO domain, they are multipath configured.
#       - Run IO workload on the two VFs link.
#   	- Panic root domains NPRD1 and NPRD2 by 'echo "rootdir/W 0"|mdb -kw'in
#         NPRD1 and NPRD2.
#   	- After panic, check VFs state by "hotplug list" in IO domain,both
#         should be "ONLINE", check the logical path from VF, should be seen.
#         Check the IO workload,should be zero.
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
import basic


def tp_float_panic_panic_002():

    basic.info_print_report("FC-IOR functional test06 TP2: panic_panic")

    nprd_a = ctiutils.cti_getvar("NPRD_A")
    nprd_b = ctiutils.cti_getvar("NPRD_B")
    iod = ctiutils.cti_getvar("IOD")
    nprd_a_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    nprd_b_password = ctiutils.cti_getvar("NPRD_B_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    operate_type_1 = 'panic'
    operate_type_2 = 'panic'
    nprd_a_dict = {
        nprd_a: {
            'password': nprd_a_password,
            'operate_type': operate_type_1,
            'operate_count': 1}}
    nprd_b_dict = {
        nprd_b: {
            'password': nprd_b_password,
            'operate_type': operate_type_2,
            'operate_count': 1}}
    nprd_dict = {
        nprd_a: {
            'password': nprd_a_password,
            'operate_type': operate_type_1,
            'operate_count': 1},
        nprd_b: {
            'password': nprd_b_password,
            'operate_type': operate_type_2,
            'operate_count': 1}}
    iods_dict = {iod: iod_password}

    # reboot root domain, check the io domain status
    event = threading.Event()
    root_domain_a_thread = common.operate_domain_thread(
        'Thread-' +
        nprd_a,
        event,
        nprd_a_dict)
    root_domain_a_thread.start()

    root_domain_b_thread = common.operate_domain_thread(
        'Thread-' +
        nprd_b,
        event,
        nprd_b_dict)
    root_domain_b_thread.start()

    root_domain_a_thread.join()
    root_domain_b_thread.join()
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
