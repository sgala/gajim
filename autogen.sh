#!/usr/bin/env bash
  AM_ARGS="--add-missing --gnu --copy"
  CONF_ARGS=""
  if test x`uname -s 2>/dev/null` = 'xDarwin';then
    . /Library/Frameworks/GTK+.framework/Versions/Current/env
    AM_ARGS="${AM_ARGS} --ignore-deps"
    CONF_ARGS="${CONF_ARGS} --disable-idle --without-x"
  fi

  echo "[encoding: UTF-8]" > po/POTFILES.in \
  && ls -1 -U data/gajim.desktop.in.in data/glade/*.glade \
  src/*py src/common/*py src/common/zeroconf/*.py >> \
  po/POTFILES.in || exit 1
  if test -z `which pkg-config 2>/dev/null`;then
    echo "***Error: pkg-config not found***"
	echo "See README.html for build requirements."
	exit 1
  fi

  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && libtoolize --copy --force --automake \
  && autoheader \
  && autoconf  \
  && automake ${AM_ARGS} \
  && ./configure ${CONF_ARGS} $@
