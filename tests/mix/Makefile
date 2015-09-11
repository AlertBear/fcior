#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

include $(CTI_ROOT)/Makefiles/Makefile.defs
include $(CTI_SUITE)/Targetdirs

SUBDIRS     = mix_nicfc \
	          mix_nicib \
	          mix_nicfcib


.PARALLEL: $(SUBDIRS)

all clean clobber lint install : $(SUBDIRS)

include $(CTI_ROOT)/Makefiles/Makefile.targ
