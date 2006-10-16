SUBDIRS = common

CLEANFILES = \
	trayicon.c
INCLUDES = \
	$(PYTHON_INCLUDES) 

if BUILD_GTKSPELL
gtkspelllib_LTLIBRARIES = gtkspell.la
gtkspelllibdir = $(libdir)/gajim

gtkspell_la_LIBADD = \
	$(GTKSPELL_LIBS) $(PYGTK_LIBS) 

gtkspell_la_SOURCES = \
	gtkspellmodule.c

gtkspell_la_LDFLAGS = \
	-module -avoid-version 

gtkspell_la_CFLAGS = $(GTKSPELL_CFLAGS) $(PYGTK_CFLAGS)
endif
if BUILD_TRAYICON
trayiconlib_LTLIBRARIES = trayicon.la
trayiconlibdir = $(libdir)/gajim
trayicon_la_LIBADD = $(PYGTK_LIBS)
trayicon_la_SOURCES = \
					  eggtrayicon.c \
					  trayiconmodule.c

nodist_trayicon_la_SOURCES = \
					trayicon.c

trayicon_la_LDFLAGS = \
	-module -avoid-version 
trayicon_la_CFLAGS = $(PYGTK_CFLAGS)

trayicon.c: 
	    pygtk-codegen-2.0 --prefix trayicon \
		    --register $(PYGTK_DEFS)/gdk-types.defs \
		    --register $(PYGTK_DEFS)/gtk-types.defs \
		    --override $(srcdir)/trayicon.override \
		    $(srcdir)/trayicon.defs > $@
endif
gajimsrcdir = $(pkgdatadir)/src
gajimsrc_DATA = $(srcdir)/*.py 

gajimsrc1dir = $(pkgdatadir)/src/common
gajimsrc1_DATA = \
				$(srcdir)/common/*.py 

gajimsrc2dir = $(pkgdatadir)/src/common/xmpp
gajimsrc2_DATA = \
				$(srcdir)/common/xmpp/*.py 

gajimsrc3dir = $(pkgdatadir)/src/common/zeroconf
gajimsrc3_DATA = \
				$(srcdir)/common/zeroconf/*.py 

DISTCLEANFILES = 

EXTRA_DIST = $(gajimsrc_DATA) \
			$(gajimsrc1_DATA) \
			$(gajimsrc2_DATA) \
			$(gajimsrc3_DATA) \
			gtkspellmodule.c \
			eggtrayicon.c \
			trayiconmodule.c \
			eggtrayicon.h \
			trayicon.defs \
			trayicon.override 

MAINTAINERCLEANFILES = Makefile.in