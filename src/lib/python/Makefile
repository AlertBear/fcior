#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

include $(CTI_ROOT)/Makefiles/Makefile.defs

CTI_SRCS:sh     = ls *.py
CTI_TARGET      = $(CTI_SRCS:%.py=$(CTI_SUITE_LIB)/%.pyc)

all install : $(CTI_SUITE_LIB) $(CTI_TARGET)

clean : 
		$(RM) $(CTI_SUITE_LIB) $(CTI_MACH64) $(CTI_TARGET)

clobber : clean 
		$(RM) $(CTI_PROTO)/lib

include $(CTI_ROOT)/Makefiles/Makefile.targ
