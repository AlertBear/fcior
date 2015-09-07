#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

include $(CTI_ROOT)/Makefiles/Makefile.defs
include $(CTI_SUITE)/Targetdirs

CTI_SUBDIRS   = functional \
	            stress


.PARALLEL: $(CTI_SUBDIRS)

all clean clobber lint install : $(CTI_SUBDIRS)

include $(CTI_ROOT)/Makefiles/Makefile.targ
