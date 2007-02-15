##	chat_control.py
##
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2006 Travis Shirk <travis@pobox.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import os
import time
import gtk
import pango
import gobject
import gtkgui_helpers
import message_control
import dialogs
import history_window
import notify

from common import gajim
from common import helpers
from message_control import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView
from common.contacts import GC_Contact
from common.logger import Constants
constants = Constants()
from common.rst_xhtml_generator import create_xhtml
from common.xmpp.protocol import NS_XHTML

try:
	import gtkspell
	HAS_GTK_SPELL = True
except:
	HAS_GTK_SPELL = False


# the next script, executed in the "po" directory,
# generates the following list.
##!/bin/sh
#LANG=$(for i in *.po; do  j=${i/.po/}; echo -n "_('"$j"')":" '"$j"', " ; done)
#echo "{_('en'):'en'",$LANG"}"
langs = {_('English'): 'en', _('Belarusian'): 'be', _('Bulgarian'): 'bg', _('Briton'): 'br', _('Czech'): 'cs', _('German'): 'de', _('Greek'): 'el', _('British'): 'en_GB', _('Esperanto'): 'eo', _('Spanish'): 'es', _('Basc'): 'eu', _('French'): 'fr', _('Croatian'): 'hr', _('Italian'): 'it', _('Norwegian (b)'): 'nb', _('Dutch'): 'nl', _('Norwegian'): 'no', _('Polish'): 'pl', _('Portuguese'): 'pt', _('Brazilian Portuguese'): 'pt_BR', _('Russian'): 'ru', _('Serbian'): 'sr', _('Slovak'): 'sk', _('Swedish'): 'sv', _('Chinese (Ch)'): 'zh_CN'}


