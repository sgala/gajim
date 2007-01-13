##	groupchat_control.py
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <kourem@gmail.com>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
## Copyright (C) 2006 Travis Shirk <travis@pobox.com>
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
import tooltips
import dialogs
import config
import vcard
import cell_renderer_image

from common import gajim
from common import helpers

from chat_control import ChatControl
from chat_control import ChatControlBase
from conversation_textview import ConversationTextview
from common.exceptions import GajimGeneralException

#(status_image, type, nick, shown_nick)
(
C_IMG, # image to show state (online, new message etc)
C_NICK, # contact nickame or ROLE name
C_TYPE, # type of the row ('contact' or 'role')
C_TEXT, # text shown in the cellrenderer
C_AVATAR, # avatar of the contact
) = range(5)
	
def set_renderer_color(treeview, renderer, set_background = True):
	'''set style for group row, using PRELIGHT system color'''
	if set_background:
		bgcolor = treeview.style.bg[gtk.STATE_PRELIGHT]
		renderer.set_property('cell-background-gdk', bgcolor)
	else:
		fgcolor = treeview.style.fg[gtk.STATE_PRELIGHT]
		renderer.set_property('foreground-gdk', fgcolor)

def tree_cell_data_func(column, renderer, model, iter, tv=None):
	# cell data func is global, because we don't want it to keep
	# reference to GroupchatControl instance (self)
	theme = gajim.config.get('roster_theme')
	if model.iter_parent(iter):
		bgcolor = gajim.config.get_per('themes', theme, 'contactbgcolor')
		if bgcolor:
			renderer.set_property('cell-background', bgcolor)
		else:
			renderer.set_property('cell-background', None)
		if isinstance(renderer, gtk.CellRendererText):
			# foreground property is only with CellRendererText
			color = gajim.config.get_per('themes', theme, 'contacttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
	else: # it is root (eg. group)
		bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
		if bgcolor:
			renderer.set_property('cell-background', bgcolor)
		else:
			set_renderer_color(tv, renderer)
		if isinstance(renderer, gtk.CellRendererText):
			# foreground property is only with CellRendererText
			color = gajim.config.get_per('themes', theme, 'grouptextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				set_renderer_color(tv, renderer, False)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))

class PrivateChatControl(ChatControl):
	TYPE_ID = message_control.TYPE_PM

	def __init__(self, parent_win, contact, acct):
		room_jid = contact.jid.split('/')[0]
		room_ctrl = gajim.interface.msg_win_mgr.get_control(room_jid, acct)
		self.room_name = room_ctrl.name
		ChatControl.__init__(self, parent_win, contact, acct)
		self.TYPE_ID = 'pm'
		self.display_names = (_('Private Chat'), _('Private Chats'))

	def send_message(self, message):
		'''call this function to send our message'''
		if not message:
			return

		# We need to make sure that we can still send through the room and that
		# the recipient did not go away
		contact = gajim.contacts.get_first_contact_from_jid(self.account,
			self.contact.jid)
		if contact is None:
			# contact was from pm in MUC
			room, nick = gajim.get_room_and_nick_from_fjid(self.contact.jid)
			gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
			if not gc_contact:
				dialogs.ErrorDialog(
					_('Sending private message failed'),
					#in second %s code replaces with nickname
					_('You are no longer in group chat "%s" or "%s" has left.') % \
					(room, nick))
				return

		ChatControl.send_message(self, message)
	
	def update_ui(self):
		if self.contact.show == 'offline':
			self.got_disconnected()
		else:
			self.got_connected()
		ChatControl.update_ui(self)


class GroupchatControl(ChatControlBase):
	TYPE_ID = message_control.TYPE_GC

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', (_('Group Chat'), _('Group Chats')),
					contact, acct);

		widget = self.xml.get_widget('muc_window_actions_button')
		id = widget.connect('clicked', self.on_actions_button_clicked)
		self.handlers[id] = widget

		widget = self.xml.get_widget('list_treeview')
		id = widget.connect('row_expanded', self.on_list_treeview_row_expanded)
		self.handlers[id] = widget

		id = widget.connect('row_collapsed', 
			self.on_list_treeview_row_collapsed)
		self.handlers[id] = widget

		id = widget.connect('row_activated', 
			self.on_list_treeview_row_activated)
		self.handlers[id] = widget

		id = widget.connect('button_press_event', 
			self.on_list_treeview_button_press_event)
		self.handlers[id] = widget

		id = widget.connect('key_press_event', 
			self.on_list_treeview_key_press_event)
		self.handlers[id] = widget

		id = widget.connect('motion_notify_event', 
			self.on_list_treeview_motion_notify_event)
		self.handlers[id] = widget

		id = widget.connect('leave_notify_event', 
			self.on_list_treeview_leave_notify_event)
		self.handlers[id] = widget

		self.room_jid = self.contact.jid
		self.nick = contact.name
		self.name = self.room_jid.split('@')[0]

		hide_chat_buttons_always = gajim.config.get(
			'always_hide_groupchat_buttons')
		self.chat_buttons_set_visible(hide_chat_buttons_always)
		self.widget_set_visible(self.xml.get_widget('banner_eventbox'),
			gajim.config.get('hide_groupchat_banner'))
		self.widget_set_visible(self.xml.get_widget('list_scrolledwindow'),
			gajim.config.get('hide_groupchat_occupants_list'))

		self._last_selected_contact = None # None or holds jid, account tuple
		# alphanum sorted
		self.muc_cmds = ['ban', 'chat', 'query', 'clear', 'close', 'compact',
			'help', 'invite', 'join', 'kick', 'leave', 'me', 'msg', 'nick',
			'part', 'names', 'say', 'topic']
		# muc attention flag (when we are mentioned in a muc)
		# if True, the room has mentioned us
		self.attention_flag = False
		self.room_creation = time.time()
		self.nick_hits = []
		self.cmd_hits = []
		self.last_key_tabs = False

		self.subject = ''
		self.subject_tooltip = gtk.Tooltips()

		self.tooltip = tooltips.GCTooltip()

		# connect the menuitems to their respective functions
		xm = gtkgui_helpers.get_glade('gc_control_popup_menu.glade')

		widget = xm.get_widget('bookmark_room_menuitem')
		id = widget.connect('activate',
			self._on_bookmark_room_menuitem_activate)
		self.handlers[id] = widget

		widget = xm.get_widget('change_nick_menuitem')
		id = widget.connect('activate', self._on_change_nick_menuitem_activate)
		self.handlers[id] = widget

		widget = xm.get_widget('configure_room_menuitem')
		id = widget.connect('activate',
			self._on_configure_room_menuitem_activate)
		self.handlers[id] = widget

		widget = xm.get_widget('change_subject_menuitem')
		id = widget.connect('activate',
			self._on_change_subject_menuitem_activate)
		self.handlers[id] = widget

		widget = xm.get_widget('compact_view_menuitem')
		id = widget.connect('activate', self._on_compact_view_menuitem_activate)
		self.handlers[id] = widget

		widget = xm.get_widget('history_menuitem')
		id = widget.connect('activate', self._on_history_menuitem_activate)
		self.handlers[id] = widget

		self.gc_popup_menu = xm.get_widget('gc_control_popup_menu')

		self.name_label = self.xml.get_widget('banner_name_label')
		self.event_box = self.xml.get_widget('banner_eventbox')

		# set the position of the current hpaned
		self.hpaned_position = gajim.config.get('gc-hpaned-position')
		self.hpaned = self.xml.get_widget('hpaned')
		self.hpaned.set_position(self.hpaned_position)

		self.list_treeview = self.xml.get_widget('list_treeview')
		selection = self.list_treeview.get_selection()
		id = selection.connect('changed', 
				self.on_list_treeview_selection_changed)
		self.handlers[id] = selection
		id = self.list_treeview.connect('style-set',
			self.on_list_treeview_style_set)
		self.handlers[id] = self.list_treeview
		# we want to know when the the widget resizes, because that is
		# an indication that the hpaned has moved...
		# FIXME: Find a better indicator that the hpaned has moved.
		id = self.list_treeview.connect('size-allocate',
			self.on_treeview_size_allocate)
		self.handlers[id] = self.list_treeview
		#status_image, shown_nick, type, nickname, avatar
		store = gtk.TreeStore(gtk.Image, str, str, str, gtk.gdk.Pixbuf)
		store.set_sort_column_id(C_TEXT, gtk.SORT_ASCENDING)
		self.list_treeview.set_model(store)

		# columns

		# this col has 3 cells:
		# first one img, second one text, third is sec pixbuf
		column = gtk.TreeViewColumn()

		renderer_pixbuf = gtk.CellRendererPixbuf() # avatar image
		column.pack_start(renderer_pixbuf, expand = False)
		column.add_attribute(renderer_pixbuf, 'pixbuf', C_AVATAR)
		column.set_cell_data_func(renderer_pixbuf, tree_cell_data_func,
			self.list_treeview)
		renderer_pixbuf.set_property('xalign', 1) # align pixbuf to the right

		renderer_image = cell_renderer_image.CellRendererImage(0, 0) # status img
		column.pack_start(renderer_image, expand = False)
		column.add_attribute(renderer_image, 'image', C_IMG)
		column.set_cell_data_func(renderer_image, tree_cell_data_func, 
			self.list_treeview)

		renderer_text = gtk.CellRendererText() # nickname
		column.pack_start(renderer_text, expand = True)
		column.add_attribute(renderer_text, 'markup', C_TEXT)
		column.set_cell_data_func(renderer_text, tree_cell_data_func,
			self.list_treeview)

		self.list_treeview.append_column(column)

		# workaround to avoid gtk arrows to be shown
		column = gtk.TreeViewColumn() # 2nd COLUMN
		renderer = gtk.CellRendererPixbuf()
		column.pack_start(renderer, expand = False)
		self.list_treeview.append_column(column)
		column.set_visible(False)
		self.list_treeview.set_expander_column(column)

		gajim.gc_connected[self.account][self.room_jid] = False
		# disable win, we are not connected yet
		ChatControlBase.got_disconnected(self) 

		self.update_ui()
		self.conv_textview.tv.grab_focus()
		self.widget.show_all()

	def on_msg_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		and the ability to insert a nick'''
		ChatControlBase.on_msg_textview_populate_popup(self, textview, menu)
		item = gtk.SeparatorMenuItem()
		menu.prepend(item)

		item = gtk.MenuItem(_('Insert Nickname'))
		menu.prepend(item)
		submenu = gtk.Menu()
		item.set_submenu(submenu)

		for nick in sorted(gajim.contacts.get_nick_list(self.account,
		self.room_jid)):
			item = gtk.MenuItem(nick, use_underline = False)
			submenu.append(item)
			id = item.connect('activate', self.append_nick_in_msg_textview, nick)
			self.handlers[id] = item

		menu.show_all()

	def on_treeview_size_allocate(self, widget, allocation):
		'''The MUC treeview has resized. Move the hpaned in all tabs to match'''
		self.hpaned_position = self.hpaned.get_position()
		self.hpaned.set_position(self.hpaned_position)

	def iter_contact_rows(self):
		'''iterate over all contact rows in the tree model'''
		model = self.list_treeview.get_model()
		role_iter = model.get_iter_root()
		while role_iter:
			contact_iter = model.iter_children(role_iter)
			while contact_iter:
				yield model[contact_iter]
				contact_iter = model.iter_next(contact_iter)
			role_iter = model.iter_next(role_iter)

	def on_list_treeview_style_set(self, treeview, style):
		'''When style (theme) changes, redraw all contacts'''
		# Get the room_jid from treeview
		for contact in self.iter_contact_rows():
			nick = contact[C_NICK].decode('utf-8')
			self.draw_contact(nick)

	def on_list_treeview_selection_changed(self, selection):
		model, selected_iter = selection.get_selected()
		self.draw_contact(self.nick)
		if self._last_selected_contact is not None:
			self.draw_contact(self._last_selected_contact)
		if selected_iter is None:
			self._last_selected_contact = None
			return
		contact = model[selected_iter]
		nick = contact[C_NICK].decode('utf-8')
		self._last_selected_contact = nick
		if contact[C_TYPE] != 'contact':
			return
		self.draw_contact(nick, selected=True, focus=True)

	def get_tab_label(self, chatstate):
		'''Markup the label if necessary. Returns a tuple such as:
		(new_label_str, color)
		either of which can be None
		if chatstate is given that means we have HE SENT US a chatstate'''

		has_focus = self.parent_win.window.get_property('has-toplevel-focus')
		current_tab = self.parent_win.get_active_control() == self
		color_name = None
		color = None
		theme = gajim.config.get('roster_theme')
		if chatstate == 'attention' and (not has_focus or not current_tab):
			self.attention_flag = True
			color_name = gajim.config.get_per('themes', theme,
							'state_muc_directed_msg_color')
		elif chatstate:
			if chatstate == 'active' or (current_tab and has_focus):
				self.attention_flag = False
				# get active color from gtk
				color = self.parent_win.notebook.style.fg[gtk.STATE_ACTIVE]
			elif chatstate == 'newmsg' and (not has_focus or not current_tab) and\
					not self.attention_flag:
				color_name = gajim.config.get_per('themes', theme,
					'state_muc_msg_color')
		if color_name:
			color = gtk.gdk.colormap_get_system().alloc_color(color_name)
			
		label_str = self.name
		
		# count waiting highlighted messages
		unread = ''
		num_unread = self.get_nb_unread()
		if num_unread == 1:
			unread = '*'
		elif num_unread > 1:
			unread = '[' + unicode(num_unread) + ']'
		label_str = unread + label_str
		return (label_str, color)

	def get_tab_image(self):
		# Set tab image (always 16x16)
		tab_image = None
		if gajim.gc_connected[self.account][self.room_jid]:
			tab_image = gajim.interface.roster.load_icon('muc_active')
		else:
			tab_image = gajim.interface.roster.load_icon('muc_inactive')
		return tab_image

	def update_ui(self):
		ChatControlBase.update_ui(self)
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			self.draw_contact(nick)

	def _change_style(self, model, path, iter):
		model[iter][C_NICK] = model[iter][C_NICK]

	def change_roster_style(self):
		model = self.list_treeview.get_model()
		model.foreach(self._change_style)

	def repaint_themed_widgets(self):
		ChatControlBase.repaint_themed_widgets(self)
		self.change_roster_style()

	def _update_banner_state_image(self):
		banner_status_img = self.xml.get_widget('gc_banner_status_image')
		images = gajim.interface.roster.jabber_state_images
		if gajim.gc_connected[self.account].has_key(self.room_jid) and \
		gajim.gc_connected[self.account][self.room_jid]:
			image = 'muc_active'
		else:
			image = 'muc_inactive'
		if images.has_key('32') and images['32'].has_key(image):
			muc_icon = images['32'][image]
			if muc_icon.get_storage_type() != gtk.IMAGE_EMPTY:
				pix = muc_icon.get_pixbuf()
				banner_status_img.set_from_pixbuf(pix)
				return
		# we need to scale 16x16 to 32x32
		muc_icon = images['16'][image]
		pix = muc_icon.get_pixbuf()
		scaled_pix = pix.scale_simple(32, 32, gtk.gdk.INTERP_BILINEAR)
		banner_status_img.set_from_pixbuf(scaled_pix)

	def draw_banner_text(self):
		'''Draw the text in the fat line at the top of the window that 
		houses the room jid, subject. 
		'''
		self.name_label.set_ellipsize(pango.ELLIPSIZE_END)
		font_attrs, font_attrs_small = self.get_font_attrs()
		text = '<span %s>%s</span>' % (font_attrs, self.room_jid)
		if self.subject:
			subject = helpers.reduce_chars_newlines(self.subject, max_lines = 2)
			subject = gtkgui_helpers.escape_for_pango_markup(subject)
			text += '\n<span %s>%s</span>' % (font_attrs_small, subject)

			# tooltip must always hold ALL the subject
			self.subject_tooltip.set_tip(self.event_box, self.subject)

		self.name_label.set_markup(text)
	
	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets sensitivity state for configure_room'''
		menu = self.gc_popup_menu
		childs = menu.get_children()
		# hide chat buttons
		childs[5].set_active(self.hide_chat_buttons_current)
		if gajim.gc_connected[self.account][self.room_jid]:
			c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				self.nick)
			if c.affiliation not in ('owner', 'admin'):
				childs[1].set_sensitive(False)
		else:
			# We are not connected to this groupchat, disable unusable menuitems
			childs[1].set_sensitive(False)
			childs[2].set_sensitive(False)
			childs[3].set_sensitive(False)
		return menu

	def on_message(self, nick, msg, tim, has_timestamp = False, xhtml = None):
		if not nick:
			# message from server
			self.print_conversation(msg, tim = tim, xhtml = xhtml)
		else:
			# message from someone
			if has_timestamp:
				self.print_old_conversation(msg, nick, tim, xhtml)
			else:
				self.print_conversation(msg, nick, tim, xhtml)

	def on_private_message(self, nick, msg, tim, xhtml):
		# Do we have a queue?
		fjid = self.room_jid + '/' + nick
		no_queue = len(gajim.events.get_events(self.account, fjid)) == 0

		# We print if window is opened
		pm_control = gajim.interface.msg_win_mgr.get_control(fjid, self.account)
		if pm_control:
			pm_control.print_conversation(msg, tim = tim, xhtml = xhtml)
			return

		event = gajim.events.create_event('pm', (msg, '', 'incoming', tim,
			False, '', None, xhtml))
		gajim.events.add_event(self.account, fjid, event)

		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')
		iter = self.get_contact_iter(nick)
		path = self.list_treeview.get_model().get_path(iter)
		if not autopopup or (not autopopupaway and \
		gajim.connections[self.account].connected > 2):
			if no_queue: # We didn't have a queue: we change icons
				model = self.list_treeview.get_model()
				state_images =\
					gajim.interface.roster.get_appropriate_state_images(
						self.room_jid, icon_name = 'message')
				image = state_images['message']
				model[iter][C_IMG] = image
			self.parent_win.show_title()
			self.parent_win.redraw_tab(self)
		else:
			self._start_private_message(nick)
		# Scroll to line
		self.list_treeview.expand_row(path[0:1], False)
		self.list_treeview.scroll_to_cell(path)
		self.list_treeview.set_cursor(path)

	def get_contact_iter(self, nick):
		model = self.list_treeview.get_model()
		fin = False
		role_iter = model.get_iter_root()
		if not role_iter:
			return None
		while not fin:
			fin2 = False
			user_iter = model.iter_children(role_iter)
			if not user_iter:
				fin2 = True
			while not fin2:
				if nick == model[user_iter][C_NICK].decode('utf-8'):
					return user_iter
				user_iter = model.iter_next(user_iter)
				if not user_iter:
					fin2 = True
			role_iter = model.iter_next(role_iter)
			if not role_iter:
				fin = True
		return None

	gc_count_nicknames_colors = 0
	gc_custom_colors = {}  

	def print_old_conversation(self, text, contact = '', tim = None,
	xhtml = None):
		if isinstance(text, str):
			text = unicode(text, 'utf-8')
		if contact:
			if contact == self.nick: # it's us
				kind = 'outgoing'
			else:
				kind = 'incoming'
		else:
			kind = 'status'
		if gajim.config.get('restored_messages_small'):
			small_attr = ['small']
		else:
			small_attr = []
		ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
			small_attr, small_attr + ['restored_message'],
			small_attr + ['restored_message'], xhtml = xhtml)

	def print_conversation(self, text, contact = '', tim = None, xhtml = None):
		'''Print a line in the conversation:
		if contact is set: it's a message from someone or an info message (contact
		= 'info' in such a case)
		if contact is not set: it's a message from the server or help'''
		if isinstance(text, str):
			text = unicode(text, 'utf-8')
		other_tags_for_name = []
		other_tags_for_text = []
		if contact:
			if contact == self.nick: # it's us
				kind = 'outgoing'
			elif contact == 'info':
				kind = 'info'
				contact = None
			else:
				kind = 'incoming'
				# muc-specific chatstate
				self.parent_win.redraw_tab(self, 'newmsg')
		else:
			kind = 'status'

		if kind == 'incoming': # it's a message NOT from us
			# highlighting and sounds
			(highlight, sound) = self.highlighting_for_message(text, tim)
			if self.gc_custom_colors.has_key(contact):
				other_tags_for_name.append('gc_nickname_color_' + \
					str(self.gc_custom_colors[contact]))
			else:
				self.gc_count_nicknames_colors += 1
				number_of_colors = len(gajim.config.get('gc_nicknames_colors').\
					split(':'))
				if self.gc_count_nicknames_colors == number_of_colors:
					self.gc_count_nicknames_colors = 0				
				self.gc_custom_colors[contact] = \
					self.gc_count_nicknames_colors
				other_tags_for_name.append('gc_nickname_color_' + \
					str(self.gc_count_nicknames_colors))
			if highlight:
				# muc-specific chatstate
				self.parent_win.redraw_tab(self, 'attention')
				other_tags_for_name.append('bold')
				other_tags_for_text.append('marked')
			if sound == 'received':
				helpers.play_sound('muc_message_received')
			elif sound == 'highlight':
				helpers.play_sound('muc_message_highlight')
			if text.startswith('/me ') or text.startswith('/me\n'):
				other_tags_for_text.append('gc_nickname_color_' + \
					str(self.gc_custom_colors[contact]))

			self.check_and_possibly_add_focus_out_line()

		ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
			other_tags_for_name, [], other_tags_for_text, xhtml = xhtml)

	def get_nb_unread(self):
		nb = len(gajim.events.get_events(self.account, self.room_jid,
			['printed_gc_msg']))
		nb += self.get_nb_unread_pm()
		return nb

	def get_nb_unread_pm(self):
		nb = 0
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			nb += len(gajim.events.get_events(self.account, self.room_jid + '/' + \
				nick, ['pm']))
		return nb

	def highlighting_for_message(self, text, tim):
		'''Returns a 2-Tuple. The first says whether or not to highlight the
		text, the second, what sound to play.'''
		highlight, sound = (None, None)

		# Do we play a sound on every muc message?
		if gajim.config.get_per('soundevents', 'muc_message_received', 'enabled'):
			sound = 'received'

		# Are any of the defined highlighting words in the text?
		if self.needs_visual_notification(text):
			highlight = True
			if gajim.config.get_per('soundevents', 'muc_message_highlight',
									'enabled'):
				sound = 'highlight'

		# Is it a history message? Don't want sound-floods when we join.
		if tim != time.localtime():
			sound = None

		return (highlight, sound)

	def check_and_possibly_add_focus_out_line(self):
		'''checks and possibly adds focus out line for room_jid if it needs it
		and does not already have it as last event. If it goes to add this line
		it removes previous line first'''

		win = gajim.interface.msg_win_mgr.get_window(self.room_jid, self.account)
		if self.room_jid == win.get_active_jid() and\
		win.window.get_property('has-toplevel-focus') and\
		self.parent_win.get_active_control() == self:
			# it's the current room and it's the focused window.
			# we have full focus (we are reading it!)
			return

		self.conv_textview.show_focus_out_line()

	def needs_visual_notification(self, text):
		'''checks text to see whether any of the words in (muc_highlight_words
		and nick) appear.'''

		special_words = gajim.config.get('muc_highlight_words').split(';')
		special_words.append(self.nick)
		# Strip empties: ''.split(';') == [''] and would highlight everything.
		# Also lowercase everything for case insensitive compare.
		special_words = [word.lower() for word in special_words if word]
		text = text.lower()

		text_splitted = text.split()
		for word in text_splitted: # get each word of the text
			for special_word in special_words:
				if word.startswith(special_word):
					# get char after the word that highlight us
					char_position = len(special_word)
					refer_to_nick_char = \
						word[char_position:char_position+1]
					if (refer_to_nick_char != ''):
						refer_to_nick_char_code = ord(refer_to_nick_char)
						if ((refer_to_nick_char_code < 65 or \
						refer_to_nick_char_code > 123) or \
						(refer_to_nick_char_code < 97 and \
						refer_to_nick_char_code > 90)):
							return True
						else: 
							# This is A->Z or a->z, we can be sure our nick is the
							# beginning of a real word, do not highlight. Note that we
							# can probably do a better detection of non-punctuation
							# characters
							return False
					else: # Special word == word, no char after in word
						return True 
		return False

	def set_subject(self, subject):
		self.subject = subject
		self.draw_banner_text()

	def got_connected(self):
		gajim.gc_connected[self.account][self.room_jid] = True
		ChatControlBase.got_connected(self)
		# We don't redraw the whole banner here, because only icon change
		self._update_banner_state_image()

	def got_disconnected(self):
		self.list_treeview.get_model().clear()
		nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
		for nick in nick_list:
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				nick)
			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		gajim.gc_connected[self.account][self.room_jid] = False
		ChatControlBase.got_disconnected(self)
		# We don't redraw the whole banner here, because only icon change
		self._update_banner_state_image()

	def draw_roster(self):
		self.list_treeview.get_model().clear()
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
				nick)
			self.add_contact_to_roster(nick, gc_contact.show, gc_contact.role,
						gc_contact.affiliation, gc_contact.status,
						gc_contact.jid)

	def on_send_pm(self, widget = None, model = None, iter = None, nick = None,
	msg = None):
		'''opens a chat window and msg is not None sends private message to a
		contact in a room'''
		if nick is None:
			nick = model[iter][C_NICK].decode('utf-8')
		fjid = gajim.construct_fjid(self.room_jid, nick) # 'fake' jid

		self._start_private_message(nick)
		if msg:
			gajim.interface.msg_win_mgr.get_control(fjid, self.account).\
				send_message(msg)

	def draw_contact(self, nick, selected=False, focus=False):
		iter = self.get_contact_iter(nick)
		if not iter:
			return
		model = self.list_treeview.get_model()
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		state_images = gajim.interface.roster.jabber_state_images['16']
		if len(gajim.events.get_events(self.account, self.room_jid + '/' + nick)):
			image = state_images['message']
		else:
			image = state_images[gc_contact.show]

		name = gtkgui_helpers.escape_for_pango_markup(gc_contact.name)
		status = gc_contact.status
		# add status msg, if not empty, under contact name in the treeview
		if status and gajim.config.get('show_status_msgs_in_roster'):
			status = status.strip()
			if status != '':
				status = helpers.reduce_chars_newlines(status, max_lines = 1)
				# escape markup entities and make them small italic and fg color
				color = gtkgui_helpers._get_fade_color(self.list_treeview,
					selected, focus)
				colorstring = "#%04x%04x%04x" % (color.red, color.green, color.blue)
				name += '\n' '<span size="small" style="italic" foreground="%s">%s</span>'\
					% (colorstring, gtkgui_helpers.escape_for_pango_markup(status))

		model[iter][C_IMG] = image
		model[iter][C_TEXT] = name

	def draw_avatar(self, nick):
		model = self.list_treeview.get_model()
		iter = self.get_contact_iter(nick)
		if not iter:
			return
		if gajim.config.get('show_avatars_in_roster'):
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(self.room_jid + \
				'/' + nick, True)
			if pixbuf in ('ask', None):
				scaled_pixbuf = None
			else:
				scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
		else:
			scaled_pixbuf = None
		model[iter][C_AVATAR] = scaled_pixbuf

	def chg_contact_status(self, nick, show, status, role, affiliation, jid,
	reason, actor, statusCode, new_nick):
		'''When an occupant changes his or her status'''
		if show == 'invisible':
			return

		if not role:
			role = 'visitor'
		if not affiliation:
			affiliation = 'none'

		newly_created = False
		if show in ('offline', 'error'):
			if statusCode == '307':
				if actor is None: # do not print 'kicked by None'
					s = _('%(nick)s has been kicked: %(reason)s') % {
						'nick': nick,
						'reason': reason }
				else:
					s = _('%(nick)s has been kicked by %(who)s: %(reason)s') % {
						'nick': nick,
						'who': actor,
						'reason': reason }
				self.print_conversation(s, 'info')
			elif statusCode == '301':
				if actor is None: # do not print 'banned by None'
					s = _('%(nick)s has been banned: %(reason)s') % {
						'nick': nick,
						'reason': reason }
				else:
					s = _('%(nick)s has been banned by %(who)s: %(reason)s') % {
						'nick': nick,
						'who': actor,
						'reason': reason }
				self.print_conversation(s, 'info')
			elif statusCode == '303': # Someone changed his or her nick
				if nick == self.nick: # We changed our nick
					self.nick = new_nick
					s = _('You are now known as %s') % new_nick
				else:
					s = _('%s is now known as %s') % (nick, new_nick)
					# We add new nick to muc roster here, so we don't see 
					# that "new_nick has joined the room" when he just changed nick.
					# add_contact_to_roster will be called a second time 
					# after that, but that doesn't hurt
					self.add_contact_to_roster(new_nick, show, role, affiliation,
						status, jid)
					# keep nickname color
					if nick in self.gc_custom_colors:
						self.gc_custom_colors[new_nick] = self.gc_custom_colors[nick]
				# rename vcard / avatar
				puny_jid = helpers.sanitize_filename(self.room_jid)
				puny_nick = helpers.sanitize_filename(nick)
				puny_new_nick = helpers.sanitize_filename(new_nick)
				old_path = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
				new_path = os.path.join(gajim.VCARD_PATH, puny_jid, puny_new_nick)
				files = {old_path: new_path}
				path = os.path.join(gajim.AVATAR_PATH, puny_jid)
				# possible extensions
				for ext in ('.png', '.jpeg', '_notif_size_bw.png',
				'_notif_size_colored.png'):
					files[os.path.join(path, puny_nick + ext)] = \
						os.path.join(path, puny_new_nick + ext)
				for old_file in files:
					if os.path.exists(old_file):
						if os.path.exists(files[old_file]):
							# Windows require this
							os.remove(files[old_file])
						os.rename(old_file, files[old_file])
				self.print_conversation(s, 'info')

			if len(gajim.events.get_events(self.account,
			self.room_jid + '/' + nick)) == 0:
				self.remove_contact(nick)
			else:
				c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
				c.show = show
				c.status = status
			if nick == self.nick and statusCode != '303': # We became offline
				self.got_disconnected()
				self.parent_win.redraw_tab(self)
		else:
			iter = self.get_contact_iter(nick)
			if not iter:
				iter = self.add_contact_to_roster(nick, show, role, affiliation,
					status, jid)
				newly_created = True
				if statusCode == '201': # We just created the room
					gajim.connections[self.account].request_gc_config(self.room_jid)
			else:
				actual_role = self.get_role(nick)
				if role != actual_role:
					self.remove_contact(nick)
					self.add_contact_to_roster(nick, show, role,
						affiliation, status, jid)
				else:
					c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
						nick)
					if c.show == show and c.status == status and \
						c.affiliation == affiliation: #no change
						return
					c.show = show
					c.affiliation = affiliation
					c.status = status
					self.draw_contact(nick)

		self.parent_win.redraw_tab(self)
		if (time.time() - self.room_creation) > 30 and \
				nick != self.nick and statusCode != '303':
			st = ''
			print_status = None
			for bookmark in gajim.connections[self.account].bookmarks:
				if bookmark['jid'] == self.room_jid:
					print_status = bookmark.get('print_status', None)
					break
			if not print_status:
				print_status = gajim.config.get('print_status_in_muc')
			nick_jid = nick
			if jid:
				# delete ressource
				simple_jid = gajim.get_jid_without_resource(jid)
				nick_jid += ' (%s)' % simple_jid
			if show == 'offline' and print_status in ('all', 'in_and_out'):
				st = _('%s has left') % nick_jid
				if reason:
					st += ' [%s]' % reason
			else:
				if newly_created and print_status in ('all', 'in_and_out'):
					st = _('%s has joined the group chat') % nick_jid
				elif print_status == 'all':
					st = _('%s is now %s') % (nick_jid, helpers.get_uf_show(show))
			if st:
				if status:
					st += ' (' + status + ')'
				self.print_conversation(st)

	def add_contact_to_roster(self, nick, show, role, affiliation, status,
	jid = ''):
		model = self.list_treeview.get_model()
		role_name = helpers.get_uf_role(role, plural = True)

		resource = ''
		if jid:
			jids = jid.split('/', 1)
			j = jids[0]
			if len(jids) > 1:
				resource = jids[1]
		else:
			j = ''

		name = nick

		role_iter = self.get_role_iter(role)
		if not role_iter:
			role_iter = model.append(None,
				(gajim.interface.roster.jabber_state_images['16']['closed'], role, 
				'role', '%s' % role_name,  None))
		iter = model.append(role_iter, (None, nick, 'contact', name, None))
		if not nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			gc_contact = gajim.contacts.create_gc_contact(room_jid = self.room_jid,
				name = nick, show = show, status = status, role = role,
				affiliation = affiliation, jid = j, resource = resource)
			gajim.contacts.add_gc_contact(self.account, gc_contact)
		self.draw_contact(nick)
		self.draw_avatar(nick)
		# Do not ask avatar to irc rooms as irc transports reply with messages
		server = gajim.get_server_from_jid(self.room_jid)
		if gajim.config.get('ask_avatars_on_startup') and \
		not server.startswith('irc'):
			fjid = self.room_jid + '/' + nick
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(fjid, True)
			if pixbuf == 'ask':
				gajim.connections[self.account].request_vcard(fjid, True)
		if nick == self.nick: # we became online
			self.got_connected()
		self.list_treeview.expand_row((model.get_path(role_iter)), False)
		return iter

	def get_role_iter(self, role):
		model = self.list_treeview.get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			role_name = model[iter][C_NICK].decode('utf-8')
			if role == role_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def remove_contact(self, nick):
		'''Remove a user from the contacts_list'''
		model = self.list_treeview.get_model()
		iter = self.get_contact_iter(nick)
		if not iter:
			return
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		if gc_contact:
			gajim.contacts.remove_gc_contact(self.account, gc_contact)
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)

	def _process_command(self, message):
		if message[0] != '/':
			return False

		# Handle common commands
		if ChatControlBase._process_command(self, message):
			return True

		message = message[1:]
		message_array = message.split(' ', 1)
		command = message_array.pop(0).lower()
		if message_array == ['']:
			message_array = []

		if command == 'me':
			return False # This is not really a command

		if command == 'nick':
			# example: /nick foo
			if len(message_array) and message_array[0] != self.nick:
				nick = message_array[0]
				gajim.connections[self.account].change_gc_nick(self.room_jid, nick)
				self.clear(self.msg_textview)
			else:
				self.get_command_help(command)
			return True
		elif command == 'query' or command == 'chat':
			# Open a chat window to the specified nick
			# example: /query foo
			if len(message_array):
				nick0 = message_array.pop(0)
				if nick0[-1] == ' ':
					nick1 = nick0[:-1]
				else:
					nick1 = nick0
				nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
				for nick in [nick0, nick1]:
					if nick in nicks:
						self.on_send_pm(nick = nick)
						self.clear(self.msg_textview)
						return True
				self.print_conversation(_('Nickname not found: %s') % \
					nick0, 'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'msg':
			# Send a message to a nick. Also opens a private message window.
			# example: /msg foo Hey, what's up?
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account,
					self.room_jid)
				if nick in room_nicks:
					privmsg = ' '.join(message_array)
					self.on_send_pm(nick=nick, msg=privmsg)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick,
						'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'topic':
			# display or change the room topic
			# example: /topic : print topic
			# /topic foo : change topic to foo
			if len(message_array):
				new_topic = message_array.pop(0)
				gajim.connections[self.account].send_gc_subject(self.room_jid,
					new_topic)
			elif self.subject is not '':
				self.print_conversation(self.subject, 'info')
			else:
				self.print_conversation(_('This group chat has no subject'), 'info')
			self.clear(self.msg_textview)
			return True
		elif command == 'invite':
			# invite a user to a room for a reason
			# example: /invite user@example.com reason
			if len(message_array):
				message_array = message_array[0].split()
				invitee = message_array.pop(0)
				if invitee.find('@') >= 0:
					reason = ' '.join(message_array)
					gajim.connections[self.account].send_invite(self.room_jid,
						invitee, reason)
					s = _('Invited %(contact_jid)s to %(room_jid)s.') % {
						'contact_jid': invitee,
						'room_jid': self.room_jid}
					self.print_conversation(s, 'info')
					self.clear(self.msg_textview)
				else:
					#%s is something the user wrote but it is not a jid so we inform
					s = _('%s does not appear to be a valid JID') % invitee
					self.print_conversation(s, 'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'join':
			# example: /join room@conference.example.com/nick
			if len(message_array):
				room_jid = message_array[0]
				if room_jid.find('@') >= 0:
					if room_jid.find('/') >= 0:
						room_jid, nick = room_jid.split('/', 1)
					else:
						nick = ''
					# join_gc window is needed in order to provide for password entry.
					if gajim.interface.instances[self.account].has_key('join_gc'):
						gajim.interface.instances[self.account]['join_gc'].\
							window.present()
					else:
						try:
							gajim.interface.instances[self.account]['join_gc'] =\
								dialogs.JoinGroupchatWindow(self.account,
									room_jid = room_jid, nick = nick)
						except GajimGeneralException:
							pass
					self.clear(self.msg_textview)
				else:
					#%s is something the user wrote but it is not a jid so we inform
					s = _('%s does not appear to be a valid JID') % message_array[0]
					self.print_conversation(s, 'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'leave' or command == 'part' or command == 'close':
			# Leave the room and close the tab or window
			reason = 'offline'
			if len(message_array):
				reason = message_array.pop(0)
			self.parent_win.remove_tab(self, self.parent_win.CLOSE_COMMAND, reason)
			self.clear(self.msg_textview)
			return True
		elif command == 'ban':
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account,
					self.room_jid)
				reason = ' '.join(message_array)
				if nick in room_nicks:
					gc_contact = gajim.contacts.get_gc_contact(self.account,
						self.room_jid, nick)
					nick = gc_contact.jid
				if nick.find('@') >= 0:
					gajim.connections[self.account].gc_set_affiliation(self.room_jid,
						nick, 'outcast', reason)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick,
						'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'kick':
			if len(message_array):
				message_array = message_array[0].split()
				nick = message_array.pop(0)
				room_nicks = gajim.contacts.get_nick_list(self.account,
					self.room_jid)
				reason = ' '.join(message_array)
				if nick in room_nicks:
					gajim.connections[self.account].gc_set_role(self.room_jid, nick,
						'none', reason)
					self.clear(self.msg_textview)
				else:
					self.print_conversation(_('Nickname not found: %s') % nick,
						'info')
			else:
				self.get_command_help(command)
			return True
		elif command == 'names':
			# print the list of participants
			nicklist=''
			i=0
			for contact in self.iter_contact_rows():
				nicklist += '[ %-12.12s ] ' % (contact[C_NICK].decode('utf-8'))
				i=i+1
				if i == 3:
					i=0
					self.print_conversation(nicklist, 'info')
					nicklist=''
			if nicklist:
				self.print_conversation(nicklist, 'info')
			self.clear(self.msg_textview)
			return True
		elif command == 'help':
			if len(message_array):
				subcommand = message_array.pop(0)
				self.get_command_help(subcommand)
			else:
				self.get_command_help(command)
			self.clear(self.msg_textview)
			return True
		elif command == 'say':
			if len(message_array):
				gajim.connections[self.account].send_gc_message(self.room_jid,
										message[4:])
				self.clear(self.msg_textview)
			else:
				self.get_command_help(command)
			return True
		else:
			self.print_conversation(_('No such command: /%s (if you want to send '
				'this, prefix it with /say)') % command, 'info')
			return True

		return False

	def send_message(self, message):
		'''call this function to send our message'''
		if not message:
			return

		if message != '' or message != '\n':
			self.save_sent_message(message)

			if not self._process_command(message):
				# Send the message
				gajim.connections[self.account].send_gc_message(self.room_jid,
					message)
				self.msg_textview.get_buffer().set_text('')
				self.msg_textview.grab_focus()

	def get_command_help(self, command):
		if command == 'help':
			self.print_conversation(_('Commands: %s') % self.muc_cmds, 'info')
		elif command == 'ban':
			s = _('Usage: /%s <nickname|JID> [reason], bans the JID from the group chat.'
				' The nickname of an occupant may be substituted, but not if it '
				'contains "@". If the JID is currently in the group chat, '
				'he/she/it will also be kicked. Does NOT support spaces in '
				'nickname.') % command
			self.print_conversation(s, 'info')
		elif command == 'chat' or command == 'query':
			self.print_conversation(_('Usage: /%s <nickname>, opens a private chat'
				' window with the specified occupant.') % command, 'info')
		elif command == 'clear':
			self.print_conversation(
				_('Usage: /%s, clears the text window.') % command, 'info')
		elif command == 'close' or command == 'leave' or command == 'part':
			self.print_conversation(_('Usage: /%s [reason], closes the current '
				'window or tab, displaying reason if specified.') % command, 'info')
		elif command == 'compact':
			self.print_conversation(_('Usage: /%s, hide the chat buttons.') % \
				command, 'info')
		elif command == 'invite':
			self.print_conversation(_('Usage: /%s <JID> [reason], invites JID to '
				'the current group chat, optionally providing a reason.') % command,
				'info')
		elif command == 'join':
			self.print_conversation(_('Usage: /%s <room>@<server>[/nickname], '
				'offers to join room@server optionally using specified nickname.') \
				% command, 'info')
		elif command == 'kick':
			self.print_conversation(_('Usage: /%s <nickname> [reason], removes '
				'the occupant specified by nickname from the group chat and '
				'optionally displays a reason. Does NOT support spaces in '
				'nickname.') % command, 'info')
		elif command == 'me':
			self.print_conversation(_('Usage: /%s <action>, sends action to the '
				'current group chat. Use third person. (e.g. /%s explodes.)') % \
				(command, command), 'info')
		elif command == 'msg':
			s = _('Usage: /%s <nickname> [message], opens a private message window'
				' and sends message to the occupant specified by nickname.') % \
				command
			self.print_conversation(s, 'info')
		elif command == 'nick':
			s = _('Usage: /%s <nickname>, changes your nickname in current group '
				'chat.')	% command
			self.print_conversation(s, 'info')
		elif command == 'names':
			s = _('Usage: /%s , display the names of group chat occupants.')\
				% command
			self.print_conversation(s, 'info')
		elif command == 'topic':
			self.print_conversation(_('Usage: /%s [topic], displays or updates the'
				' current group chat topic.') % command, 'info')
		elif command == 'say':
			self.print_conversation(_('Usage: /%s <message>, sends a message '
				'without looking for other commands.') % command, 'info')
		else:
			self.print_conversation(_('No help info for /%s') % command, 'info')

	def get_role(self, nick):
		gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
			nick)
		if gc_contact:
			return gc_contact.role
		else:
			return 'visitor'

	def show_change_nick_input_dialog(self, title, prompt, proposed_nick = None):
		'''asks user for new nick and on ok it sets it on room'''
		def on_ok(widget):
			nick = instance.input_entry.get_text().decode('utf-8')
			gajim.connections[self.account].change_gc_nick(self.room_jid, nick)
			self.nick = nick
		instance = dialogs.InputDialog(title, prompt, proposed_nick,
			is_modal = False, ok_handler = on_ok)

	def shutdown(self, status='offline'):
		gajim.connections[self.account].send_gc_status(self.nick, self.room_jid,
							show='offline', status=status)
		# They can already be removed by the destroy function
		if self.room_jid in gajim.contacts.get_gc_list(self.account):
			gajim.contacts.remove_room(self.account, self.room_jid)
			del gajim.gc_connected[self.account][self.room_jid]
		# Save hpaned position
		gajim.config.set('gc-hpaned-position', self.hpaned_position)
		# remove all register handlers on wigets, created by self.xml
		# to prevent circular references among objects
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
			del self.handlers[i]
		# Remove unread events from systray
		gajim.events.remove_events(self.account, self.room_jid)

	def allow_shutdown(self, method):
		'''If check_selection is True, '''
		if method == self.parent_win.CLOSE_ESC:
			model, iter = self.list_treeview.get_selection().get_selected()
			if iter:
				self.list_treeview.get_selection().unselect_all()
				return False
		retval = True
		includes = gajim.config.get('confirm_close_muc_rooms').split(' ')
		excludes = gajim.config.get('noconfirm_close_muc_rooms').split(' ')
		# whether to ask for comfirmation before closing muc
		if (gajim.config.get('confirm_close_muc') or self.room_jid in includes) \
		and gajim.gc_connected[self.account][self.room_jid] and self.room_jid not\
		in excludes:
			pritext = _('Are you sure you want to leave group chat "%s"?')\
				% self.name
			sectext = _('If you close this window, you will be disconnected '
					'from this group chat.')

			dialog = dialogs.ConfirmationDialogCheck(pritext, sectext,
						_('Do _not ask me again'))

			if dialog.get_response() != gtk.RESPONSE_OK:
				retval = False

			if dialog.is_checked(): # user does not want to be asked again
				gajim.config.set('confirm_close_muc', False)

			dialog.destroy()

		return retval

	def set_control_active(self, state):
		self.conv_textview.allow_focus_out_line = True
		self.attention_flag = False
		ChatControlBase.set_control_active(self, state)
		if not state:
			# add the focus-out line to the tab we are leaving
			self.check_and_possibly_add_focus_out_line()
		# Sending active to undo unread state
		self.parent_win.redraw_tab(self, 'active')

	def get_specific_unread(self):
		# returns the number of the number of unread msgs
		# for room_jid & number of unread private msgs with each contact
		# that we have
		nb = 0
		for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
			fjid = self.room_jid + '/' + nick
			nb += len(gajim.events.get_events(self.account, fjid))
			# gc can only have messages as event
		return nb

	def _on_change_subject_menuitem_activate(self, widget):
		instance = dialogs.InputDialog(_('Changing Subject'),
			_('Please specify the new subject:'), self.subject)
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			# Note, we don't update self.subject since we don't know whether it
			# will work yet
			subject = instance.input_entry.get_text().decode('utf-8')
			gajim.connections[self.account].send_gc_subject(self.room_jid, subject)

	def _on_change_nick_menuitem_activate(self, widget):
		title = _('Changing Nickname')
		prompt = _('Please specify the new nickname you want to use:')
		self.show_change_nick_input_dialog(title, prompt, self.nick)

	def _on_configure_room_menuitem_activate(self, widget):
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, self.nick)
		if c.affiliation == 'owner':
			gajim.connections[self.account].request_gc_config(self.room_jid)
		elif c.affiliation == 'admin':
			if not gajim.interface.instances[self.account]['gc_config'].has_key(
				self.room_jid):
				gajim.interface.instances[self.account]['gc_config'][self.room_jid]\
					= config.GroupchatConfigWindow(self.account, self.room_jid)

	def _on_bookmark_room_menuitem_activate(self, widget):
		bm = {
			'name': self.name,
			'jid': self.room_jid,
			'autojoin': '0',
			'password': '',
			'nick': self.nick
		}

		for bookmark in gajim.connections[self.account].bookmarks:
			if bookmark['jid'] == bm['jid']:
				dialogs.ErrorDialog(
					_('Bookmark already set'),
					_('Group Chat "%s" is already in your bookmarks.') % bm['jid'])
				return

		gajim.connections[self.account].bookmarks.append(bm)
		gajim.connections[self.account].store_bookmarks()

		gajim.interface.roster.actions_menu_needs_rebuild = True

		dialogs.InformationDialog(
				_('Bookmark has been added successfully'),
				_('You can manage your bookmarks via Actions menu in your roster.'))

	def handle_message_textview_mykey_press(self, widget, event_keyval,
	event_keymod):
		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_room(). for this singal see message_textview.py

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		message_buffer = widget.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()

		if event.keyval == gtk.keysyms.Tab: # TAB
			cursor_position = message_buffer.get_insert()
			end_iter = message_buffer.get_iter_at_mark(cursor_position)
			text = message_buffer.get_text(start_iter, end_iter, False).decode(
				'utf-8')

			splitted_text = text.split()
			# topic completion
			splitted_text2 = text.split(None, 1)
			if text.startswith('/topic '):
				if len(splitted_text2) == 2 and \
					    self.subject.startswith(splitted_text2[1]) and\
					    len(self.subject) > len(splitted_text2[1]):
					message_buffer.insert_at_cursor(
						self.subject[len(splitted_text2[1]):])
					return True
				elif len(splitted_text2) == 1 and text.startswith('/topic  '):
					message_buffer.delete(start_iter, end_iter)
					message_buffer.insert_at_cursor('/topic '+self.subject)
					return True

			# command completion
			if text.startswith('/') and len(splitted_text) == 1:
				text = splitted_text[0]
				if len(text) == 1: # user wants to cycle all commands
					self.cmd_hits = self.muc_cmds
				else:
					# cycle possible commands depending on what the user typed
					if self.last_key_tabs and len(self.cmd_hits) and \
					self.cmd_hits[0].startswith(text.lstrip('/')):
						self.cmd_hits.append(self.cmd_hits[0])
						self.cmd_hits.pop(0)
					else: # find possible commands
						self.cmd_hits = []
						for cmd in self.muc_cmds:
							if cmd.startswith(text.lstrip('/')):
								self.cmd_hits.append(cmd)
				if len(self.cmd_hits):
					message_buffer.delete(start_iter, end_iter)
					message_buffer.insert_at_cursor('/' + self.cmd_hits[0] + ' ')
					self.last_key_tabs = True
				return True

			# nick completion
			# check if tab is pressed with empty message
			if len(splitted_text): # if there are any words
				begin = splitted_text[-1] # last word we typed
			else:
				begin = ''

			gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
			if len(self.nick_hits) and \
					self.nick_hits[0].startswith(begin.replace(
					gc_refer_to_nick_char, '')) and \
					self.last_key_tabs: # we should cycle
				self.nick_hits.append(self.nick_hits[0])
				self.nick_hits.pop(0)
			else:
				self.nick_hits = [] # clear the hit list
				list_nick = gajim.contacts.get_nick_list(self.account,
									self.room_jid)
				list_nick.remove(self.nick) # Skip self
				for nick in list_nick:
					if nick.lower().startswith(begin.lower()):
						# the word is the begining of a nick
						self.nick_hits.append(nick)
			if len(self.nick_hits):
				if len(splitted_text)  < 2: # This is the 1st word of the line or no word
					add = gc_refer_to_nick_char + ' '
				else:
					add = ' '
				start_iter = end_iter.copy()
				if self.last_key_tabs and begin.endswith(', '):
					# have to accomodate for the added space from last
					# completion
					start_iter.backward_chars(len(begin) + 2)
				elif self.last_key_tabs:
					# have to accomodate for the added space from last
					# completion
					start_iter.backward_chars(len(begin) + 1)
				else:
					start_iter.backward_chars(len(begin))

				message_buffer.delete(start_iter, end_iter)
				message_buffer.insert_at_cursor(self.nick_hits[0] + add)
				self.last_key_tabs = True
				return True
			self.last_key_tabs = False

	def on_list_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			selection = widget.get_selection()
			model, iter = selection.get_selected()
			if iter:
				widget.get_selection().unselect_all()
				return True

	def on_list_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.roster.jabber_state_images['16']['opened']
		model[iter][C_IMG] = image

	def on_list_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed: change the icon of the arrow'''
		model = widget.get_model()
		image = gajim.interface.roster.jabber_state_images['16']['closed']
		model[iter][C_IMG] = image

	def kick(self, widget, nick):
		'''kick a user'''
		# ask for reason
		instance = dialogs.InputDialog(_('Kicking %s') % nick,
					_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text().decode('utf-8')
		else:
			return # stop kicking procedure
		gajim.connections[self.account].gc_set_role(self.room_jid, nick, 'none',
								reason)

	def mk_menu(self, event, iter):
		'''Make contact's popup menu'''
		model = self.list_treeview.get_model()
		nick = model[iter][C_NICK].decode('utf-8')
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		jid = c.jid
		target_affiliation = c.affiliation
		target_role = c.role

		# looking for user's affiliation and role
		user_nick = self.nick
		user_affiliation = gajim.contacts.get_gc_contact(self.account,
			self.room_jid, user_nick).affiliation
		user_role = self.get_role(user_nick)

		# making menu from glade
		xml = gtkgui_helpers.get_glade('gc_occupants_menu.glade')

		# these conditions were taken from JEP 0045
		item = xml.get_widget('kick_menuitem')
		if user_role != 'moderator' or \
		(user_affiliation == 'admin' and target_affiliation == 'owner') or \
		(user_affiliation == 'member' and target_affiliation in ('admin',
		'owner')) or (user_affiliation == 'none' and target_affiliation != \
		'none'):
			item.set_sensitive(False)
		id = item.connect('activate', self.kick, nick)
		self.handlers[id] = item

		item = xml.get_widget('voice_checkmenuitem')
		item.set_active(target_role != 'visitor')
		if user_role != 'moderator' or \
		user_affiliation == 'none' or \
		(user_affiliation=='member' and target_affiliation!='none') or \
		target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		id = item.connect('activate', self.on_voice_checkmenuitem_activate, 
			nick)
		self.handlers[id] = item

		item = xml.get_widget('moderator_checkmenuitem')
		item.set_active(target_role == 'moderator')
		if not user_affiliation in ('admin', 'owner') or \
		target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		id = item.connect('activate', self.on_moderator_checkmenuitem_activate,
					nick)
		self.handlers[id] = item
	
		item = xml.get_widget('ban_menuitem')
		if not user_affiliation in ('admin', 'owner') or \
		(target_affiliation in ('admin', 'owner') and\
		user_affiliation != 'owner'):
			item.set_sensitive(False)
		id = item.connect('activate', self.ban, jid)
		self.handlers[id] = item

		item = xml.get_widget('member_checkmenuitem')
		item.set_active(target_affiliation != 'none')
		if not user_affiliation in ('admin', 'owner') or \
		(user_affiliation != 'owner' and target_affiliation in ('admin','owner')):
			item.set_sensitive(False)
		id = item.connect('activate', self.on_member_checkmenuitem_activate, 
					jid)
		self.handlers[id] = item
	
		item = xml.get_widget('admin_checkmenuitem')
		item.set_active(target_affiliation in ('admin', 'owner'))
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		id = item.connect('activate', self.on_admin_checkmenuitem_activate, jid)
		self.handlers[id] = item

		item = xml.get_widget('owner_checkmenuitem')
		item.set_active(target_affiliation == 'owner')
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		id = item.connect('activate', self.on_owner_checkmenuitem_activate, jid)
		self.handlers[id] = item

		item = xml.get_widget('information_menuitem')
		id = item.connect('activate', self.on_info, nick)
		self.handlers[id] = item

		item = xml.get_widget('history_menuitem')
		id = item.connect('activate', self.on_history, nick)
		self.handlers[id] = item

		item = xml.get_widget('add_to_roster_menuitem')
		if not jid:
			item.set_sensitive(False)
		id = item.connect('activate', self.on_add_to_roster, jid)
		self.handlers[id] = item

		item = xml.get_widget('send_private_message_menuitem')
		id = item.connect('activate', self.on_send_pm, model, iter)
		self.handlers[id] = item

		# show the popup now!
		menu = xml.get_widget('gc_occupants_menu')
		menu.show_all()
		menu.popup(None, None, None, event.button, event.time)

	def _start_private_message(self, nick):
		gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		c = gajim.contacts.contact_from_gc_contact(gc_c)
		nick_jid = c.jid

		win = gajim.interface.msg_win_mgr.get_window(nick_jid, self.account)
		if not win:
			gajim.interface.roster.new_chat(c, self.account, private_chat = True)
			win = gajim.interface.msg_win_mgr.get_window(nick_jid, self.account)
		win.set_active_tab(nick_jid, self.account)
		win.window.present()

	def on_list_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the chat window'''
		model = widget.get_model()
		if len(path) == 1: # It's a group
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)
		else: # We want to send a private message
			nick = model[path][C_NICK].decode('utf-8')
			self._start_private_message(nick)

	def on_list_treeview_button_press_event(self, widget, event):
		'''popup user's group's or agent menu'''
		if event.button == 3: # right click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				self.mk_menu(event, iter)
			return True

		elif event.button == 2: # middle click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				nick = model[iter][C_NICK].decode('utf-8')
				self._start_private_message(nick)
			return True

		elif event.button == 1: # left click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return

			model = widget.get_model()
			iter = model.get_iter(path)
			nick = model[iter][C_NICK].decode('utf-8')
			if not nick in gajim.contacts.get_nick_list(self.account,
			self.room_jid):
				#it's a group
				col = widget.get_column(0)
				avatar_cell = col.get_cell_renderers()[0]
				(pos, avatar_size) = col.cell_get_position(avatar_cell)
				status_cell = col.get_cell_renderers()[1]
				(pos, status_size) = col.cell_get_position(status_cell)
				if x > avatar_size and x < avatar_size + status_size:
					if (widget.row_expanded(path)):
						widget.collapse_row(path)
					else:
						widget.expand_row(path, False)
			elif event.state & gtk.gdk.SHIFT_MASK:
				self.append_nick_in_msg_textview(self.msg_textview, nick)
				self.msg_textview.grab_focus()
				return True

	def append_nick_in_msg_textview(self, widget, nick):
		message_buffer = self.msg_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		cursor_position = message_buffer.get_insert()
		end_iter = message_buffer.get_iter_at_mark(cursor_position)
		text = message_buffer.get_text(start_iter, end_iter, False)
		start = ''
		if text: # Cursor is not at first position
			if not text[-1] in (' ', '\n', '\t'):
				start = ' '
			add = ' '
		else:
			gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
			add = gc_refer_to_nick_char + ' '
		message_buffer.insert_at_cursor(start + nick + add)

	def on_list_treeview_motion_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter = None
			try:
				iter = model.get_iter(row)
			except:
				self.tooltip.hide_tooltip()
				return
			typ = model[iter][C_TYPE].decode('utf-8')
			if typ == 'contact':
				account = self.account

				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					nick = model[iter][C_NICK].decode('utf-8')
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, gajim.contacts.get_gc_contact(account,
						self.room_jid, nick))

	def on_list_treeview_leave_notify_event(self, widget, event):
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def show_tooltip(self, contact):
		pointer = self.list_treeview.get_pointer()
		props = self.list_treeview.get_path_at_pos(pointer[0], pointer[1])
		# check if the current pointer is at the same path
		# as it was before setting the timeout
		if props and self.tooltip.id == props[0]:
			rect = self.list_treeview.get_cell_area(props[0],props[1])
			position = self.list_treeview.window.get_origin()
			self.tooltip.show_tooltip(contact, rect.height, 
											position[1] + rect.y)
		else:
			self.tooltip.hide_tooltip()


	def grant_voice(self, widget, nick):
		'''grant voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'participant')

	def revoke_voice(self, widget, nick):
		'''revoke voice privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'visitor')

	def grant_moderator(self, widget, nick):
		'''grant moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'moderator')

	def revoke_moderator(self, widget, nick):
		'''revoke moderator privilege to a user'''
		gajim.connections[self.account].gc_set_role(self.room_jid, nick,
			'participant')

	def ban(self, widget, jid):
		'''ban a user'''
		# to ban we know the real jid. so jid is not fakejid
		nick = gajim.get_nick_from_jid(jid)
		# ask for reason
		instance = dialogs.InputDialog(_('Banning %s') % nick,
			_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text().decode('utf-8')
		else:
			return # stop banning procedure
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'outcast', reason)

	def grant_membership(self, widget, jid):
		'''grant membership privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'member')

	def revoke_membership(self, widget, jid):
		'''revoke membership privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'none')

	def grant_admin(self, widget, jid):
		'''grant administrative privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'admin')

	def revoke_admin(self, widget, jid):
		'''revoke administrative privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
			'member')

	def grant_owner(self, widget, jid):
		'''grant owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'owner')

	def revoke_owner(self, widget, jid):
		'''revoke owner privilege to a user'''
		gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid, 'admin')

	def on_info(self, widget, nick):
		'''Call vcard_information_window class to display user's information'''
		c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
		c2 = gajim.contacts.contact_from_gc_contact(c)
		if gajim.interface.instances[self.account]['infos'].has_key(c2.jid):
			gajim.interface.instances[self.account]['infos'][c2.jid].window.\
				present()
		else:
			gajim.interface.instances[self.account]['infos'][c2.jid] = \
				vcard.VcardWindow(c2, self.account, c)

	def on_history(self, widget, nick):
		jid = gajim.construct_fjid(self.room_jid, nick)
		self._on_history_menuitem_activate(widget = widget, jid = jid)

	def on_add_to_roster(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def on_voice_checkmenuitem_activate(self, widget, nick):
		if widget.get_active():
			self.grant_voice(widget, nick)
		else:
			self.revoke_voice(widget, nick)

	def on_moderator_checkmenuitem_activate(self, widget, nick):
		if widget.get_active():
			self.grant_moderator(widget, nick)
		else:
			self.revoke_moderator(widget, nick)

	def on_member_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_membership(widget, jid)
		else:
			self.revoke_membership(widget, jid)

	def on_admin_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_admin(widget, jid)
		else:
			self.revoke_admin(widget, jid)

	def on_owner_checkmenuitem_activate(self, widget, jid):
		if widget.get_active():
			self.grant_owner(widget, jid)
		else:
			self.revoke_owner(widget, jid)
