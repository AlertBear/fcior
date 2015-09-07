#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

include $(CTI_ROOT)/Makefiles/Makefile.defs
include $(CTI_SUITE)/Targetdirs

CTI_SRCS        = tc_test05.py
CTI_TARGET      = $(CTI_SRCS:%.py=%)
CTI_SRCS2:sh       = ls tp_*.py
CTI_TARGET2     = $(CTI_SRCS2:%.py=%.pyc)

CTI_INSTOBJS    = $(CTI_TARGET:%=$(CTI_PROTO)/$(CTI_EXEC)/%) \
                  $(CTI_TARGET2:%=$(CTI_PROTO)/$(CTI_EXEC)/%)

include $(CTI_ROOT)/Makefiles/Makefile.tests

all : $(CTI_TARGET) $(CTI_TARGET2)

clean : 
		$(RM) $(CTI_MACH64) $(CTI_TARGET) $(CTI_TARGET2)

clobber : clean 
		$(RM) $(CTI_PROTO)/$(CTI_EXEC)

include $(CTI_ROOT)/Makefiles/Makefile.targ
