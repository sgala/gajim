SUBDIRS = src data po

ACLOCAL_AMFLAGS = -I m4

if BUILD_REMOTE_CONTROL
OPTIONAL_BIN = scripts/gajim-remote
else
OPTIONAL_BIN =
endif

bin_SCRIPTS = scripts/gajim $(OPTIONAL_BIN)


docfilesdir = $(docdir)
docfiles_DATA = README \
				README.html \
				ChangeLog \
				COPYING \
				THANKS \
				THANKS.artists \
				AUTHORS 

EXTRA_DIST = \
	$(docfiles_DATA) \
	autogen.sh			\
	intltool-extract.in \
	intltool-merge.in 	\
	intltool-update.in	\
	gajim.nsi \
	setup_win32.py \
	scripts/gajim.in	\
	scripts/gajim-remote.in
	
DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update		\
	scripts/gajim		\
	scripts/gajim-remote

MAINTAINERCLEANFILES = \
	configure \
	Makefile.in \
	intltool-extract.in \
	intltool-update.in \
	intltool-merge.in \
	ltmain.sh \
	missing \
	mkinstalldirs \
	install-sh \
	compile \
	depcomp \
	config.guess \
	config.log \
	config.sub \
	config.status \
	aclocal.m4 \
	libtool \
	po/POTFILES.in \
	src/trayicon_la-eggtrayicon.loT \
	m4/intltool.m4

MAINTAINERCLEANDIRS = \
	autom4te.cache \
	build \
	dist
