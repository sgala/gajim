##	message_textview.py
##
## Contributors for this file:
## - Yann Leboulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Leboulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Leboulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <kourem@gmail.com>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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

import gtk
import gobject

class MessageTextView(gtk.TextView):
	'''Class for the message textview (where user writes new messages)
	for chat/groupchat windows'''
	__gsignals__ = dict(
		mykeypress = (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION,
				None, # return value
				(int, gtk.gdk.ModifierType ) # arguments
			)
		)
		
	def __init__(self):
		gtk.TextView.__init__(self)
		
		# set properties
		self.set_border_width(1)
		self.set_accepts_tab(True)
		self.set_editable(True)
		self.set_cursor_visible(True)
		self.set_wrap_mode(gtk.WRAP_WORD_CHAR)
		self.set_left_margin(2)
		self.set_right_margin(2)
		self.set_pixels_above_lines(2)
		self.set_pixels_below_lines(2)

		self.lang = None # Lang used for spell checking

	def destroy(self):
		import gc
		gobject.idle_add(lambda:gc.collect())

	def clear(self, widget = None):
		'''clear text in the textview'''
		buffer = self.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)


# We register depending on keysym and modifier some bindings
# but we also pass those as param so we can construct fake Event
# Here we register bindings for those combinations that there is NO DEFAULT
# action to be done by gtk TextView. In such case we should not add a binding
# as the default action comes first and our bindings is useless. In that case
# we catch and do stuff before default action in normal key_press_event
# and we also return True there to stop the default action from running

# CTRL + SHIFT + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.ISO_Left_Tab,
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.ISO_Left_Tab,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Tab, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Tab,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)
	
# TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Tab, 
	0, 'mykeypress', int, gtk.keysyms.Tab,	gtk.gdk.ModifierType, 0)

# CTRL + UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Up, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Up,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Down, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Down,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# ENTER
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return, 
	0, 'mykeypress', int, gtk.keysyms.Return,
	gtk.gdk.ModifierType, 0)

# Ctrl + Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Return,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter, 
	0, 'mykeypress', int, gtk.keysyms.KP_Enter,
	gtk.gdk.ModifierType, 0)

# Ctrl + Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.KP_Enter,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)
