#!/usr/bin/python2.7
#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

##########################################################################
#
#__stc_assertion_start
#
# ID:
#       mix/mix_nicib/tp_mix_nic_ib_001
#
# DESCRIPTION:
#       Reboot root domain, IO domain with two IB VFs configured with IPMP
#       and two NIC VFs configured with IPMP is alive during the reboot period.
#       Besides, the two IB VFs where running io workload are still ONLINE and
#       IO workload continues after reboot. Meanwhile, the NIC vfs are still
#       ONLINE after reboot.
#
# STRATEGY:
#       - Create two Ib VFs separately from two PFs in NPRD1 and NPRD2, and
#         create two NIC VFs separately from two PFs in NPRD1 and NPRD2.
#       - Allocated two IB VFs to the IO domain, create IPoIB interface on the
#         VFs, run io workload on these two VFs which are IPMP configured.
#       - Allocated two NIC VFs configured with IPMP to the IO domain.
#       - Reboot NPRD1 by "reboot".
#       - During reboot NPRD1, IO domain should be alive.
#       - During reboot, check IB VFs from NPRD1 by "hotplug list" in IO domain,
#         should be "OFFLINE". check the io workload, still continues on the
#         alternative path. Check VF created from NPRD2 by "hotplug list" in IO
#         domain, should be "ONLINE". Check ipmp state with "ipmpstat -g" and
#         "ipmpstat -i", the state should be degraded/failed.
#       - During reboot, check NIC VF from NPRD1 by "hotplug list" in IO domain,
#         should be "MAINTENANCE-SUSPENDED". Ping the IPMP interface, should
#         successfully. Check NIC VF created from NPRD2 by "hotplug list" in IO
#         domain, should be "ONLINE". Check ipmp state with "ipmpstat -g" and
#         "ipmpstat -i", the state should be degraded/failed.
#       - After reboot, check VFs state by "hotplug list" in IO domain, all
#         should be "ONLINE". Check io workload on IB VFs, should continue as
#         nothing happened. Ping IPMP interface, should successfully. Check ipmp
#         state with "ipmpstat -g" and "ipmpstat -i", the stat should be normal.
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
