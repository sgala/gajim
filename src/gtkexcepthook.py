##	gtkexcepthook.py
##
## Copyright (C) 2005-2006 Yann Leboulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
##
## Initially written and submitted by Gustavo J. A. M. Carneiro
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import sys
import os
import traceback
import threading

import gtk
import pango
from common import i18n
import dialogs

from cStringIO import StringIO
from common import helpers

_exception_in_progress = threading.Lock()

def _info(type, value, tb):
	if not _exception_in_progress.acquire(False):
		# Exceptions have piled up, so we use the default exception
		# handler for such exceptions
		_excepthook_save(type, value, tb)
		return

	dialog = dialogs.HigDialog(None, gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE, 
				_('A programming error has been detected'),
				_('It probably is not fatal, but should be reported '
				'to the developers nonetheless.'))
	
	#FIXME: add icon to this button
	RESPONSE_REPORT_BUG = 42
	dialog.add_buttons(gtk.STOCK_CLOSE, gtk.BUTTONS_CLOSE,
		_('_Report Bug'), RESPONSE_REPORT_BUG)
	dialog.set_default_response(RESPONSE_REPORT_BUG)
	report_button = dialog.action_area.get_children()[0] # right to left
	report_button.grab_focus()

	# Details
	textview = gtk.TextView()
	textview.set_editable(False)
	textview.modify_font(pango.FontDescription('Monospace'))
	sw = gtk.ScrolledWindow()
	sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.add(textview)
	frame = gtk.Frame()
	frame.set_shadow_type(gtk.SHADOW_IN)
	frame.add(sw)
	frame.set_border_width(6)
	textbuffer = textview.get_buffer()
	trace = StringIO()
	traceback.print_exception(type, value, tb, None, trace)
	textbuffer.set_text(trace.getvalue())
	textview.set_size_request(
		gtk.gdk.screen_width() / 3,
		gtk.gdk.screen_height() / 4)
	expander = gtk.Expander(_('Details'))
	expander.add(frame)
	dialog.vbox.add(expander)

	dialog.set_resizable(True)
	# on expand the details the dialog remains centered on screen
	dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)

	dialog.show_all()

	close_clicked = False
	while not close_clicked:
		resp = dialog.run()
		if resp == RESPONSE_REPORT_BUG:
			url = 'http://trac.gajim.org/wiki/WikiStart#howto_report_ticket'
			helpers.launch_browser_mailer('url', url)
		else:
			close_clicked = True
	
	dialog.destroy()

	_exception_in_progress.release()
	
# gdb/kdm etc if we use startx this is not True
if os.name == 'nt' or not sys.stderr.isatty():
	#FIXME: maybe always show dialog?
	_excepthook_save = sys.excepthook
	sys.excepthook = _info

# this is just to assist testing (python gtkexcepthook.py)
if __name__ == '__main__':
	_excepthook_save = sys.excepthook
	sys.excepthook = _info
	print x # this always tracebacks