################################################################################
class ChatControlBase(MessageControl):
	'''A base class containing a banner, ConversationTextview, MessageTextView
	'''
	def get_font_attrs(self):
		''' get pango font  attributes for banner from theme settings '''
		theme = gajim.config.get('roster_theme')
		bannerfont = gajim.config.get_per('themes', theme, 'bannerfont')
		bannerfontattrs = gajim.config.get_per('themes', theme, 'bannerfontattrs')

		if bannerfont:
			font = pango.FontDescription(bannerfont)
		else:
			font = pango.FontDescription('Normal')
		if bannerfontattrs:
			# B attribute is set by default
			if 'B' in bannerfontattrs:
				font.set_weight(pango.WEIGHT_HEAVY)
			if 'I' in bannerfontattrs:
				font.set_style(pango.STYLE_ITALIC)

		font_attrs = 'font_desc="%s"' % font.to_string()

		# in case there is no font specified we use x-large font size
		if font.get_size() == 0:
			font_attrs = '%s size="x-large"' % font_attrs
		font.set_weight(pango.WEIGHT_NORMAL)
		font_attrs_small = 'font_desc="%s" size="small"' % font.to_string()
		return (font_attrs, font_attrs_small)

	def get_nb_unread(self):
		jid = self.contact.jid
		if self.resource:
			jid += '/' + self.resource
		type_ = self.type_id
		return len(gajim.events.get_events(self.account, jid, ['printed_' + type_,
			type_]))

	def draw_banner(self):
		'''Draw the fat line at the top of the window that 
		houses the icon, jid, ... 
		'''
		self.draw_banner_text()
		self._update_banner_state_image()
		# Derived types MAY implement this

	def draw_banner_text(self):
		pass # Derived types SHOULD implement this

	def update_ui(self):
		self.draw_banner()
		# Derived types SHOULD implement this

	def repaint_themed_widgets(self):
		self._paint_banner()
		self.draw_banner()
		# Derived classes MAY implement this

	def _update_banner_state_image(self):
		pass # Derived types MAY implement this

	def handle_message_textview_mykey_press(self, widget, event_keyval,
	event_keymod):
		pass # Derived should implement this rather than connecting to the event itself.

	def __init__(self, type_id, parent_win, widget_name, contact, acct, 
	resource = None):
		MessageControl.__init__(self, type_id, parent_win, widget_name,
			contact, acct, resource = resource);
		# when/if we do XHTML we will put formatting buttons back
		widget = self.xml.get_widget('emoticons_button')
		id = widget.connect('clicked', self.on_emoticons_button_clicked)
		self.handlers[id] = widget

		id = self.widget.connect('key_press_event', self._on_keypress_event)
		self.handlers[id] = self.widget

		widget = self.xml.get_widget('banner_eventbox')
		id = widget.connect('button-press-event',
			self._on_banner_eventbox_button_press_event)
		self.handlers[id] = widget

		# Create textviews and connect signals
		self.conv_textview = ConversationTextview(self.account)

		self.conv_scrolledwindow = self.xml.get_widget(
			'conversation_scrolledwindow')
		self.conv_scrolledwindow.add(self.conv_textview.tv)
		widget = self.conv_scrolledwindow.get_vadjustment()
		id = widget.connect('value-changed',
			self.on_conversation_vadjustment_value_changed)
		self.handlers[id] = widget
		# add MessageTextView to UI and connect signals
		self.msg_scrolledwindow = self.xml.get_widget('message_scrolledwindow')
		self.msg_textview = MessageTextView()
		id = self.msg_textview.connect('mykeypress',
			self._on_message_textview_mykeypress_event)
		self.handlers[id] = self.msg_textview
		self.msg_scrolledwindow.add(self.msg_textview)
		id = self.msg_textview.connect('key_press_event',
			self._on_message_textview_key_press_event)
		self.handlers[id] = self.msg_textview
		id = self.msg_textview.connect('size-request', self.size_request)
		self.handlers[id] = self.msg_textview
		id = self.msg_textview.connect('populate_popup',
			self.on_msg_textview_populate_popup)
		self.handlers[id] = self.msg_textview
	
		self.update_font()

		# Hook up send button
		widget = self.xml.get_widget('send_button')
		id = widget.connect('clicked', self._on_send_button_clicked)
		self.handlers[id] = widget

		# the following vars are used to keep history of user's messages
		self.sent_history = []
		self.sent_history_pos = 0
		self.orig_msg = None

		# Emoticons menu
		# set image no matter if user wants at this time emoticons or not
		# (so toggle works ok)
		img = self.xml.get_widget('emoticons_button_image')
		img.set_from_file(os.path.join(gajim.DATA_DIR, 'emoticons', 'static',
			'smile.png'))
		self.toggle_emoticons()

		# Attach speller
		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			try:
				spell = gtkspell.Spell(self.msg_textview)
				# loop removing non-existant dictionaries
				# iterating on a copy
				for lang in dict(langs):
					try: 
						spell.set_language(langs[lang])
					except:
						del langs[lang]
				# now set the one the user selected
				per_type = 'contacts'
				if self.type_id == message_control.TYPE_GC:
					per_type = 'rooms'
				lang = gajim.config.get_per(per_type, self.contact.jid,
					'speller_language')
				if not lang:
					# use the default one
					lang = gajim.config.get('speller_language')
				if lang:
					self.msg_textview.lang = lang
					spell.set_language(lang)
			except (gobject.GError, RuntimeError), msg:
				dialogs.ErrorDialog(unicode(msg), _('If that is not your language '
					'for which you want to highlight misspelled words, then please '
					'set your $LANG as appropriate. Eg. for French do export '
					'LANG=fr_FR or export LANG=fr_FR.UTF-8 in ~/.bash_profile or to '
					'make it global in /etc/profile.\n\nHighlighting misspelled '
					'words feature will not be used'))
				gajim.config.set('use_speller', False)

		self.style_event_id = 0
		self.conv_textview.tv.show()
		self._paint_banner()

		# For JEP-0172
		self.user_nick = None

	def on_msg_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend an option to switch languages'''
		def _on_select_dictionary(widget, lang):
			per_type = 'contacts'
			if self.type_id == message_control.TYPE_GC:
				per_type = 'rooms'
			if not gajim.config.get_per(per_type, self.contact.jid):
				gajim.config.add_per(per_type, self.contact.jid)
			gajim.config.set_per(per_type, self.contact.jid, 'speller_language',
				lang)
			spell = gtkspell.get_from_text_view(self.msg_textview)
			self.msg_textview.lang = lang
			spell.set_language(lang)
			widget.set_active(True)

		item = gtk.SeparatorMenuItem()
		menu.prepend(item)

		item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
		menu.prepend(item)
		id = item.connect('activate', self.msg_textview.clear)
		self.handlers[id] = item

		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			item = gtk.MenuItem(_('Spelling language'))
			menu.prepend(item)
			submenu = gtk.Menu()
			item.set_submenu(submenu)
			for lang in sorted(langs):
				item = gtk.CheckMenuItem(lang)
				if langs[lang] == self.msg_textview.lang:
					item.set_active(True)
				submenu.append(item)
				id = item.connect('activate', _on_select_dictionary, langs[lang])
				self.handlers[id] = item

		menu.show_all()

	# moved from ChatControl 
	def _on_banner_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			self.parent_win.popup_menu(event)

	def _on_send_button_clicked(self, widget):
		'''When send button is pressed: send the current message'''
		if gajim.connections[self.account].connected < 2: # we are not connected
			dialogs.ErrorDialog(_('A connection is not available'),
				_('Your message can not be sent until you are connected.'))
			return
		message_buffer = self.msg_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0).decode('utf-8')

		# send the message
		self.send_message(message)

	def _paint_banner(self):
		'''Repaint banner with theme color'''
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		# the backgrounds are colored by using an eventbox by
		# setting the bg color of the eventbox and the fg of the name_label
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		banner_name_label = self.xml.get_widget('banner_name_label')
		self.disconnect_style_event(banner_name_label)
		if bgcolor:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, 
				gtk.gdk.color_parse(bgcolor))
			default_bg = False
		else:
			default_bg = True
		if textcolor:
			banner_name_label.modify_fg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(textcolor))
			default_fg = False
		else:
			default_fg = True
		if default_bg or default_fg:
			self._on_style_set_event(banner_name_label, None, default_fg,
				default_bg)
	
	def disconnect_style_event(self, widget):
		if self.style_event_id:
			widget.disconnect(self.style_event_id)
			del self.handlers[self.style_event_id]
			self.style_event_id = 0	
	
	def connect_style_event(self, widget, set_fg = False, set_bg = False):
		self.disconnect_style_event(widget)
		self.style_event_id = widget.connect('style-set',
			self._on_style_set_event, set_fg, set_bg)
		self.handlers[self.style_event_id] = widget
	
	def _on_style_set_event(self, widget, style, *opts):
		'''set style of widget from style class *.Frame.Eventbox 
			opts[0] == True -> set fg color
			opts[1] == True -> set bg color'''
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		self.disconnect_style_event(widget)
		if opts[1]:
			bg_color = widget.style.bg[gtk.STATE_SELECTED]
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, bg_color)
		if opts[0]:
			fg_color = widget.style.fg[gtk.STATE_SELECTED]
			widget.modify_fg(gtk.STATE_NORMAL, fg_color)
		self.connect_style_event(widget, opts[0], opts[1])
	
	def _on_keypress_event(self, widget, event):
		if event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + l|L: clear conv_textview
			if event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L:
				self.conv_textview.clear()
				return True
			# CTRL + v: Paste into msg_textview
			elif event.keyval == gtk.keysyms.v:
				if not self.msg_textview.is_focus():
					self.msg_textview.grab_focus()
				# Paste into the msg textview
				self.msg_textview.emit('key_press_event', event)
			# CTRL + u: emacs style clear line
			elif event.keyval == gtk.keysyms.u:
				self.clear(self.msg_textview) # clear message textview too
			elif event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.parent_win.move_to_next_unread_tab(False)
				return True
			elif event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.parent_win.move_to_next_unread_tab(True)
				return True
			# CTRL + PAGE_[UP|DOWN]: send to parent notebook
			elif event.keyval == gtk.keysyms.Page_Down or \
					event.keyval == gtk.keysyms.Page_Up:
				self.parent_win.notebook.emit('key_press_event', event)
				return True
		elif event.keyval == gtk.keysyms.m and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + m opens emoticons menu
			if gajim.config.get('emoticons_theme'):
				msg_tv = self.msg_textview
				def set_emoticons_menu_position(w, msg_tv = self.msg_textview):
					window = msg_tv.get_window(gtk.TEXT_WINDOW_WIDGET)
					# get the window position
					origin = window.get_origin()
					size = window.get_size()
					buf = msg_tv.get_buffer()
					# get the cursor position
					cursor = msg_tv.get_iter_location(buf.get_iter_at_mark(
						buf.get_insert()))
					cursor =  msg_tv.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT,
						cursor.x, cursor.y)
					x = origin[0] + cursor[0]
					y = origin[1] + size[1]
					menu_width, menu_height = \
						gajim.interface.emoticons_menu.size_request()
					#FIXME: get_line_count is not so good
					#get the iter of cursor, then tv.get_line_yrange
					# so we know in which y we are typing (not how many lines we have
					# then go show just above the current cursor line for up
					# or just below the current cursor line for down
					#TEST with having 3 lines and writing in the 2nd
					if y + menu_height > gtk.gdk.screen_height():
						# move menu just above cursor
						y -= menu_height +\
							(msg_tv.allocation.height / buf.get_line_count())
					#else: # move menu just below cursor
					#	y -= (msg_tv.allocation.height / buf.get_line_count())
					return (x, y, True) # push_in True
				gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
				gajim.interface.emoticons_menu.popup(None, None,
					set_emoticons_menu_position, 1, 0)
		return False

	def _on_message_textview_key_press_event(self, widget, event):
		if self.widget_name == 'muc_child_vbox':
			if event.keyval not in (gtk.keysyms.ISO_Left_Tab, gtk.keysyms.Tab):
				self.last_key_tabs = False
		if event.state & gtk.gdk.SHIFT_MASK:
			# CTRL + SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK and \
					event.keyval == gtk.keysyms.ISO_Left_Tab:
				self.parent_win.move_to_next_unread_tab(False)
				return True
			# SHIFT + PAGE_[UP|DOWN]: send to conv_textview
			elif event.keyval == gtk.keysyms.Page_Down or \
					event.keyval == gtk.keysyms.Page_Up:
				self.conv_textview.tv.emit('key_press_event', event)
				return True
		elif event.state & gtk.gdk.CONTROL_MASK:
			if event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.parent_win.move_to_next_unread_tab(True)
				return True
			# CTRL + PAGE_[UP|DOWN]: send to parent notebook
			elif event.keyval == gtk.keysyms.Page_Down or \
					event.keyval == gtk.keysyms.Page_Up:
				self.parent_win.notebook.emit('key_press_event', event)
				return True
			# we pressed a control key or ctrl+sth: we don't block
			# the event in order to let ctrl+c (copy text) and
			# others do their default work
			self.conv_textview.tv.emit('key_press_event', event)
		return False

	def _on_message_textview_mykeypress_event(self, widget, event_keyval,
		event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''

		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_tab(). for this singal see message_textview.py
		message_textview = widget
		message_buffer = message_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode(
			'utf-8')

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		if event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+UP
				self.sent_messages_scroll('up', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+Down
				self.sent_messages_scroll('down', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			# NOTE: SHIFT + ENTER is not needed to be emulated as it is not
			# binding at all (textview's default action is newline)

			if gajim.config.get('send_on_ctrl_enter'):
				# here, we emulate GTK default action on ENTER (add new line)
				# normally I would add in keypress but it gets way to complex
				# to get instant result on changing this advanced setting
				if event.state == 0: # no ctrl, no shift just ENTER add newline
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				elif event.state & gtk.gdk.CONTROL_MASK: # CTRL + ENTER
					send_message = True
			else: # send on Enter, do newline on Ctrl Enter
				if event.state & gtk.gdk.CONTROL_MASK: # Ctrl + ENTER
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				else: # ENTER
					send_message = True
				
			if gajim.connections[self.account].connected < 2: # we are not connected
				dialogs.ErrorDialog(_('A connection is not available'),
					_('Your message can not be sent until you are connected.'))
				send_message = False

			if send_message:
				self.send_message(message) # send the message
		else:
			# Give the control itself a chance to process
			self.handle_message_textview_mykey_press(widget, event_keyval,
				event_keymod)

	def _process_command(self, message):
		if not message or message[0] != '/':
			return False

		message = message[1:]
		message_array = message.split(' ', 1)
		command = message_array.pop(0).lower()
		if message_array == ['']:
			message_array = []

		if command == 'clear' and not len(message_array):
			self.conv_textview.clear() # clear conversation
			self.clear(self.msg_textview) # clear message textview too
			return True
		elif message == 'compact' and not len(message_array):
			self.chat_buttons_set_visible(not self.hide_chat_buttons_current)
			self.clear(self.msg_textview)
			return True
		return False

	def send_message(self, message, keyID = '', type = 'chat', chatstate = None,
	msg_id = None, composing_jep = None, resource = None):
		'''Send the given message to the active tab. Doesn't return None if error
		'''
		if not message or message == '\n':
			return 1


		if not self._process_command(message):
			ret = MessageControl.send_message(self, message, keyID, type = type,
				chatstate = chatstate, msg_id = msg_id,
				composing_jep = composing_jep, resource = resource,
				user_nick = self.user_nick)
			if ret:
				return ret
			# Record message history
			self.save_sent_message(message)

			# Be sure to send user nickname only once according to JEP-0172
			self.user_nick = None

		# Clear msg input
		message_buffer = self.msg_textview.get_buffer()
		message_buffer.set_text('') # clear message buffer (and tv of course)

	def save_sent_message(self, message):
		#save the message, so user can scroll though the list with key up/down
		size = len(self.sent_history)
		#we don't want size of the buffer to grow indefinately
		max_size = gajim.config.get('key_up_lines')
		if size >= max_size:
			for i in xrange(0, size - 1): 
				self.sent_history[i] = self.sent_history[i + 1]
			self.sent_history[max_size - 1] = message
		else:
			self.sent_history.append(message)
			self.sent_history_pos = size + 1
		self.orig_msg = None

	def print_conversation_line(self, text, kind, name, tim,
		other_tags_for_name = [], other_tags_for_time = [], 
		other_tags_for_text = [], count_as_new = True,
		subject = None, old_kind = None, xhtml = None):
		'''prints 'chat' type messages'''
		jid = self.contact.jid
		full_jid = self.get_full_jid()
		textview = self.conv_textview
		end = False
		if textview.at_the_end() or kind == 'outgoing':
			end = True
		textview.print_conversation_line(text, jid, kind, name, tim,
			other_tags_for_name, other_tags_for_time, other_tags_for_text,
			subject, old_kind, xhtml)

		if not count_as_new:
			return
		if kind == 'incoming':
			gajim.last_message_time[self.account][full_jid] = time.time()
		if (not self.parent_win.get_active_jid() or \
		full_jid != self.parent_win.get_active_jid() or \
		not self.parent_win.is_active() or not end) and \
		kind in ('incoming', 'incoming_queue'):
			gc_message = False
			if self.type_id  == message_control.TYPE_GC:
				gc_message = True
			if not gc_message or \
			(gc_message and (other_tags_for_text == ['marked'] or \
			gajim.config.get('notify_on_all_muc_messages'))):
			# we want to have save this message in events list
			# other_tags_for_text == ['marked'] --> highlighted gc message
				type_ = 'printed_' + self.type_id
				if gc_message:
					type_ = 'printed_gc_msg'
				show_in_roster = notify.get_show_in_roster('message_received',
					self.account, self.contact)
				show_in_systray = notify.get_show_in_systray('message_received',
					self.account, self.contact)
				event = gajim.events.create_event(type_, None,
					show_in_roster = show_in_roster,
					show_in_systray = show_in_systray)
				gajim.events.add_event(self.account, full_jid, event)
				# We need to redraw contact if we show in roster
				if show_in_roster:
					gajim.interface.roster.draw_contact(self.contact.jid,
						self.account)
			self.parent_win.redraw_tab(self)
			ctrl = gajim.interface.msg_win_mgr.get_control(full_jid, self.account)
			if not self.parent_win.is_active():
				self.parent_win.show_title(True, ctrl) # Enabled Urgent hint
			else:
				self.parent_win.show_title(False, ctrl) # Disabled Urgent hint

	def toggle_emoticons(self):
		'''hide show emoticons_button and make sure emoticons_menu is always there
		when needed'''
		emoticons_button = self.xml.get_widget('emoticons_button')
		if gajim.config.get('emoticons_theme'):
			emoticons_button.show()
			emoticons_button.set_no_show_all(False)
		else:
			emoticons_button.hide()
			emoticons_button.set_no_show_all(True)

	def append_emoticon(self, str_):
		buffer = self.msg_textview.get_buffer()
		if buffer.get_char_count():
			buffer.insert_at_cursor(' %s ' % str_)
		else: # we are the beginning of buffer
			buffer.insert_at_cursor('%s ' % str_)
		self.msg_textview.grab_focus()

	def on_emoticons_button_clicked(self, widget):
		'''popup emoticons menu'''
		gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
		gajim.interface.popup_emoticons_under_button(widget, self.parent_win)

	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		menu = self.prepare_context_menu()
		menu.show_all()
		gtkgui_helpers.popup_emoticons_under_button(menu, widget,
			self.parent_win)

	def update_font(self):
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.conv_textview.tv.modify_font(font)
		self.msg_textview.modify_font(font)

	def update_tags(self):
		self.conv_textview.update_tags()

	def clear(self, tv):
		buffer = tv.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def _on_history_menuitem_activate(self, widget = None, jid = None):
		'''When history menuitem is pressed: call history window'''
		if not jid:
			jid = self.contact.jid

		if gajim.interface.instances['logs'].has_key(jid):
			gajim.interface.instances['logs'][jid].window.present()
		else:
			gajim.interface.instances['logs'][jid] = \
				history_window.HistoryWindow(jid, self.account)

	def _on_compact_view_menuitem_activate(self, widget):
		isactive = widget.get_active()
		self.chat_buttons_set_visible(isactive)

	def set_control_active(self, state):
		if state:
			jid = self.contact.jid
			if self.conv_textview.at_the_end():
				# we are at the end
				type_ = 'printed_' + self.type_id
				if self.type_id == message_control.TYPE_GC:
					type_ = 'printed_gc_msg'
				if not gajim.events.remove_events(self.account, self.get_full_jid(),
				types = [type_]):
					# There were events to remove
					self.redraw_after_event_removed(jid)
			self.msg_textview.grab_focus()
			# Note, we send None chatstate to preserve current
			self.parent_win.redraw_tab(self)

	def bring_scroll_to_end(self, textview, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			gobject.idle_add(self.scroll_to_end_iter, textview)

	def scroll_to_end_iter(self, textview):
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		textview.scroll_to_iter(end_iter, 0, False, 1, 1)
		return False

	def size_request(self, msg_textview , requisition):
		''' When message_textview changes its size. If the new height
		will enlarge the window, enable the scrollbar automatic policy
		Also enable scrollbar automatic policy for horizontal scrollbar
		if message we have in message_textview is too big'''
		if msg_textview.window is None:
			return

		min_height = self.conv_scrolledwindow.get_property('height-request')
		conversation_height = self.conv_textview.tv.window.get_size()[1]
		message_height = msg_textview.window.get_size()[1]
		message_width = msg_textview.window.get_size()[0]
		# new tab is not exposed yet
		if conversation_height < 2:
			return

		if conversation_height < min_height:
			min_height = conversation_height

		# we don't want to always resize in height the message_textview
		# so we have minimum on conversation_textview's scrolled window
		# but we also want to avoid window resizing so if we reach that 
		# minimum for conversation_textview and maximum for message_textview
		# we set to automatic the scrollbar policy
		diff_y =  message_height - requisition.height
		if diff_y != 0:
			if conversation_height + diff_y < min_height:
				if message_height + conversation_height - min_height > min_height:
					policy = self.msg_scrolledwindow.get_property(
						'vscrollbar-policy')
					# scroll only when scrollbar appear
					if policy != gtk.POLICY_AUTOMATIC:
						self.msg_scrolledwindow.set_property('vscrollbar-policy', 
							gtk.POLICY_AUTOMATIC)
						self.msg_scrolledwindow.set_property('height-request', 
							message_height + conversation_height - min_height)
						self.bring_scroll_to_end(msg_textview)
			else:
				self.msg_scrolledwindow.set_property('vscrollbar-policy', 
					gtk.POLICY_NEVER)
				self.msg_scrolledwindow.set_property('height-request', -1)

		self.conv_textview.bring_scroll_to_end(diff_y - 18)
		
		# enable scrollbar automatic policy for horizontal scrollbar
		# if message we have in message_textview is too big
		if requisition.width > message_width:
			self.msg_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_AUTOMATIC)
		else:
			self.msg_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_NEVER)

		return True

	def on_conversation_vadjustment_value_changed(self, widget):
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		type_ = self.type_id
		if type_ == message_control.TYPE_GC:
			type_ = 'gc_msg'
		if not len(gajim.events.get_events(self.account, jid, ['printed_' + type_,
		type_])):
			return
		if self.conv_textview.at_the_end() and \
				self.parent_win.get_active_control() == self and \
				self.parent_win.window.is_active():
			# we are at the end
			type_ = self.type_id
			if type_ == message_control.TYPE_GC:
				type_ = 'gc_msg'
			if not gajim.events.remove_events(self.account, self.get_full_jid(),
			types = ['printed_' + type_, type_]):
				# There were events to remove
				self.redraw_after_event_removed(jid)

	def redraw_after_event_removed(self, jid):
		''' We just removed a 'printed_*' event, redraw contact in roster or 
		gc_roster and titles in	roster and msg_win '''
		self.parent_win.redraw_tab(self)
		self.parent_win.show_title()
		# TODO : get the contact and check notify.get_show_in_roster()
		if self.type_id == message_control.TYPE_PM:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			groupchat_control = gajim.interface.msg_win_mgr.get_control(
				room_jid, self.account)
			groupchat_control.draw_contact(nick)
			mw = gajim.interface.msg_win_mgr.get_window(room_jid, self.account)
			mw.redraw_tab(groupchat_control)
		else:
			gajim.interface.roster.draw_contact(jid, self.account)
			gajim.interface.roster.show_title()

	def sent_messages_scroll(self, direction, conv_buf):
		size = len(self.sent_history) 
		if self.orig_msg is None:
			# user was typing something and then went into history, so save
			# whatever is already typed
			start_iter = conv_buf.get_start_iter()
			end_iter = conv_buf.get_end_iter()
			self.orig_msg = conv_buf.get_text(start_iter, end_iter, 0).decode(
				'utf-8')
		if direction == 'up':
			if self.sent_history_pos == 0:
				return
			self.sent_history_pos = self.sent_history_pos - 1
			conv_buf.set_text(self.sent_history[self.sent_history_pos])
		elif direction == 'down':
			if self.sent_history_pos >= size - 1:
				conv_buf.set_text(self.orig_msg);
				self.orig_msg = None
				self.sent_history_pos = size
				return

			self.sent_history_pos = self.sent_history_pos + 1
			conv_buf.set_text(self.sent_history[self.sent_history_pos])

	def lighten_color(self, color):
		p = 0.4
		mask = 0
		color.red = int((color.red * p) + (mask * (1 - p)))
		color.green = int((color.green * p) + (mask * (1 - p)))
		color.blue = int((color.blue * p) + (mask * (1 - p)))
		return color

	def widget_set_visible(self, widget, state):
		'''Show or hide a widget. state is bool'''
		# make the last message visible, when changing to "full view"
		if not state:
			gobject.idle_add(self.conv_textview.scroll_to_end_iter)

		widget.set_no_show_all(state)
		if state:
			widget.hide()
		else:
			widget.show_all()

	def chat_buttons_set_visible(self, state):
		'''Toggle chat buttons. state is bool'''
		MessageControl.chat_buttons_set_visible(self, state)
		self.widget_set_visible(self.xml.get_widget('actions_hbox'), state)

	def got_connected(self):
		self.msg_textview.set_sensitive(True)
		self.msg_textview.set_editable(True)
		self.xml.get_widget('send_button').set_sensitive(True)

	def got_disconnected(self):
		self.msg_textview.set_sensitive(False)
		self.msg_textview.set_editable(False)
		self.conv_textview.tv.grab_focus()
		self.xml.get_widget('send_button').set_sensitive(False)

################################################################################
class ChatControl(ChatControlBase):
	'''A control for standard 1-1 chat'''
	TYPE_ID = message_control.TYPE_CHAT
	old_msg_kind = None # last kind of the printed message
	
	def __init__(self, parent_win, contact, acct, resource = None):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
			'chat_child_vbox', contact, acct, resource)
			
		# for muc use:
		# widget = self.xml.get_widget('muc_window_actions_button')
		widget = self.xml.get_widget('message_window_actions_button')
		id = widget.connect('clicked', self.on_actions_button_clicked)
		self.handlers[id] = widget

		hide_chat_buttons_always = gajim.config.get(
			'always_hide_chat_buttons')
		self.chat_buttons_set_visible(hide_chat_buttons_always)
		self.widget_set_visible(self.xml.get_widget('banner_eventbox'),
			gajim.config.get('hide_chat_banner'))
		# Initialize drag-n-drop
		self.TARGET_TYPE_URI_LIST = 80
		self.dnd_list = [ ( 'text/uri-list', 0, self.TARGET_TYPE_URI_LIST ) ]
		id = self.widget.connect('drag_data_received',
			self._on_drag_data_received)
		self.handlers[id] = self.widget
		self.widget.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
			gtk.DEST_DEFAULT_HIGHLIGHT |
			gtk.DEST_DEFAULT_DROP,
			self.dnd_list, gtk.gdk.ACTION_COPY)

		# keep timeout id and window obj for possible big avatar
		# it is on enter-notify and leave-notify so no need to be per jid
		self.show_bigger_avatar_timeout_id = None
		self.bigger_avatar_window = None
		self.show_avatar(self.contact.resource)			

		# chatstate timers and state
		self.reset_kbd_mouse_timeout_vars()
		self._schedule_activity_timers()

		# Hook up signals
		id = self.parent_win.window.connect('motion-notify-event',
			self._on_window_motion_notify)
		self.handlers[id] = self.parent_win.window
		message_tv_buffer = self.msg_textview.get_buffer()
		id = message_tv_buffer.connect('changed',
			self._on_message_tv_buffer_changed)
		self.handlers[id] = message_tv_buffer
		
		widget = self.xml.get_widget('avatar_eventbox')
		id = widget.connect('enter-notify-event',
			self.on_avatar_eventbox_enter_notify_event)
		self.handlers[id] = widget

		id = widget.connect('leave-notify-event',
			self.on_avatar_eventbox_leave_notify_event)
		self.handlers[id] = widget

		id = widget.connect('button-press-event',
			self.on_avatar_eventbox_button_press_event)
		self.handlers[id] = widget

		widget = self.xml.get_widget('gpg_togglebutton')
		id = widget.connect('clicked', self.on_toggle_gpg_togglebutton)
		self.handlers[id] = widget

		if self.contact.jid in gajim.encrypted_chats[self.account]:
			self.xml.get_widget('gpg_togglebutton').set_active(True)
		
		self.status_tooltip = gtk.Tooltips()
		self.update_ui()
		# restore previous conversation
		self.restore_conversation()

	def on_avatar_eventbox_enter_notify_event(self, widget, event):
		'''we enter the eventbox area so we under conditions add a timeout
		to show a bigger avatar after 0.5 sec'''
		jid = self.contact.jid
		is_fake = False
		if self.type_id == message_control.TYPE_PM:
			is_fake = True
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid,
			is_fake)
		if avatar_pixbuf in ('ask', None):
			return
		avatar_w = avatar_pixbuf.get_width()
		avatar_h = avatar_pixbuf.get_height()
		
		scaled_buf = self.xml.get_widget('avatar_image').get_pixbuf()
		scaled_buf_w = scaled_buf.get_width()
		scaled_buf_h = scaled_buf.get_height()
		
		# do we have something bigger to show?
		if avatar_w > scaled_buf_w or avatar_h > scaled_buf_h:
			# wait for 0.5 sec in case we leave earlier
			self.show_bigger_avatar_timeout_id = gobject.timeout_add(500,
				self.show_bigger_avatar, widget)
		
	def on_avatar_eventbox_leave_notify_event(self, widget, event):
		'''we left the eventbox area that holds the avatar img'''
		# did we add a timeout? if yes remove it
		if self.show_bigger_avatar_timeout_id is not None:
			gobject.source_remove(self.show_bigger_avatar_timeout_id)

	def on_avatar_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
			id = menuitem.connect('activate', 
				gtkgui_helpers.on_avatar_save_as_menuitem_activate,
				self.contact.jid, self.account, self.contact.get_shown_name() +  
					'.jpeg')
			self.handlers[id] = menuitem
			menu.append(menuitem)
			menu.show_all()
			menu.connect('selection-done', lambda w:w.destroy())	
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)
		return True

	def _on_window_motion_notify(self, widget, event):
		'''it gets called no matter if it is the active window or not'''
		if self.parent_win.get_active_jid() == self.contact.jid:
			# if window is the active one, change vars assisting chatstate
			self.mouse_over_in_last_5_secs = True
			self.mouse_over_in_last_30_secs = True

	def _schedule_activity_timers(self):
		self.possible_paused_timeout_id = gobject.timeout_add(5000,
			self.check_for_possible_paused_chatstate, None)
		self.possible_inactive_timeout_id = gobject.timeout_add(30000,
			self.check_for_possible_inactive_chatstate, None)

	def update_ui(self):
		# The name banner is drawn here
		ChatControlBase.update_ui(self)

	def _update_banner_state_image(self):
		contact = gajim.contacts.get_contact_with_highest_priority(self.account,
			self.contact.jid)
		if not contact or self.resource:
			# For transient contacts
			contact = self.contact
		show = contact.show
		jid = contact.jid

		# Set banner image
		img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
			size = '32', icon_name = show)
		img_16 = gajim.interface.roster.get_appropriate_state_images(jid,
			icon_name = show)
		if img_32.has_key(show) and img_32[show].get_pixbuf():
			# we have 32x32! use it!
			banner_image = img_32[show]
			use_size_32 = True
		else:
			banner_image = img_16[show]
			use_size_32 = False

		banner_status_img = self.xml.get_widget('banner_status_image')
		if banner_image.get_storage_type() == gtk.IMAGE_ANIMATION:
			banner_status_img.set_from_animation(banner_image.get_animation())
		else:
			pix = banner_image.get_pixbuf()
			if pix is not None:
				if use_size_32:
					banner_status_img.set_from_pixbuf(pix)
				else: # we need to scale 16x16 to 32x32
					scaled_pix = pix.scale_simple(32, 32,
									gtk.gdk.INTERP_BILINEAR)
					banner_status_img.set_from_pixbuf(scaled_pix)

		self._update_gpg()

	def draw_banner_text(self):
		'''Draw the text in the fat line at the top of the window that 
		houses the name, jid. 
		'''
		contact = self.contact
		jid = contact.jid

		banner_name_label = self.xml.get_widget('banner_name_label')
		name = contact.get_shown_name()
		if self.resource:
			name += '/' + self.resource
		if self.TYPE_ID == message_control.TYPE_PM:
			name = _('%(nickname)s from group chat %(room_name)s') %\
				{'nickname': name, 'room_name': self.room_name}
		name = gtkgui_helpers.escape_for_pango_markup(name)

		# We know our contacts nick, but if another contact has the same nick
		# in another account we need to also display the account.
		# except if we are talking to two different resources of the same contact
		acct_info = ''
		for account in gajim.contacts.get_accounts():
			if account == self.account:
				continue
			if acct_info: # We already found a contact with same nick
				break
			for jid in gajim.contacts.get_jid_list(account):
				contact_ = gajim.contacts.get_first_contact_from_jid(account, jid)
				if contact_.get_shown_name() == self.contact.get_shown_name():
					acct_info = ' (%s)' % \
						gtkgui_helpers.escape_for_pango_markup(self.account)
					break

		status = contact.status
		if status is not None:
			banner_name_label.set_ellipsize(pango.ELLIPSIZE_END)
			status = helpers.reduce_chars_newlines(status, max_lines = 2)
		status_escaped = gtkgui_helpers.escape_for_pango_markup(status)

		font_attrs, font_attrs_small = self.get_font_attrs()
		st = gajim.config.get('displayed_chat_state_notifications')
		cs = contact.chatstate
		if cs and st in ('composing_only', 'all'):
			if contact.show == 'offline':
				chatstate = ''
			elif contact.composing_jep == 'JEP-0085':
				if st == 'all' or cs == 'composing':
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			elif contact.composing_jep == 'JEP-0022':
				if cs in ('composing', 'paused'):
					# only print composing, paused
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			else:
				# When does that happen ? See [7797] and [7804]
				chatstate = helpers.get_uf_chatstate(cs)

			label_text = '<span %s>%s</span><span %s>%s %s</span>' % \
				(font_attrs, name, font_attrs_small, acct_info, chatstate)
		else:
			# weight="heavy" size="x-large"
			label_text = '<span %s>%s</span><span %s>%s</span>' % \
				(font_attrs, name, font_attrs_small, acct_info)
		if status_escaped:
			label_text += '\n<span %s>%s</span>' %\
				(font_attrs_small, status_escaped)
			banner_eventbox = self.xml.get_widget('banner_eventbox')
			self.status_tooltip.set_tip(banner_eventbox, status)
			self.status_tooltip.enable()
		else:
			self.status_tooltip.disable()
		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)

	def on_toggle_gpg_togglebutton(self, widget):
		gajim.config.set_per('contacts', self.contact.jid, 'gpg_enabled',
			widget.get_active())

	def _update_gpg(self):
		tb = self.xml.get_widget('gpg_togglebutton')
		# we can do gpg
		# if self.contact is our own contact info (transports), 
		# don't enable pgp
		if self.contact.keyID and not gajim.jid_is_transport(self.contact.jid): 
			tb.set_sensitive(True)
			tt = _('OpenPGP Encryption')

			# restore gpg pref
			gpg_pref = gajim.config.get_per('contacts', self.contact.jid,
				'gpg_enabled')
			if gpg_pref == None:
				gajim.config.add_per('contacts', self.contact.jid)
				gpg_pref = gajim.config.get_per('contacts', self.contact.jid,
					'gpg_enabled')
			tb.set_active(gpg_pref)

		else:
			tb.set_sensitive(False)
			#we talk about a contact here
			tt = _('%s has not broadcast an OpenPGP key, nor has one been assigned') %\
					self.contact.get_shown_name()
		gtk.Tooltips().set_tip(self.xml.get_widget('gpg_eventbox'), tt)

	def send_message(self, message, keyID = '', chatstate = None):
		'''Send a message to contact'''
		if message in ('', None, '\n') or self._process_command(message):
			return

		# refresh timers
		self.reset_kbd_mouse_timeout_vars()

		contact = self.contact

		keyID = ''
		encrypted = False
		if self.xml.get_widget('gpg_togglebutton').get_active():
			keyID = contact.keyID
			encrypted = True


		chatstates_on = gajim.config.get('outgoing_chat_state_notifications') != \
			'disabled'
		composing_jep = contact.composing_jep
		chatstate_to_send = None
		if chatstates_on and contact is not None:
			if composing_jep is None:
				# no info about peer
				# send active to discover chat state capabilities
				# this is here (and not in send_chatstate)
				# because we want it sent with REAL message
				# (not standlone) eg. one that has body
				
				#FIXME:
				# Enable 3 next lines after 0.11 release.
				# Having this disabled violate xep85 5.1.2 but then we don't break
				# notifications between 0.10.1 and 0.11 See #2637
				# if contact.our_chatstate:
				#	# We already ask for xep 85, don't ask it twice
				#	composing_jep = 'asked_once'

				chatstate_to_send = 'active'
				contact.our_chatstate = 'ask' # pseudo state
			# if peer supports jep85 and we are not 'ask', send 'active'
			# NOTE: first active and 'ask' is set in gajim.py
			elif composing_jep is not False:
				#send active chatstate on every message (as JEP says)
				chatstate_to_send = 'active'
				contact.our_chatstate = 'active'

				gobject.source_remove(self.possible_paused_timeout_id)
				gobject.source_remove(self.possible_inactive_timeout_id)
				self._schedule_activity_timers()
				
		if not ChatControlBase.send_message(self, message, keyID, type = 'chat',
		chatstate = chatstate_to_send, composing_jep = composing_jep):
			self.print_conversation(message, self.contact.jid,
				encrypted = encrypted)

	def check_for_possible_paused_chatstate(self, arg):
		''' did we move mouse of that window or write something in message
		textview in the last 5 seconds?
		if yes we go active for mouse, composing for kbd
		if no we go paused if we were previously composing '''
		contact = self.contact
		jid = contact.jid
		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		message_buffer = self.msg_textview.get_buffer()
		if self.kbd_activity_in_last_5_secs and message_buffer.get_char_count():
			# Only composing if the keyboard activity was in text entry
			self.send_chatstate('composing')
		elif self.mouse_over_in_last_5_secs and\
			jid == self.parent_win.get_active_jid():
			self.send_chatstate('active')
		else:
			if current_state == 'composing':
				self.send_chatstate('paused') # pause composing

		# assume no activity and let the motion-notify or 'insert-text' make them
		# True refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever		

	def check_for_possible_inactive_chatstate(self, arg):
		''' did we move mouse over that window or wrote something in message
		textview in the last 30 seconds?
		if yes we go active
		if no we go inactive '''
		contact = self.contact

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
			return True # loop forever

		if not self.mouse_over_in_last_30_secs or \
		self.kbd_activity_in_last_30_secs:
			self.send_chatstate('inactive', contact)

		# assume no activity and let the motion-notify or 'insert-text' make them
		# True refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def reset_kbd_mouse_timeout_vars(self):
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False

	def print_conversation(self, text, frm = '', tim = None,
		encrypted = False, subject = None, xhtml = None):
		'''Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is set to print_queue: it is incomming from queue
		if contact is not set: it's an incomming message'''
		contact = self.contact
		jid = contact.jid

		if frm == 'status':
			if not gajim.config.get('print_status_in_chats'):
				return
			kind = 'status'
			name = ''
		elif frm == 'info':
			kind = 'info'
			name = ''
		else:
			ec = gajim.encrypted_chats[self.account]
			if encrypted and jid not in ec:
				msg = _('Encryption enabled')
				ChatControlBase.print_conversation_line(self, msg, 
					'status', '', tim)
				ec.append(jid)
			elif not encrypted and jid in ec:
				msg = _('Encryption disabled')
				ChatControlBase.print_conversation_line(self, msg,
					'status', '', tim)
				ec.remove(jid)
			self.xml.get_widget('gpg_togglebutton').set_active(encrypted)
			if not frm:
				kind = 'incoming'
				name = contact.get_shown_name()
			elif frm == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = contact.get_shown_name()
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account]
				if not xhtml and not encrypted and gajim.config.get('rst_formatting_outgoing_messages'):
					xhtml = create_xhtml(text)
					if xhtml:
						xhtml = '<body xmlns="%s">%s</body>' % (NS_XHTML, xhtml)
		ChatControlBase.print_conversation_line(self, text, kind, name, tim,
			subject = subject, old_kind = self.old_msg_kind, xhtml = xhtml)
		if text.startswith('/me ') or text.startswith('/me\n'):
			self.old_msg_kind = None
		else:
			self.old_msg_kind = kind

	def get_tab_label(self, chatstate):
		unread = ''
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		num_unread = len(gajim.events.get_events(self.account, jid,
			['printed_' + self.type_id, self.type_id]))
		if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
			unread = '*'
		elif num_unread > 1:
			unread = '[' + unicode(num_unread) + ']'

		# Draw tab label using chatstate 
		theme = gajim.config.get('roster_theme')
		color = None
		if not chatstate:
			chatstate = self.contact.chatstate
		if chatstate is not None:
			if chatstate == 'composing':
				color = gajim.config.get_per('themes', theme,
						'state_composing_color')
			elif chatstate == 'inactive':
				color = gajim.config.get_per('themes', theme,
						'state_inactive_color')
			elif chatstate == 'gone':
				color = gajim.config.get_per('themes', theme,
						'state_gone_color')
			elif chatstate == 'paused':
				color = gajim.config.get_per('themes', theme,
						'state_paused_color')
		if color:
			# We set the color for when it's the current tab or not
			color = gtk.gdk.colormap_get_system().alloc_color(color)
			# In inactive tab color to be lighter against the darker inactive
			# background
			if chatstate in ('inactive', 'gone') and\
			self.parent_win.get_active_control() != self:
				color = self.lighten_color(color)
		else: # active or not chatstate, get color from gtk
			color = self.parent_win.notebook.style.fg[gtk.STATE_ACTIVE]
		

		name = self.contact.get_shown_name()
		if self.resource:
			name += '/' + self.resource
		label_str = gtkgui_helpers.escape_for_pango_markup(name)
		if num_unread: # if unread, text in the label becomes bold
			label_str = '<b>' + unread + label_str + '</b>'
		return (label_str, color)

	def get_tab_image(self):
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		num_unread = len(gajim.events.get_events(self.account, jid,
			['printed_' + self.type_id, self.type_id]))
		# Set tab image (always 16x16); unread messages show the 'message' image
		tab_img = None
		
		if num_unread and gajim.config.get('show_unread_tab_icon'):
			img_16 = gajim.interface.roster.get_appropriate_state_images(
				self.contact.jid, icon_name = 'message')
			tab_img = img_16['message']
		else:
			contact = gajim.contacts.get_contact_with_highest_priority(
				self.account, self.contact.jid)
			if not contact or self.resource:
				# For transient contacts
				contact = self.contact
			img_16 = gajim.interface.roster.get_appropriate_state_images(
				self.contact.jid, icon_name = contact.show)
			tab_img = img_16[contact.show]

		return tab_img

	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		sets sensitivity for history_menuitem (False for tranasports)
		and file_transfer_menuitem
		and hide()/show() for add_to_roster_menuitem
		'''
		xml = gtkgui_helpers.get_glade('chat_control_popup_menu.glade')
		menu = xml.get_widget('chat_control_popup_menu')
		
		history_menuitem = xml.get_widget('history_menuitem')
		toggle_gpg_menuitem = xml.get_widget('toggle_gpg_menuitem')
		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		compact_view_menuitem = xml.get_widget('compact_view_menuitem')
		information_menuitem = xml.get_widget('information_menuitem')
		
		contact = self.parent_win.get_active_contact()
		jid = contact.jid
		
		# history_menuitem
		if gajim.jid_is_transport(jid):
			history_menuitem.set_sensitive(False)
		
		# check if gpg capabitlies or else make gpg toggle insensitive
		gpg_btn = self.xml.get_widget('gpg_togglebutton')
		isactive = gpg_btn.get_active()
		is_sensitive = gpg_btn.get_property('sensitive')
		toggle_gpg_menuitem.set_active(isactive)
		toggle_gpg_menuitem.set_property('sensitive', is_sensitive)
		
		# If we don't have resource, we can't do file transfer
		# in transports, contact holds our info we need to disable it too
		if contact.resource and contact.jid.find('@') != -1:
			send_file_menuitem.set_sensitive(True)
		else:
			send_file_menuitem.set_sensitive(False)
		
		# compact_view_menuitem
		compact_view_menuitem.set_active(self.hide_chat_buttons_current)
		
		# add_to_roster_menuitem
		if _('Not in Roster') in contact.groups:
			add_to_roster_menuitem.show()
			add_to_roster_menuitem.set_no_show_all(False)
		else:
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)
		
		
		# connect signals
		id = history_menuitem.connect('activate', 
			self._on_history_menuitem_activate)
		self.handlers[id] = history_menuitem
		id = send_file_menuitem.connect('activate', 
			self._on_send_file_menuitem_activate)
		self.handlers[id] = send_file_menuitem 
		id = compact_view_menuitem.connect('activate', 
			self._on_compact_view_menuitem_activate)
		self.handlers[id] = compact_view_menuitem 
		id = add_to_roster_menuitem.connect('activate', 
			self._on_add_to_roster_menuitem_activate)
		self.handlers[id] = add_to_roster_menuitem 
		id = toggle_gpg_menuitem.connect('activate', 
			self._on_toggle_gpg_menuitem_activate)
		self.handlers[id] = toggle_gpg_menuitem 
		id = information_menuitem.connect('activate', 
			self._on_contact_information_menuitem_activate)
		self.handlers[id] = information_menuitem
		menu.connect('selection-done', lambda w:w.destroy())	
		return menu

	def send_chatstate(self, state, contact = None):
		''' sends OUR chatstate as STANDLONE chat state message (eg. no body)
		to contact only if new chatstate is different from the previous one
		if jid is not specified, send to active tab'''
		# JEP 85 does not allow resending the same chatstate
		# this function checks for that and just returns so it's safe to call it
		# with same state.
		
		# This functions also checks for violation in state transitions
		# and raises RuntimeException with appropriate message
		# more on that http://www.jabber.org/jeps/jep-0085.html#statechart

		# do not send nothing if we have chat state notifications disabled
		# that means we won't reply to the <active/> from other peer
		# so we do not broadcast jep85 capabalities
		chatstate_setting = gajim.config.get('outgoing_chat_state_notifications')
		if chatstate_setting == 'disabled':
			return
		elif chatstate_setting == 'composing_only' and state != 'active' and\
			state != 'composing':
			return

		if contact is None:
			contact = self.parent_win.get_active_contact()
			if contact is None:
				# contact was from pm in MUC, and left the room so contact is None
				# so we cannot send chatstate anymore
				return

		# Don't send chatstates to offline contacts
		if contact.show == 'offline':
			return

		if contact.composing_jep is False: # jid cannot do jep85 nor jep22
			return

		# if the new state we wanna send (state) equals 
		# the current state (contact.our_chatstate) then return
		if contact.our_chatstate == state:
			return

		if contact.composing_jep is None:
			# we don't know anything about jid, so return
			# NOTE:
			# send 'active', set current state to 'ask' and return is done
			# in self.send_message() because we need REAL message (with <body>)
			# for that procedure so return to make sure we send only once
			# 'active' until we know peer supports jep85
			return 

		if contact.our_chatstate == 'ask':
			return

		# in JEP22, when we already sent stop composing
		# notification on paused, don't resend it
		if contact.composing_jep == 'JEP-0022' and \
		contact.our_chatstate in ('paused', 'active', 'inactive') and \
		state is not 'composing': # not composing == in (active, inactive, gone)
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()
			return

		# prevent going paused if we we were not composing (JEP violation)
		if state == 'paused' and not contact.our_chatstate == 'composing':
			# go active before
			MessageControl.send_message(self, None, chatstate = 'active')
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()
		
		# if we're inactive prevent composing (JEP violation)
		elif contact.our_chatstate == 'inactive' and state == 'composing':
			# go active before
			MessageControl.send_message(self, None, chatstate = 'active')
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()

		MessageControl.send_message(self, None, chatstate = state,
			msg_id = contact.msg_id, composing_jep = contact.composing_jep)
		contact.our_chatstate = state
		if contact.our_chatstate == 'active':
			self.reset_kbd_mouse_timeout_vars()

	def shutdown(self):
		# destroy banner tooltip - bug #pygtk for that!
		self.status_tooltip.destroy()
		# Send 'gone' chatstate
		self.send_chatstate('gone', self.contact)
		self.contact.chatstate = None
		self.contact.our_chatstate = None
		# Disconnect timer callbacks
		gobject.source_remove(self.possible_paused_timeout_id)
		gobject.source_remove(self.possible_inactive_timeout_id)
		# Remove bigger avatar window
		if self.bigger_avatar_window:
			self.bigger_avatar_window.destroy()
		# Clean events
		gajim.events.remove_events(self.account, self.get_full_jid(),
			types = ['printed_' + self.type_id, self.type_id])
		# remove all register handlers on wigets, created by self.xml
		# to prevent circular references among objects
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
			del self.handlers[i]
		self.conv_textview.del_handlers()
		self.msg_textview.destroy()
		

	def allow_shutdown(self, method):
		if time.time() - gajim.last_message_time[self.account]\
		[self.get_full_jid()] < 2:
			# 2 seconds
			dialog = dialogs.ConfirmationDialog(
				#%s is being replaced in the code with JID
				_('You just received a new message from "%s"') % self.contact.jid,
				_('If you close this tab and you have history disabled, '\
				'this message will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return False #stop the propagation of the event
		return True

	def handle_incoming_chatstate(self):
		''' handle incoming chatstate that jid SENT TO us '''
		self.draw_banner_text()
		# update chatstate in tab for this chat
		self.parent_win.redraw_tab(self, self.contact.chatstate)

	def set_control_active(self, state):
		ChatControlBase.set_control_active(self, state)
		# send chatstate inactive to the one we're leaving
		# and active to the one we visit
		if state:
			self.send_chatstate('active', self.contact)
		else:
			self.send_chatstate('inactive', self.contact)

	def show_avatar(self, resource = None):
		if not gajim.config.get('show_avatar_in_chat'):
			return

		jid = self.contact.jid
		jid_with_resource = jid
		if resource:
			jid_with_resource += '/' + resource

		# we assume contact has no avatar
		scaled_pixbuf = None

		pixbuf = None
		is_fake = False
		if gajim.contacts.is_pm_from_jid(self.account, jid):
			is_fake = True
		pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid_with_resource,
			is_fake)
		if pixbuf == 'ask':
			# we don't have the vcard
			gajim.connections[self.account].request_vcard(jid_with_resource,
				is_fake)
			return
		if pixbuf is not None:
			scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'chat')

		image = self.xml.get_widget('avatar_image')
		image.set_from_pixbuf(scaled_pixbuf)
		image.show_all()

	def _on_drag_data_received(self, widget, context, x, y, selection,
		target_type, timestamp):
		# If not resource, we can't send file
		if not self.contact.resource:
			return
		if target_type == self.TARGET_TYPE_URI_LIST:
			uri = selection.data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				if os.path.isfile(path): # is it file?
					ft = gajim.interface.instances['file_transfers']
					ft.send_file(self.account, self.contact, path)

	def _on_message_tv_buffer_changed(self, textbuffer):
		self.kbd_activity_in_last_5_secs = True
		self.kbd_activity_in_last_30_secs = True
		if textbuffer.get_char_count():
			self.send_chatstate('composing', self.contact)
		else:
			self.send_chatstate('active', self.contact)

	def restore_conversation(self):
		jid = self.contact.jid
		# don't restore lines if it's a transport
		if gajim.jid_is_transport(jid):
			return

		# How many lines to restore and when to time them out
		restore_how_many = gajim.config.get('restore_lines')
		if restore_how_many <= 0:
			return
		timeout = gajim.config.get('restore_timeout') # in minutes

		# number of messages that are in queue and are already logged, we want
		# to avoid duplication
		pending_how_many = len(gajim.events.get_events(self.account, jid,
			['chat', 'pm']))
		if self.resource:
			pending_how_many += len(gajim.events.get_events(self.account,
				self.contact.get_full_jid(), ['chat', 'pm']))

		rows = gajim.logger.get_last_conversation_lines(jid, restore_how_many,
			pending_how_many, timeout, self.account)
		local_old_kind = None
		for row in rows: # row[0] time, row[1] has kind, row[2] the message
			if not row[2]: # message is empty, we don't print it
				continue
			if row[1] in (constants.KIND_CHAT_MSG_SENT,
					constants.KIND_SINGLE_MSG_SENT):
				kind = 'outgoing'
				name = gajim.nicks[self.account]
			elif row[1] in (constants.KIND_SINGLE_MSG_RECV,
					constants.KIND_CHAT_MSG_RECV):
				kind = 'incoming'
				name = self.contact.get_shown_name()
			elif row[1] == constants.KIND_ERROR:
				kind = 'status'
				name = self.contact.get_shown_name()

			tim = time.localtime(float(row[0]))

			if gajim.config.get('restored_messages_small'):
				small_attr = ['small']
			else:
				small_attr = []
			ChatControlBase.print_conversation_line(self, row[2], kind, name, tim,
								small_attr,
								small_attr + ['restored_message'],
								small_attr + ['restored_message'],
								False, old_kind = local_old_kind)
			if row[2].startswith('/me ') or row[2].startswith('/me\n'):
				local_old_kind = None
			else:
				local_old_kind = kind
		if len(rows):
			self.conv_textview.print_empty_line()

	def read_queue(self):
		'''read queue and print messages containted in it'''
		jid = self.contact.jid
		jid_with_resource = jid
		if self.resource:
			jid_with_resource += '/' + self.resource
		events = gajim.events.get_events(self.account, jid_with_resource)

		# Is it a pm ?
		is_pm = False
		room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
		control = gajim.interface.msg_win_mgr.get_control(room_jid, self.account)
		if control and control.type_id == message_control.TYPE_GC:
			is_pm = True
		# list of message ids which should be marked as read
		message_ids = []
		for event in events:
			if event.type_ != self.type_id:
				continue
			data = event.parameters
			kind = data[2]
			if kind == 'error':
				kind = 'info'
			else:
				kind = 'print_queue'
			self.print_conversation(data[0], kind, tim = data[3],
				encrypted = data[4], subject = data[1], xhtml = data[7])
			if len(data) > 6 and isinstance(data[6], int):
				message_ids.append(data[6])
		if message_ids:
			gajim.logger.set_read_messages(message_ids)
		gajim.events.remove_events(self.account, jid_with_resource,
			types = [self.type_id])

		typ = 'chat' # Is it a normal chat or a pm ?
		# reset to status image in gc if it is a pm
		if is_pm:
			control.update_ui()
			control.parent_win.show_title()
			typ = 'pm'

		self.redraw_after_event_removed(jid)
		if (self.contact.show in ('offline', 'error')):
			show_offline = gajim.config.get('showoffline')
			show_transports = gajim.config.get('show_transports_group')
			if (not show_transports and gajim.jid_is_transport(jid)) or \
			(not show_offline and typ == 'chat' and \
			len(gajim.contacts.get_contact(self.account, jid)) < 2):
				gajim.interface.roster.really_remove_contact(self.contact,
					self.account)
			elif typ == 'pm':
				control.remove_contact(nick)

	def show_bigger_avatar(self, small_avatar):
		'''resizes the avatar, if needed, so it has at max half the screen size
		and shows it'''
		if not small_avatar.window:
			# Tab has been closed since we hovered the avatar
			return
		is_fake = False
		if self.type_id == message_control.TYPE_PM:
			is_fake = True
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(
			self.contact.jid, is_fake)
		if avatar_pixbuf in ('ask', None):
			return
		# Hide the small avatar
		# this code hides the small avatar when we show a bigger one in case
		# the avatar has a transparency hole in the middle
		# so when we show the big one we avoid seeing the small one behind.
		# It's why I set it transparent.
		image = self.xml.get_widget('avatar_image')
		pixbuf = image.get_pixbuf()
		pixbuf.fill(0xffffff00L) # RGBA
		image.queue_draw()

		screen_w = gtk.gdk.screen_width()
		screen_h = gtk.gdk.screen_height()
		avatar_w = avatar_pixbuf.get_width()
		avatar_h = avatar_pixbuf.get_height()
		half_scr_w = screen_w / 2
		half_scr_h = screen_h / 2
		if avatar_w > half_scr_w:
			avatar_w = half_scr_w
		if avatar_h > half_scr_h:
			avatar_h = half_scr_h
		window = gtk.Window(gtk.WINDOW_POPUP)
		self.bigger_avatar_window = window
		pixmap, mask = avatar_pixbuf.render_pixmap_and_mask()
		window.set_size_request(avatar_w, avatar_h)
		# we should make the cursor visible
		# gtk+ doesn't make use of the motion notify on gtkwindow by default
		# so this line adds that
		window.set_events(gtk.gdk.POINTER_MOTION_MASK)
		window.set_app_paintable(True)
		
		window.realize()
		window.window.set_back_pixmap(pixmap, False) # make it transparent
		window.window.shape_combine_mask(mask, 0, 0)

		# make the bigger avatar window show up centered 
		x0, y0 = small_avatar.window.get_origin()
		x0 += small_avatar.allocation.x
		y0 += small_avatar.allocation.y
		center_x= x0 + (small_avatar.allocation.width / 2)
		center_y = y0 + (small_avatar.allocation.height / 2)
		pos_x, pos_y = center_x - (avatar_w / 2), center_y - (avatar_h / 2) 
		window.move(pos_x, pos_y)
		# make the cursor invisible so we can see the image
		invisible_cursor = gtkgui_helpers.get_invisible_cursor()
		window.window.set_cursor(invisible_cursor)

		# we should hide the window
		window.connect('leave_notify_event',
			self._on_window_avatar_leave_notify_event)
		window.connect('motion-notify-event',
			self._on_window_motion_notify_event)

		window.show_all()

	def _on_window_avatar_leave_notify_event(self, widget, event):
		'''we just left the popup window that holds avatar'''
		self.bigger_avatar_window.destroy()
		self.bigger_avatar_window = None
		# Re-show the small avatar
		self.show_avatar()

	def _on_window_motion_notify_event(self, widget, event):
		'''we just moved the mouse so show the cursor'''
		cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
		self.bigger_avatar_window.window.set_cursor(cursor)

	def _on_send_file_menuitem_activate(self, widget):
		gajim.interface.instances['file_transfers'].show_file_send_request( 
			self.account, self.contact)

	def _on_add_to_roster_menuitem_activate(self, widget):
		dialogs.AddNewContactWindow(self.account, self.contact.jid)

	def _on_contact_information_menuitem_activate(self, widget):
		gajim.interface.roster.on_info(widget, self.contact, self.account)

	def _on_toggle_gpg_menuitem_activate(self, widget):
		# update the button
		# this is reverse logic, as we are on 'activate' (before change happens)
		tb = self.xml.get_widget('gpg_togglebutton')
		tb.set_active(not tb.get_active())

	def got_connected(self):
		ChatControlBase.got_connected(self)
		# Refreshing contact
		contact = gajim.contacts.get_contact_with_highest_priority(
			self.account, self.contact.jid)
		if isinstance(contact, GC_Contact):
			contact = gajim.contacts.contact_from_gc_contact(contact)
		if contact:
			self.contact = contact
		self.draw_banner()
