#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       stress/multidom/tp_multidom_002
#
# DESCRIPTION:
#       Panic root domain, all IO domains with 2 VFs created from the root domain is
#       alive during the reboot period and the VFs is still ONLINE after reboot
#
# STRATEGY:
#       - Create as much IO domains as the maxvfs number of a FC port
#   	- Create 2*maxvfs from two root domain, half VFs are from NPRD1, half are
#         from NPRD2.
#       - Allocated one VF from NPRD1 and one VF from NPRD2 to the IO domain iod0.
#       - Allocated the other pairs VFs to the other io domains seperately as iod0
#       - Run vdbench in 3 of the domains.
#   	- Reboot root domain by 'echo "rootdir/W 0"|mdb -kw' in root domain.
#   	- After reboot, all IO domains should alive. Check VFs state by "hotplug
#         list" in IO domain, all should be "ONLINE", check the IO workload in the
#         3 io domains where run vdbench, io are still continute as nothing happened.
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


def tp_multidom_002():

    basic.info_print_report("FC-IOR stress multidom TP2: panic")

    nprd = ctiutils.cti_getvar("NPRD_A")
    iod = ctiutils.cti_getvar("IOD")
    iods_list = [iod]
    for i in range(1, 15):
        check_iod = ctiutils.cti_getvar("IOD_{0}".format(i))
        try:
            common.check_domain_exists(check_iod)
        except Exception as e:
            pass
        else:
            iods_list.append(check_iod)
    nprd_password = ctiutils.cti_getvar("NPRD_A_PASSWORD")
    iod_password = ctiutils.cti_getvar("IOD_PASSWORD")

    operate_type = 'panic'
    nprd_dict = {
        nprd: {
            'password': nprd_password,
            'operate_type': operate_type,
            'operate_count': 1}}

    iods_dict = {}
    for iod in iods_list:
        iods_dict_item = {iod: iod_password}
        iods_dict.update(iods_dict_item)

    # reboot root domain, check the io domain status
    event = threading.Event()
    root_domain_thread = common.operate_domain_thread(
        'Thread-' +
        nprd,
        event,
        nprd_dict)
    root_domain_thread.start()
    root_domain_thread.join()
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
