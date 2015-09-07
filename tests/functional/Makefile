#
# Copyright (c) 2015, Oracle and/or its affiliates. All rights reserved.
#

include $(CTI_ROOT)/Makefiles/Makefile.defs
include $(CTI_SUITE)/Targetdirs

CTI_SUBDIRS     = test01 \
                  test02 \
                  test03 \
                  test04 \
                  test05 \
                  float

.PARALLEL: $(CTI_SUBDIRS)

all clean clobber lint install : $(CTI_SUBDIRS)

include $(CTI_ROOT)/Makefiles/Makefile.targ
