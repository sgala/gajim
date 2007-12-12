##	config.py
##
## Copyright (C) 2003-2007 Yann Leboulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2003-2005 Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
## Copyright (C) 2007 Stephan Erb <steve-e@h3c.de> 
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
import os, sys
import common.config
import common.sleepy
from common.i18n import Q_

import gtkgui_helpers
import dialogs
import cell_renderer_image
import message_control
import chat_control
import dataforms_widget

try:
	import gtkspell
	HAS_GTK_SPELL = True
except:
	HAS_GTK_SPELL = False

from common import helpers
from common import gajim
from common import connection
from common import passwords
from common import zeroconf
from common import dbus_support
from common import dataforms
from common import pep

from common.exceptions import GajimGeneralException

#---------- PreferencesWindow class -------------#
class PreferencesWindow:
	'''Class for Preferences window'''

	def on_preferences_window_destroy(self, widget):
		'''close window'''
		del gajim.interface.instances['preferences']

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self):
		'''Initialize Preferences window'''
		self.xml = gtkgui_helpers.get_glade('preferences_window.glade')
		self.window = self.xml.get_widget('preferences_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.notebook = self.xml.get_widget('preferences_notebook')
		self.treat_incoming_messages_combobox =\
			self.xml.get_widget('treat_incoming_messages_combobox')
		self.one_window_type_combobox =\
			self.xml.get_widget('one_window_type_combobox')
		self.iconset_combobox = self.xml.get_widget('iconset_combobox')
		self.notify_on_signin_checkbutton = self.xml.get_widget(
			'notify_on_signin_checkbutton')
		self.notify_on_signout_checkbutton = self.xml.get_widget(
			'notify_on_signout_checkbutton')
		self.auto_popup_away_checkbutton = self.xml.get_widget(
			'auto_popup_away_checkbutton')
		self.auto_away_checkbutton = self.xml.get_widget('auto_away_checkbutton')
		self.auto_away_time_spinbutton = self.xml.get_widget(
			'auto_away_time_spinbutton')
		self.auto_away_message_entry = self.xml.get_widget(
			'auto_away_message_entry')
		self.auto_xa_checkbutton = self.xml.get_widget('auto_xa_checkbutton')
		self.auto_xa_time_spinbutton = self.xml.get_widget(
			'auto_xa_time_spinbutton')
		self.auto_xa_message_entry = self.xml.get_widget('auto_xa_message_entry')

		w = self.xml.get_widget('anc_hbox')

		### General tab ###
		# Display avatars in roster
		st = gajim.config.get('show_avatars_in_roster')
		self.xml.get_widget('show_avatars_in_roster_checkbutton').set_active(st)

		# Display status msg under contact name in roster
		st = gajim.config.get('show_status_msgs_in_roster')
		self.xml.get_widget('show_status_msgs_in_roster_checkbutton').set_active(
			st)

		# Sort contacts by show
		st = gajim.config.get('sort_by_show')
		self.xml.get_widget('sort_by_show_checkbutton').set_active(st)

		# emoticons
		emoticons_combobox = self.xml.get_widget('emoticons_combobox')
		emoticons_list = os.listdir(os.path.join(gajim.DATA_DIR, 'emoticons'))
		# user themes
		if os.path.isdir(gajim.MY_EMOTS_PATH):
			emoticons_list += os.listdir(gajim.MY_EMOTS_PATH)
		renderer_text = gtk.CellRendererText()
		emoticons_combobox.pack_start(renderer_text, True)
		emoticons_combobox.add_attribute(renderer_text, 'text', 0)
		model = gtk.ListStore(str)
		emoticons_combobox.set_model(model)
		l = []
		for dir in emoticons_list:
			if not os.path.isdir(os.path.join(gajim.DATA_DIR, 'emoticons', dir)) \
			and not os.path.isdir(os.path.join(gajim.MY_EMOTS_PATH, dir)) :
				continue
			if dir != '.svn':
				l.append(dir)
		l.append(_('Disabled'))
		for i in xrange(len(l)):
			model.append([l[i]])
			if gajim.config.get('emoticons_theme') == l[i]:
				emoticons_combobox.set_active(i)
		if not gajim.config.get('emoticons_theme'):
			emoticons_combobox.set_active(len(l)-1)

		# Set default for treat incoming messages
		choices = common.config.opt_treat_incoming_messages
		type = gajim.config.get('treat_incoming_messages')
		if type in choices:
			self.treat_incoming_messages_combobox.set_active(choices.index(type))
		else:
			self.treat_incoming_messages_combobox.set_active(0)

		# Set default for single window type
		choices = common.config.opt_one_window_types
		type = gajim.config.get('one_message_window')
		if type in choices:
			self.one_window_type_combobox.set_active(choices.index(type))
		else:
			self.one_window_type_combobox.set_active(0)

		# Compact View
		st = gajim.config.get('compact_view')
		self.xml.get_widget('compact_view_checkbutton').set_active(st)

		# Ignore XHTML
		st = gajim.config.get('ignore_incoming_xhtml')
		self.xml.get_widget('xhtml_checkbutton').set_active(st)

		# use speller
		if HAS_GTK_SPELL:
			st = gajim.config.get('use_speller')
			self.xml.get_widget('speller_checkbutton').set_active(st)
		else:
			self.xml.get_widget('speller_checkbutton').set_sensitive(False)

		# Themes
		theme_combobox = self.xml.get_widget('theme_combobox')
		cell = gtk.CellRendererText()
		theme_combobox.pack_start(cell, True)
		theme_combobox.add_attribute(cell, 'text', 0)
		self.update_theme_list()

		# iconset
		iconsets_list = os.listdir(os.path.join(gajim.DATA_DIR, 'iconsets'))
		if os.path.isdir(gajim.MY_ICONSETS_PATH):
			iconsets_list += os.listdir(gajim.MY_ICONSETS_PATH) 
		# new model, image in 0, string in 1
		model = gtk.ListStore(gtk.Image, str)
		renderer_image = cell_renderer_image.CellRendererImage(0, 0)
		renderer_text = gtk.CellRendererText()
		renderer_text.set_property('xpad', 5)
		self.iconset_combobox.pack_start(renderer_image, expand = False)
		self.iconset_combobox.pack_start(renderer_text, expand = True)
		self.iconset_combobox.set_attributes(renderer_text, text = 1)
		self.iconset_combobox.add_attribute(renderer_image, 'image', 0)
		self.iconset_combobox.set_model(model)
		l = []
		for dir in iconsets_list:
			if not os.path.isdir(os.path.join(gajim.DATA_DIR, 'iconsets', dir)) \
			and not os.path.isdir(os.path.join(gajim.MY_ICONSETS_PATH, dir)):
				continue
			if dir != '.svn' and dir != 'transports':
				l.append(dir)
		if l.count == 0:
			l.append(' ')
		for i in xrange(len(l)):
			preview = gtk.Image()
			files = []
			files.append(os.path.join(helpers.get_iconset_path(l[i]), '16x16',
				'online.png'))
			files.append(os.path.join(helpers.get_iconset_path(l[i]), '16x16',
				'online.gif'))
			for file in files:
				if os.path.exists(file):
					preview.set_from_file(file)
			model.append([preview, l[i]])
			if gajim.config.get('iconset') == l[i]:
				self.iconset_combobox.set_active(i)

		# Use transports iconsets
		st = gajim.config.get('use_transports_iconsets')
		self.xml.get_widget('transports_iconsets_checkbutton').set_active(st)

		### Privacy tab ###
		# outgoing send chat state notifications
		st = gajim.config.get('outgoing_chat_state_notifications')
		combo = self.xml.get_widget('outgoing_chat_states_combobox')
		if st == 'all':
			combo.set_active(0)
		elif st == 'composing_only':
			combo.set_active(1)
		else: # disabled
			combo.set_active(2)

		# displayed send chat state notifications
		st = gajim.config.get('displayed_chat_state_notifications')
		combo = self.xml.get_widget('displayed_chat_states_combobox')
		if st == 'all':
			combo.set_active(0)
		elif st == 'composing_only':
			combo.set_active(1)
		else: # disabled
			combo.set_active(2)

		# Ignore messages from unknown contacts
		self.xml.get_widget('ignore_events_from_unknown_contacts_checkbutton').\
			set_active(gajim.config.get('ignore_unknown_contacts'))

		### Events tab ###
		# On new event
		on_event_combobox = self.xml.get_widget('on_event_combobox')
		if gajim.config.get('autopopup'):
			on_event_combobox.set_active(0)
		elif gajim.config.get('notify_on_new_message'):
			on_event_combobox.set_active(1)
		else:
			on_event_combobox.set_active(2)

		# notify on online statuses
		st = gajim.config.get('notify_on_signin')
		self.notify_on_signin_checkbutton.set_active(st)

		# notify on offline statuses
		st = gajim.config.get('notify_on_signout')
		self.notify_on_signout_checkbutton.set_active(st)

		# autopopupaway
		st = gajim.config.get('autopopupaway')
		self.auto_popup_away_checkbutton.set_active(st)

		# sounds
		if ((os.name == 'nt') or (sys.platform == 'darwin')):
			# if windows, player must not become visible on show_all
			soundplayer_hbox = self.xml.get_widget('soundplayer_hbox')
			soundplayer_hbox.set_no_show_all(True)
		if gajim.config.get('sounds_on'):
			self.xml.get_widget('play_sounds_checkbutton').set_active(True)
		else:
			self.xml.get_widget('soundplayer_hbox').set_sensitive(False)
			self.xml.get_widget('sounds_scrolledwindow').set_sensitive(False)
			self.xml.get_widget('browse_sounds_hbox').set_sensitive(False)

		# sound player
		player = gajim.config.get('soundplayer')
		self.xml.get_widget('soundplayer_entry').set_text(player)
		if player == '': # only on first time Gajim starts
			commands = ('aplay', 'play', 'esdplay', 'artsplay')
			for command in commands:
				if helpers.is_in_path(command):
					if command == 'aplay':
						command += ' -q'
					self.xml.get_widget('soundplayer_entry').set_text(command)
					gajim.config.set('soundplayer', command)
					break

		# sounds treeview
		self.sound_tree = self.xml.get_widget('sounds_treeview')
		
		# active, event ui name, path to sound file, event_config_name
		model = gtk.ListStore(bool, str, str, str)
		self.sound_tree.set_model(model)

		col = gtk.TreeViewColumn(_('Active'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererToggle()
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.sound_toggled_cb)
		col.pack_start(renderer)
		col.set_attributes(renderer, active = 0)

		col = gtk.TreeViewColumn(_('Event'))
		self.sound_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 1)

		self.fill_sound_treeview()

		# Autoaway
		st = gajim.config.get('autoaway')
		self.auto_away_checkbutton.set_active(st)

		# Autoawaytime
		st = gajim.config.get('autoawaytime')
		self.auto_away_time_spinbutton.set_value(st)
		self.auto_away_time_spinbutton.set_sensitive(gajim.config.get('autoaway'))

		# autoaway message
		st = gajim.config.get('autoaway_message')
		self.auto_away_message_entry.set_text(st)
		self.auto_away_message_entry.set_sensitive(gajim.config.get('autoaway'))

		# Autoxa
		st = gajim.config.get('autoxa')
		self.auto_xa_checkbutton.set_active(st)

		# Autoxatime
		st = gajim.config.get('autoxatime')
		self.auto_xa_time_spinbutton.set_value(st)
		self.auto_xa_time_spinbutton.set_sensitive(gajim.config.get('autoxa'))

		# autoxa message
		st = gajim.config.get('autoxa_message')
		self.auto_xa_message_entry.set_text(st)
		self.auto_xa_message_entry.set_sensitive(gajim.config.get('autoxa'))

		from common import sleepy
		if not sleepy.SUPPORTED:
			self.xml.get_widget('autoaway_table').set_sensitive(False)

		# ask_status when online / offline
		st = gajim.config.get('ask_online_status')
		self.xml.get_widget('prompt_online_status_message_checkbutton').\
			set_active(st)
		st = gajim.config.get('ask_offline_status')
		self.xml.get_widget('prompt_offline_status_message_checkbutton').\
			set_active(st)

		# Default Status messages
		self.default_msg_tree = self.xml.get_widget('default_msg_treeview')
		# (status, translated_status, message, enabled)
		model = gtk.ListStore(str, str, str, bool)
		self.default_msg_tree.set_model(model)
		col = gtk.TreeViewColumn('Status')
		self.default_msg_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, False)
		col.set_attributes(renderer, text = 1)
		col = gtk.TreeViewColumn('Message')
		self.default_msg_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 2)
		renderer.connect('edited', self.on_default_msg_cell_edited)
		renderer.set_property('editable', True)
		col = gtk.TreeViewColumn('Enabled')
		self.default_msg_tree.append_column(col)
		renderer = gtk.CellRendererToggle()
		col.pack_start(renderer, False)
		col.set_attributes(renderer, active = 3)
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.default_msg_toggled_cb)
		self.fill_default_msg_treeview()

		# Status messages
		self.msg_tree = self.xml.get_widget('msg_treeview')
		model = gtk.ListStore(str, str)
		self.msg_tree.set_model(model)
		col = gtk.TreeViewColumn('name')
		self.msg_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		renderer.connect('edited', self.on_msg_cell_edited)
		renderer.set_property('editable', True)
		self.fill_msg_treeview()
		buf = self.xml.get_widget('msg_textview').get_buffer()
		buf.connect('changed', self.on_msg_textview_changed)

		# open links with
		if os.name == 'nt':
			applications_frame = self.xml.get_widget('applications_frame')
			applications_frame.set_no_show_all(True)
			applications_frame.hide()
		else:
			self.applications_combobox = self.xml.get_widget(
				'applications_combobox')
			self.xml.get_widget('custom_apps_frame').hide()
			self.xml.get_widget('custom_apps_frame').set_no_show_all(True)

			if sys.platform == 'darwin':
				self.applications_combobox.remove_text(4)
				self.applications_combobox.remove_text(3)
				self.applications_combobox.remove_text(2)
				self.applications_combobox.remove_text(1)
				self.applications_combobox.append_text(
					_('Always use OS/X default applications'))
				self.applications_combobox.append_text(_('Custom'))

			if gajim.config.get('autodetect_browser_mailer'):
				self.applications_combobox.set_active(0)
			# else autodetect_browser_mailer is False.
			# so user has 'Always Use GNOME/KDE/Xfce' or Custom
			elif gajim.config.get('openwith') == 'gnome-open':
				self.applications_combobox.set_active(1)
			elif gajim.config.get('openwith') == 'kfmclient exec':
				self.applications_combobox.set_active(2)
			elif gajim.config.get('openwith') == 'exo-open':
				self.applications_combobox.set_active(3)
			elif ((sys.platform == 'darwin') and
				  (gajim.config.get('openwith') == 'open')):
				self.applications_combobox.set_active(1)
			elif gajim.config.get('openwith') == 'custom':
				if sys.platform == 'darwin':
					self.applications_combobox.set_active(2)
				else:
					self.applications_combobox.set_active(4)
				self.xml.get_widget('custom_apps_frame').show()
				
			self.xml.get_widget('custom_browser_entry').set_text(
				gajim.config.get('custombrowser'))
			self.xml.get_widget('custom_mail_client_entry').set_text(
				gajim.config.get('custommailapp'))
			self.xml.get_widget('custom_file_manager_entry').set_text(
				gajim.config.get('custom_file_manager'))

		# log status changes of contacts
		st = gajim.config.get('log_contact_status_changes')
		self.xml.get_widget('log_show_changes_checkbutton').set_active(st)

		# send os info
		st = gajim.config.get('send_os_info')
		self.xml.get_widget('send_os_info_checkbutton').set_active(st)

		# send os info
		st = gajim.config.get('check_if_gajim_is_default')
		self.xml.get_widget('check_default_client_checkbutton').set_active(st)

		# set status msg from currently playing music track
		widget = self.xml.get_widget(
			'set_status_msg_from_current_music_track_checkbutton')
		if os.name == 'nt':
			widget.set_no_show_all(True)
			widget.hide()
		elif dbus_support.supported:
			st = gajim.config.get('set_status_msg_from_current_music_track')
			widget.set_active(st)
		else:
			widget.set_sensitive(False)

		# PEP
		st = gajim.config.get('publish_mood')
		self.xml.get_widget('publish_mood_checkbutton').set_active(st)

		st = gajim.config.get('publish_activity')
		self.xml.get_widget('publish_activity_checkbutton').set_active(st)

		st = gajim.config.get('publish_tune')
		self.xml.get_widget('publish_tune_checkbutton').set_active(st)

		st = gajim.config.get('subscribe_mood')
		self.xml.get_widget('subscribe_mood_checkbutton').set_active(st)

		st = gajim.config.get('subscribe_activity')
		self.xml.get_widget('subscribe_activity_checkbutton').set_active(st)

		st = gajim.config.get('subscribe_tune')
		self.xml.get_widget('subscribe_tune_checkbutton').set_active(st)

		# Notify user of new gmail e-mail messages,
		# only show checkbox if user has a gtalk account
		frame_gmail = self.xml.get_widget('frame_gmail')
		notify_gmail_checkbutton = self.xml.get_widget('notify_gmail_checkbutton')
		notify_gmail_extra_checkbutton = self.xml.get_widget(
			'notify_gmail_extra_checkbutton')

		for account in gajim.config.get_per('accounts'):
			jid = gajim.get_jid_from_account(account)
			if gajim.get_server_from_jid(jid) in gajim.gmail_domains:
				frame_gmail.show_all()
				st = gajim.config.get('notify_on_new_gmail_email')
				notify_gmail_checkbutton.set_active(st)
				st = gajim.config.get('notify_on_new_gmail_email_extra')
				notify_gmail_extra_checkbutton.set_active(st)
				break
		else:
			frame_gmail.hide()

		# Color for incoming messages
		colSt = gajim.config.get('inmsgcolor')
		self.xml.get_widget('incoming_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))

		# Color for outgoing messages
		colSt = gajim.config.get('outmsgcolor')
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))

		# Color for status messages
		colSt = gajim.config.get('statusmsgcolor')
		self.xml.get_widget('status_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))

		# Color for hyperlinks
		colSt = gajim.config.get('urlmsgcolor')
		self.xml.get_widget('url_msg_colorbutton').set_color(
			gtk.gdk.color_parse(colSt))

		# Font for messages
		font = gajim.config.get('conversation_font')
		# try to set default font for the current desktop env
		fontbutton = self.xml.get_widget('conversation_fontbutton')
		if font == '':
			fontbutton.set_sensitive(False)
			self.xml.get_widget('default_chat_font').set_active(True)
		else:
			fontbutton.set_font_name(font)

		self.xml.signal_autoconnect(self)

		self.sound_tree.get_model().connect('row-changed',
					self.on_sounds_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-changed',
					self.on_msg_treemodel_row_changed)
		self.msg_tree.get_model().connect('row-deleted',
					self.on_msg_treemodel_row_deleted)
		self.default_msg_tree.get_model().connect('row-changed',
					self.on_default_msg_treemodel_row_changed)
		
		self.theme_preferences = None
		
		self.notebook.set_current_page(0)
		if not gajim.config.get('use_pep'):
			self.notebook.remove_page(5)
		self.window.show_all()
		gtkgui_helpers.possibly_move_window_in_current_desktop(self.window)

	def on_preferences_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.hide()

	def on_checkbutton_toggled(self, widget, config_name,
		change_sensitivity_widgets = None):
		gajim.config.set(config_name, widget.get_active())
		if change_sensitivity_widgets:
			for w in change_sensitivity_widgets:
				w.set_sensitive(widget.get_active())
		gajim.interface.save_config()

	def on_publish_mood_checkbutton_toggled(self, widget):
		if widget.get_active() == False:
			for account in gajim.connections:
				if gajim.connections[account].pep_supported:
					pep.user_send_mood(account, '')
		self.on_checkbutton_toggled(widget, 'publish_mood')

	def on_publish_activity_checkbutton_toggled(self, widget):
		if widget.get_active() == False:
			for account in gajim.connections:
				if gajim.connections[account].pep_supported:
					pep.user_send_activity(account, '')
		self.on_checkbutton_toggled(widget, 'publish_activity')

	def on_publish_tune_checkbutton_toggled(self, widget):
		if widget.get_active() == False:
			for account in gajim.connections:
				if gajim.connections[account].pep_supported:
					pep.user_send_tune(account, '')
		self.on_checkbutton_toggled(widget, 'publish_tune')
		gajim.interface.roster.enable_syncing_status_msg_from_current_music_track(
			widget.get_active())

	def on_subscribe_mood_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'subscribe_mood')

	def on_subscribe_activity_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'subscribe_activity')

	def on_subscribe_tune_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'subscribe_tune')

	def on_save_position_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'saveposition')

	def on_sort_by_show_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sort_by_show')
		gajim.interface.roster.draw_roster()

	def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
		gajim.interface.roster.draw_roster()
		# Redraw connected groupchats (in an ugly way)
		for account in gajim.connections:
			if gajim.connections[account].connected:
				for gc_control in gajim.interface.msg_win_mgr.get_controls(
					message_control.TYPE_GC) + \
					gajim.interface.minimized_controls[account].values():
						gc_control.draw_roster()

	def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
		gajim.interface.roster.draw_roster()
		for ctl in gajim.interface.msg_win_mgr.controls():
			if ctl.type_id == message_control.TYPE_GC:
				ctl.update_ui()

	def on_sort_by_show_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sort_by_show')
		gajim.interface.roster.draw_roster()

	def on_emoticons_combobox_changed(self, widget):
		active = widget.get_active()
		model = widget.get_model()
		emot_theme = model[active][0].decode('utf-8')
		if emot_theme == _('Disabled'):
			gajim.config.set('emoticons_theme', '')
		else:
			gajim.config.set('emoticons_theme', emot_theme)

		gajim.interface.init_emoticons(need_reload = True)
		gajim.interface.make_regexps()
		self.toggle_emoticons()

	def toggle_emoticons(self):
		'''Update emoticons state in Opened Chat Windows'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.toggle_emoticons()

	def on_treat_incoming_messages_combobox_changed(self, widget):
		active = widget.get_active()
		config_type = common.config.opt_treat_incoming_messages[active]
		gajim.config.set('treat_incoming_messages', config_type)

	def on_one_window_type_combo_changed(self, widget):
		active = widget.get_active()
		config_type = common.config.opt_one_window_types[active]
		gajim.config.set('one_message_window', config_type)
		gajim.interface.save_config()
		gajim.interface.msg_win_mgr.reconfig()

	def on_compact_view_checkbutton_toggled(self, widget):
		active = widget.get_active()
		for ctl in gajim.interface.msg_win_mgr.controls():
			ctl.chat_buttons_set_visible(active)
		gajim.config.set('compact_view', active)
		gajim.interface.save_config()
		gajim.interface.roster.draw_roster()

	def on_xhtml_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_incoming_xhtml')

	def apply_speller(self):
		for acct in gajim.connections:
			for ctrl in gajim.interface.msg_win_mgr.controls():
				if isinstance(ctrl, chat_control.ChatControlBase):
					try:
						spell_obj = gtkspell.get_from_text_view(ctrl.msg_textview)
					except:
						spell_obj = None

					if not spell_obj:
						gtkspell.Spell(ctrl.msg_textview)

	def remove_speller(self):
		for acct in gajim.connections:
			for ctrl in gajim.interface.msg_win_mgr.controls():
				if isinstance(ctrl, chat_control.ChatControlBase):
					try:
						spell_obj = gtkspell.get_from_text_view(ctrl.msg_textview)
					except:
						spell_obj = None
					if spell_obj:
						spell_obj.detach()

	def on_speller_checkbutton_toggled(self, widget):
		active = widget.get_active()
		gajim.config.set('use_speller', active)
		gajim.interface.save_config()
		if active:
			lang = gajim.config.get('speller_language')
			if not lang:
				lang = gajim.LANG
			tv = gtk.TextView()
			try:
				spell = gtkspell.Spell(tv, lang)
			except:
				dialogs.ErrorDialog(
					_('Dictionary for lang %s not available') % lang,
					_('You have to install %s dictionary to use spellchecking, or '
					'choose another language by setting the speller_language option.'
					) % lang)
				gajim.config.set('use_speller', False)
				widget.set_active(False)
			else:
				gajim.config.set('speller_language', lang)
				self.apply_speller()
		else:
			self.remove_speller()

	def on_theme_combobox_changed(self, widget):
		model = widget.get_model()
		active = widget.get_active()
		config_theme = model[active][0].decode('utf-8').replace(' ', '_')

		gajim.config.set('roster_theme', config_theme)

		# begin repainting themed widgets throughout
		gajim.interface.roster.repaint_themed_widgets()
		gajim.interface.roster.change_roster_style(None)
		gajim.interface.save_config()

	def update_theme_list(self):
		theme_combobox = self.xml.get_widget('theme_combobox')
		model = gtk.ListStore(str)
		theme_combobox.set_model(model) 
		i = 0
		for config_theme in gajim.config.get_per('themes'):
			theme = config_theme.replace('_', ' ')
			model.append([theme])
			if gajim.config.get('roster_theme') == config_theme:
				theme_combobox.set_active(i)
			i += 1

	def on_manage_theme_button_clicked(self, widget):
		if self.theme_preferences is None:
			self.theme_preferences = dialogs.GajimThemesWindow()
		else:
			self.theme_preferences.window.present()
			self.theme_preferences.select_active_theme()

	def on_iconset_combobox_changed(self, widget):
		model = widget.get_model()
		active = widget.get_active()
		icon_string = model[active][1].decode('utf-8')
		gajim.config.set('iconset', icon_string)
		gajim.interface.roster.reload_jabber_state_images()
		gajim.interface.save_config()

	def on_transports_iconsets_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'use_transports_iconsets')
		gajim.interface.roster.reload_jabber_state_images()

	def on_outgoing_chat_states_combobox_changed(self, widget):
		active = widget.get_active()
		if active == 0: # all
			gajim.config.set('outgoing_chat_state_notifications', 'all')
		elif active == 1: # only composing
			gajim.config.set('outgoing_chat_state_notifications', 'composing_only')
		else: # disabled
			gajim.config.set('outgoing_chat_state_notifications', 'disabled')

	def on_displayed_chat_states_combobox_changed(self, widget):
		active = widget.get_active()
		if active == 0: # all
			gajim.config.set('displayed_chat_state_notifications', 'all')
		elif active == 1: # only composing
			gajim.config.set('displayed_chat_state_notifications',
				'composing_only')
		else: # disabled
			gajim.config.set('displayed_chat_state_notifications', 'disabled')

	def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_unknown_contacts')

	def on_on_event_combobox_changed(self, widget):
		active = widget.get_active()
		if active == 0:
			gajim.config.set('autopopup', True)
			gajim.config.set('notify_on_new_message', False)
		elif active == 1:
			gajim.config.set('autopopup', False)
			gajim.config.set('notify_on_new_message', True)
		else:
			gajim.config.set('autopopup', False)
			gajim.config.set('notify_on_new_message', False)

	def on_notify_on_signin_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signin')

	def on_notify_on_signout_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signout')

	def on_auto_popup_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopupaway')

	def on_open_advanced_notifications_button_clicked(self, widget):
		dialogs.AdvancedNotificationsWindow()

	def on_play_sounds_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sounds_on',
				[self.xml.get_widget('soundplayer_hbox'),
				self.xml.get_widget('sounds_scrolledwindow'),
				self.xml.get_widget('browse_sounds_hbox')])

	def on_soundplayer_entry_changed(self, widget):
		gajim.config.set('soundplayer', widget.get_text().decode('utf-8'))
		gajim.interface.save_config()

	def on_sounds_treemodel_row_changed(self, model, path, iter):
		sound_event = model[iter][3].decode('utf-8')
		gajim.config.set_per('soundevents', sound_event, 'enabled',
					bool(model[path][0]))
		gajim.config.set_per('soundevents', sound_event, 'path',
					model[iter][2].decode('utf-8'))
		gajim.interface.save_config()

	def update_text_tags(self):
		'''Update color tags in Opened Chat Windows'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.update_tags()

	def on_preference_widget_color_set(self, widget, text):
		color = widget.get_color()
		color_string = gtkgui_helpers.make_color_string(color)
		gajim.config.set(text, color_string)
		self.update_text_tags()
		gajim.interface.save_config()

	def on_preference_widget_font_set(self, widget, text):
		if widget:
			font = widget.get_font_name()
		else:
			font = ''
		gajim.config.set(text, font)
		self.update_text_font()
		gajim.interface.save_config()

	def update_text_font(self):
		'''Update text font in Opened Chat Windows'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.update_font()

	def on_incoming_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'inmsgcolor')

	def on_outgoing_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'outmsgcolor')

	def on_url_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'urlmsgcolor')

	def on_status_msg_colorbutton_color_set(self, widget):
		self.on_preference_widget_color_set(widget, 'statusmsgcolor')

	def on_conversation_fontbutton_font_set(self, widget):
		self.on_preference_widget_font_set(widget, 'conversation_font')
	
	def on_default_chat_font_toggled(self, widget):
		font_widget = self.xml.get_widget('conversation_fontbutton')
		if widget.get_active():
			font_widget.set_sensitive(False)
			font_widget = None
		else:
			font_widget.set_sensitive(True)
		self.on_preference_widget_font_set(font_widget, 'conversation_font')

	def on_reset_colors_button_clicked(self, widget):
		for i in ('inmsgcolor', 'outmsgcolor', 'statusmsgcolor', 'urlmsgcolor'):
			gajim.config.set(i, gajim.interface.default_colors[i])

		self.xml.get_widget('incoming_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('inmsgcolor')))
		self.xml.get_widget('outgoing_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('outmsgcolor')))
		self.xml.get_widget('status_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('statusmsgcolor')))
		self.xml.get_widget('url_msg_colorbutton').set_color(\
			gtk.gdk.color_parse(gajim.config.get('urlmsgcolor')))
		self.update_text_tags()
		gajim.interface.save_config()

	def on_auto_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoaway',
					[self.auto_away_time_spinbutton, self.auto_away_message_entry])

	def on_auto_away_time_spinbutton_value_changed(self, widget):
		aat = widget.get_value_as_int()
		gajim.config.set('autoawaytime', aat)
		gajim.interface.sleeper = common.sleepy.Sleepy(
					gajim.config.get('autoawaytime') * 60,
					gajim.config.get('autoxatime') * 60)
		gajim.interface.save_config()

	def on_auto_away_message_entry_changed(self, widget):
		gajim.config.set('autoaway_message', widget.get_text().decode('utf-8'))

	def on_auto_xa_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autoxa',
					[self.auto_xa_time_spinbutton, self.auto_xa_message_entry])

	def on_auto_xa_time_spinbutton_value_changed(self, widget):
		axt = widget.get_value_as_int()
		gajim.config.set('autoxatime', axt)
		gajim.interface.sleeper = common.sleepy.Sleepy(
					gajim.config.get('autoawaytime') * 60,
					gajim.config.get('autoxatime') * 60)
		gajim.interface.save_config()

	def on_auto_xa_message_entry_changed(self, widget):
		gajim.config.set('autoxa_message', widget.get_text().decode('utf-8'))

	def on_prompt_online_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_online_status')

	def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_offline_status')

	def fill_default_msg_treeview(self):
		model = self.default_msg_tree.get_model()
		model.clear()
		status = []
		for status_ in gajim.config.get_per('defaultstatusmsg'):
			status.append(status_)
		status.sort()
		for status_ in status:
			msg = gajim.config.get_per('defaultstatusmsg', status_, 'message')
			enabled = gajim.config.get_per('defaultstatusmsg', status_, 'enabled')
			iter = model.append()
			uf_show = helpers.get_uf_show(status_)
			model.set(iter, 0, status_, 1, uf_show, 2, msg, 3, enabled)

	def on_default_msg_cell_edited(self, cell, row, new_text):
		model = self.default_msg_tree.get_model()
		iter = model.get_iter_from_string(row)
		model.set_value(iter, 2, new_text)

	def default_msg_toggled_cb(self, cell, path):
		model = self.default_msg_tree.get_model()
		model[path][3] = not model[path][3]

	def on_default_msg_treemodel_row_changed(self, model, path, iter):
		status = model[iter][0]
		message = model[iter][2].decode('utf-8')
		gajim.config.set_per('defaultstatusmsg', status, 'enabled',
			model[iter][3])
		gajim.config.set_per('defaultstatusmsg', status, 'message', message)

	def on_default_status_expander_activate(self, expander):
		eventbox = self.xml.get_widget('default_status_eventbox')
		vbox = self.xml.get_widget('status_vbox')
		vbox.set_child_packing(eventbox, not expander.get_expanded(), True, 0,
			gtk.PACK_START)

	def save_status_messages(self, model):
		for msg in gajim.config.get_per('statusmsg'):
			gajim.config.del_per('statusmsg', msg)
		iter = model.get_iter_first()
		while iter:
			val = model[iter][0].decode('utf-8')
			if model[iter][1]: # we have a preset message
				if not val: # no title, use message text for title
					val = model[iter][1] 
				gajim.config.add_per('statusmsg', val)
				msg = helpers.to_one_line(model[iter][1].decode('utf-8'))
				gajim.config.set_per('statusmsg', val, 'message', msg)
			iter = model.iter_next(iter)
		gajim.interface.save_config()

	def on_msg_treemodel_row_changed(self, model, path, iter):
		self.save_status_messages(model)

	def on_msg_treemodel_row_deleted(self, model, path):
		self.save_status_messages(model)

	def on_applications_combobox_changed(self, widget):
		gajim.config.set('autodetect_browser_mailer', False)
		if sys.platform == 'darwin':
			if widget.get_active() == 0:
				gajim.config.set('autodetect_browser_mailer', True)
				self.xml.get_widget('custom_apps_frame').hide()
			elif widget.get_active() == 1:
				self.xml.get_widget('custom_apps_frame').hide()
				gajim.config.set('openwith', 'open')
			elif widget.get_active() == 2:
				self.xml.get_widget('custom_apps_frame').show()
				gajim.config.set('openwith', 'custom')
		else:
			if widget.get_active() == 4:
				self.xml.get_widget('custom_apps_frame').show()
				gajim.config.set('openwith', 'custom')
			else:
				if widget.get_active() == 0:
					gajim.config.set('autodetect_browser_mailer', True)
				elif widget.get_active() == 1:
					gajim.config.set('openwith', 'gnome-open')
				elif widget.get_active() == 2:
					gajim.config.set('openwith', 'kfmclient exec')
				elif widget.get_active() == 3:
					gajim.config.set('openwith', 'exo-open')
				self.xml.get_widget('custom_apps_frame').hide()
		gajim.interface.save_config()

	def on_custom_browser_entry_changed(self, widget):
		gajim.config.set('custombrowser', widget.get_text().decode('utf-8'))
		gajim.interface.save_config()

	def on_custom_mail_client_entry_changed(self, widget):
		gajim.config.set('custommailapp', widget.get_text().decode('utf-8'))
		gajim.interface.save_config()

	def on_custom_file_manager_entry_changed(self, widget):
		gajim.config.set('custom_file_manager', widget.get_text().decode('utf-8'))
		gajim.interface.save_config()

	def on_log_show_changes_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

	def on_send_os_info_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'send_os_info')

	def on_check_default_client_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'check_if_gajim_is_default')

	def on_notify_gmail_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_new_gmail_email')

	def on_notify_gmail_extra_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_new_gmail_email_extra')

	def fill_msg_treeview(self):
		self.xml.get_widget('delete_msg_button').set_sensitive(False)
		model = self.msg_tree.get_model()
		model.clear()
		preset_status = []
		for msg_name in gajim.config.get_per('statusmsg'):
			preset_status.append(msg_name)
		preset_status.sort()
		for msg_name in preset_status:
			msg_text = gajim.config.get_per('statusmsg', msg_name, 'message')
			msg_text = helpers.from_one_line(msg_text)
			iter = model.append()
			model.set(iter, 0, msg_name, 1, msg_text)

	def on_msg_cell_edited(self, cell, row, new_text):
		model = self.msg_tree.get_model()
		iter = model.get_iter_from_string(row)
		model.set_value(iter, 0, new_text)

	def on_msg_treeview_cursor_changed(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		self.xml.get_widget('delete_msg_button').set_sensitive(True)
		buf = self.xml.get_widget('msg_textview').get_buffer()
		msg = model[iter][1]
		buf.set_text(msg)

	def on_new_msg_button_clicked(self, widget, data = None):
		model = self.msg_tree.get_model()
		iter = model.append()
		model.set(iter, 0, _('status message title'), 1, _('status message text'))
		self.msg_tree.set_cursor(model.get_path(iter))

	def on_delete_msg_button_clicked(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		buf = self.xml.get_widget('msg_textview').get_buffer()
		model.remove(iter)
		buf.set_text('')
		self.xml.get_widget('delete_msg_button').set_sensitive(False)

	def on_msg_textview_changed(self, widget, data = None):
		(model, iter) = self.msg_tree.get_selection().get_selected()
		if not iter:
			return
		buf = self.xml.get_widget('msg_textview').get_buffer()
		first_iter, end_iter = buf.get_bounds()
		name = model.get_value(iter, 0)
		model.set_value(iter, 1, buf.get_text(first_iter, end_iter))

	def on_msg_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_delete_msg_button_clicked(widget)

	def sound_toggled_cb(self, cell, path):
		model = self.sound_tree.get_model()
		model[path][0] = not model[path][0]

	def fill_sound_treeview(self):
		model = self.sound_tree.get_model()
		model.clear()
		
		# NOTE: sounds_ui_names MUST have all items of
		# sounds = gajim.config.get_per('soundevents') as keys 
		sounds_dict = {
			'first_message_received': _('First Message Received'),
			'next_message_received': _('Next Message Received'),
			'contact_connected': _('Contact Connected'),
			'contact_disconnected': _('Contact Disconnected'),
			'message_sent': _('Message Sent'),
			'muc_message_highlight': _('Group Chat Message Highlight'),
			'muc_message_received': _('Group Chat Message Received')
		}

		# In case of a GMail account we provide a sound notification option
		for account in gajim.config.get_per('accounts'):
			jid = gajim.get_jid_from_account(account)
			if gajim.get_server_from_jid(jid) in gajim.gmail_domains:
				sounds_dict['gmail_received'] = _('GMail Email Received')
				break
		
		for sound_event_config_name, sound_ui_name in sounds_dict.items():
			enabled = gajim.config.get_per('soundevents',
				sound_event_config_name, 'enabled')
			path = gajim.config.get_per('soundevents',
				sound_event_config_name, 'path')
			model.append((enabled, sound_ui_name, path, sound_event_config_name))

	def on_treeview_sounds_cursor_changed(self, widget, data = None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		sounds_entry = self.xml.get_widget('sounds_entry')
		if not iter:
			sounds_entry.set_text('')
			return
		path_to_snd_file = model[iter][2]
		sounds_entry.set_text(path_to_snd_file)

	def on_browse_for_sounds_button_clicked(self, widget, data = None):
		(model, iter) = self.sound_tree.get_selection().get_selected()
		if not iter:
			return
		def on_ok(widget, path_to_snd_file):
			self.dialog.destroy()
			model, iter = self.sound_tree.get_selection().get_selected()
			if not path_to_snd_file:
				model[iter][2] = ''
				self.xml.get_widget('sounds_entry').set_text('')
				model[iter][0] = False
				return
			directory = os.path.dirname(path_to_snd_file)
			gajim.config.set('last_sounds_dir', directory)
			self.xml.get_widget('sounds_entry').set_text(path_to_snd_file)

			model[iter][2] = path_to_snd_file # set new path to sounds_model
			model[iter][0] = True # set the sound to enabled

		def on_cancel(widget):
			self.dialog.destroy()
			model, iter = self.sound_tree.get_selection().get_selected()
			model[iter][2] = ''
			model[iter][0] = False

		path_to_snd_file = model[iter][2].decode('utf-8')
		path_to_snd_file = os.path.join(os.getcwd(), path_to_snd_file)
		self.dialog = dialogs.SoundChooserDialog(path_to_snd_file, on_ok,
			on_cancel)

	def on_sounds_entry_changed(self, widget):
		path_to_snd_file = widget.get_text()
		model, iter = self.sound_tree.get_selection().get_selected()
		model[iter][2] = path_to_snd_file # set new path to sounds_model

	def on_play_button_clicked(self, widget):
		model, iter = self.sound_tree.get_selection().get_selected()
		if not iter:
			return
		snd_event_config_name = model[iter][3]
		helpers.play_sound(snd_event_config_name)

	def on_open_advanced_editor_button_clicked(self, widget, data = None):
		if gajim.interface.instances.has_key('advanced_config'):
			gajim.interface.instances['advanced_config'].window.present()
		else:
			gajim.interface.instances['advanced_config'] = \
				dialogs.AdvancedConfigurationWindow()

	def set_status_msg_from_current_music_track_checkbutton_toggled(self,
		widget):
		self.on_checkbutton_toggled(widget,
			'set_status_msg_from_current_music_track')
		gajim.interface.roster.enable_syncing_status_msg_from_current_music_track(
			widget.get_active())

#---------- ManageProxiesWindow class -------------#
class ManageProxiesWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('manage_proxies_window.glade')
		self.window = self.xml.get_widget('manage_proxies_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.proxies_treeview = self.xml.get_widget('proxies_treeview')
		self.proxyname_entry = self.xml.get_widget('proxyname_entry')
		self.proxytype_combobox = self.xml.get_widget('proxytype_combobox')
		self.init_list()
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def fill_proxies_treeview(self):
		model = self.proxies_treeview.get_model()
		model.clear()
		iter = model.append()
		model.set(iter, 0, _('None'))
		for p in gajim.config.get_per('proxies'):
			iter = model.append()
			model.set(iter, 0, p)

	def init_list(self):
		self.xml.get_widget('remove_proxy_button').set_sensitive(False)
		self.proxytype_combobox.set_sensitive(False)
		self.xml.get_widget('proxy_table').set_sensitive(False)
		model = gtk.ListStore(str)
		self.proxies_treeview.set_model(model)
		col = gtk.TreeViewColumn('Proxies')
		self.proxies_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		self.fill_proxies_treeview()
		self.xml.get_widget('proxytype_combobox').set_active(0)

	def on_manage_proxies_window_destroy(self, widget):
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].\
				update_proxy_list()
		del gajim.interface.instances['manage_proxies']

	def on_add_proxy_button_clicked(self, widget):
		model = self.proxies_treeview.get_model()
		proxies = gajim.config.get_per('proxies')
		i = 1
		while ('proxy' + unicode(i)) in proxies:
			i += 1
		iter = model.append()
		model.set(iter, 0, 'proxy' + unicode(i))
		gajim.config.add_per('proxies', 'proxy' + unicode(i))

	def on_remove_proxy_button_clicked(self, widget):
		(model, iter) = self.proxies_treeview.get_selection().get_selected()
		if not iter:
			return
		proxy = model[iter][0].decode('utf-8')
		model.remove(iter)
		gajim.config.del_per('proxies', proxy)
		self.xml.get_widget('remove_proxy_button').set_sensitive(False)

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_useauth_checkbutton_toggled(self, widget):
		act = widget.get_active()
		self.xml.get_widget('proxyuser_entry').set_sensitive(act)
		self.xml.get_widget('proxypass_entry').set_sensitive(act)

	def on_proxies_treeview_cursor_changed(self, widget):
		#FIXME: check if off proxy settings are correct (see
		# http://trac.gajim.org/changeset/1921#file2 line 1221
		(model, iter) = widget.get_selection().get_selected()
		if not iter:
			return
		proxy = model[iter][0]
		self.xml.get_widget('proxyname_entry').set_text(proxy)
		proxyhost_entry = self.xml.get_widget('proxyhost_entry')
		proxyport_entry = self.xml.get_widget('proxyport_entry')
		proxyuser_entry = self.xml.get_widget('proxyuser_entry')
		proxypass_entry = self.xml.get_widget('proxypass_entry')
		useauth_checkbutton = self.xml.get_widget('useauth_checkbutton')
		proxyhost_entry.set_text('')
		proxyport_entry.set_text('')
		proxyuser_entry.set_text('')
		proxypass_entry.set_text('')
		useauth_checkbutton.set_active(False)
		self.on_useauth_checkbutton_toggled(useauth_checkbutton)
		if proxy == _('None'): # special proxy None
			self.proxyname_entry.set_editable(False)
			self.xml.get_widget('remove_proxy_button').set_sensitive(False)
			self.xml.get_widget('proxytype_combobox').set_sensitive(False)
			self.xml.get_widget('proxy_table').set_sensitive(False)
		else:
			self.proxyname_entry.set_editable(True)
			self.xml.get_widget('remove_proxy_button').set_sensitive(True)
			self.xml.get_widget('proxytype_combobox').set_sensitive(True)
			self.xml.get_widget('proxy_table').set_sensitive(True)
			proxyhost_entry.set_text(gajim.config.get_per('proxies', proxy,
				'host'))
			proxyport_entry.set_text(unicode(gajim.config.get_per('proxies',
				proxy, 'port')))
			proxyuser_entry.set_text(gajim.config.get_per('proxies', proxy,
				'user'))
			proxypass_entry.set_text(gajim.config.get_per('proxies', proxy,
				'pass'))
			proxytype = gajim.config.get_per('proxies', proxy, 'type')
			types = ['http', 'socks5']
			self.proxytype_combobox.set_active(types.index(proxytype))
			if gajim.config.get_per('proxies', proxy, 'user'):
				useauth_checkbutton.set_active(True)

	def on_proxies_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Delete:
			self.on_remove_proxy_button_clicked(widget)

	def on_proxyname_entry_changed(self, widget):
		(model, iter) = self.proxies_treeview.get_selection().get_selected()
		if not iter:
			return
		old_name = model.get_value(iter, 0).decode('utf-8')
		new_name = widget.get_text().decode('utf-8')
		if new_name == '':
			return
		if new_name == old_name:
			return
		config = gajim.config.get_per('proxies', old_name)
		gajim.config.del_per('proxies', old_name)
		gajim.config.add_per('proxies', new_name)
		for option in config:
			gajim.config.set_per('proxies', new_name, option,
				config[option][common.config.OPT_VAL])
		model.set_value(iter, 0, new_name)

	def on_proxytype_combobox_changed(self, widget):
		types = ['http', 'socks5']
		type_ = self.proxytype_combobox.get_active()
		proxy = self.proxyname_entry.get_text().decode('utf-8')
		gajim.config.set_per('proxies', proxy, 'type', types[type_])

	def on_proxyhost_entry_changed(self, widget):
		value = widget.get_text().decode('utf-8')
		proxy = self.proxyname_entry.get_text().decode('utf-8')
		gajim.config.set_per('proxies', proxy, 'host', value)

	def on_proxyport_entry_changed(self, widget):
		value = widget.get_text().decode('utf-8')
		proxy = self.proxyname_entry.get_text().decode('utf-8')
		gajim.config.set_per('proxies', proxy, 'port', value)

	def on_proxyuser_entry_changed(self, widget):
		value = widget.get_text().decode('utf-8')
		proxy = self.proxyname_entry.get_text().decode('utf-8')
		gajim.config.set_per('proxies', proxy, 'user', value)

	def on_proxypass_entry_changed(self, widget):
		value = widget.get_text().decode('utf-8')
		proxy = self.proxyname_entry.get_text().decode('utf-8')
		gajim.config.set_per('proxies', proxy, 'pass', value)


#---------- AccountsWindow class -------------#
class AccountsWindow:
	'''Class for accounts window: list of accounts'''
	def on_accounts_window_destroy(self, widget):
		del gajim.interface.instances['accounts']

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('accounts_window.glade')
		self.window = self.xml.get_widget('accounts_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.accounts_treeview = self.xml.get_widget('accounts_treeview')
		self.remove_button = self.xml.get_widget('remove_button')
		self.rename_button = self.xml.get_widget('rename_button')
		#FIXME: I don't understand why this import is necessary
		import os
		path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
			'kbd_input.png')
		img = self.xml.get_widget('rename_image')
		img.set_from_file(path_to_kbd_input_img)
		self.notebook = self.xml.get_widget('notebook')
		# Name
		model = gtk.ListStore(str)
		self.accounts_treeview.set_model(model)
		# column
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Name'), renderer, text = 0)

		self.current_account = None
		# When we fill info, we don't want to handle the changed signals
		self.ignore_events = False
		self.need_relogin = False
		self.resend_presence = False

		self.update_proxy_list()
		self.xml.signal_autoconnect(self)
		self.init_accounts()
		self.window.show_all()

		# Merge accounts
		st = gajim.config.get('mergeaccounts')
		self.xml.get_widget('merge_checkbutton').set_active(st)

		self.avahi_available = True
		try:
			import avahi
		except ImportError:
			self.avahi_available = False

	def on_accounts_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def select_account(self, account):
		model = self.accounts_treeview.get_model()
		iter = model.get_iter_root()
		while iter:
			acct = model[iter][0].decode('utf-8')
			if account == acct:
				self.accounts_treeview.set_cursor(model.get_path(iter))
				return
			iter = model.iter_next(iter)

	def init_accounts(self):
		'''initialize listStore with existing accounts'''
		self.remove_button.set_sensitive(False)
		self.rename_button.set_sensitive(False)
		self.current_account = None
		self.init_account()
		model = self.accounts_treeview.get_model()
		model.clear()
		for account in gajim.config.get_per('accounts'):
			iter = model.append()
			model.set(iter, 0, account)

	def resend(self):
		show = gajim.SHOW_LIST[gajim.connections[self.current_account].connected]
		status = gajim.connections[self.current_account].status
		gajim.connections[self.current_account].change_status(show, status)

	def on_accounts_treeview_cursor_changed(self, widget):
		'''Activate modify buttons when a row is selected, update accounts info'''
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		if iter:
			account = model[iter][0].decode('utf-8')
		else:
			account = None
		if self.current_account and self.current_account == account:
			# We're comming back to our current account, no need to update widgets
			return
		# Save config for previous account if needed cause focus_out event is
		# called after the changed event
		if self.current_account:
			focused_widget = self.window.get_focus()
			focused_widget_name = focused_widget.get_name()
			if focused_widget_name in ('jid_entry1', 'resource_entry1',
			'custom_port_entry'):
				if focused_widget_name == 'jid_entry1':
					func = self.on_jid_entry1_focus_out_event
				elif focused_widget_name == 'resource_entry1':
					func = self.on_resource_entry1_focus_out_event
				elif focused_widget_name == 'custom_port_entry':
					func = self.on_custom_port_entry_focus_out_event
				if func(focused_widget, None):
					# Error detected in entry, don't change account, re-put cursor on
					# previous row
					self.select_account(self.current_account)
					return True
				self.window.set_focus(widget)

		if self.need_relogin and self.current_account == gajim.ZEROCONF_ACC_NAME:
			if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME):
				gajim.connections[gajim.ZEROCONF_ACC_NAME].update_details()
				return
			
		elif self.need_relogin and self.current_account and \
		gajim.connections[self.current_account].connected > 0:
			def login(account, show_before, status_before):
				''' login with previous status'''
				# first make sure connection is really closed, 
				# 0.5 may not be enough
				gajim.connections[account].disconnect(True)
				gajim.interface.roster.send_status(account, show_before,
					status_before)

			def relog():
				self.dialog.destroy()
				show_before = gajim.SHOW_LIST[gajim.connections[
					self.current_account].connected]
				status_before = gajim.connections[self.current_account].status
				gajim.interface.roster.send_status(self.current_account, 'offline',
					_('Be right back.'))
				gobject.timeout_add(500, login, self.current_account, show_before,
					status_before)

			self.dialog = dialogs.YesNoDialog(_('Relogin now?'),
				_('If you want all the changes to apply instantly, '
				'you must relogin.'))
			resp = self.dialog.get_response()
			if resp == gtk.RESPONSE_YES:
				relog()
			elif self.resend_presence:
				self.resend()
		elif self.resend_presence:
			self.resend()

		self.need_relogin = False
		self.resend_presence = False
		self.remove_button.set_sensitive(True)
		self.rename_button.set_sensitive(True)
		if iter:
			self.current_account = account
			if account == gajim.ZEROCONF_ACC_NAME:
				self.remove_button.set_sensitive(False)
				self.rename_button.set_sensitive(False)
		self.init_account()
		self.update_proxy_list()

	def update_proxy_list(self):
		if self.current_account:
			our_proxy = gajim.config.get_per('accounts', self.current_account,
				'proxy')
		else:
			our_proxy = ''

		if not our_proxy:
			our_proxy = _('None')
		proxy_combobox = self.xml.get_widget('proxies_combobox1')
		model = gtk.ListStore(str)
		proxy_combobox.set_model(model)
		l = gajim.config.get_per('proxies')
		l.insert(0, _('None'))
		for i in xrange(len(l)):
			model.append([l[i]])
			if our_proxy == l[i]:
				proxy_combobox.set_active(i)

	def init_account(self):
		if not self.current_account:
			self.notebook.set_current_page(0)
			return
		if gajim.config.get_per('accounts', self.current_account, 'is_zeroconf'):
			self.ignore_events = True
			self.init_zeroconf_account()
			self.ignore_events = False
			self.notebook.set_current_page(2)
			return
		self.ignore_events = True
		self.init_normal_account()
		self.ignore_events = False
		self.notebook.set_current_page(1)

	def init_zeroconf_account(self):
		enable = gajim.config.get('enable_zeroconf')
		self.xml.get_widget('enable_zeroconf_checkbutton2').set_active(enable)
		self.xml.get_widget('zeroconf_notebook').set_sensitive(enable)
		# General tab
		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'autoconnect')
		self.xml.get_widget('autoconnect_checkbutton2').set_active(st)
		
		list_no_log_for = gajim.config.get_per('accounts',
			gajim.ZEROCONF_ACC_NAME, 'no_log_for').split()
		if gajim.ZEROCONF_ACC_NAME in list_no_log_for:
			self.xml.get_widget('log_history_checkbutton2').set_active(0)
		else:
			self.xml.get_widget('log_history_checkbutton2').set_active(1)

		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'sync_with_global_status')
		self.xml.get_widget('sync_with_global_status_checkbutton2').set_active(st)

		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'use_custom_host')
		self.xml.get_widget('custom_port_checkbutton2').set_active(st)
		self.xml.get_widget('custom_port_entry2').set_sensitive(st)

		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'custom_port')
		if not st:
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'custom_port', '5298')
			st = '5298'
		self.xml.get_widget('custom_port_entry2').set_text(str(st))

		# Personal tab
		gpg_key_label = self.xml.get_widget('gpg_key_label2')
		if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME) and \
		gajim.connections[gajim.ZEROCONF_ACC_NAME].gpg:
			self.xml.get_widget('gpg_choose_button2').set_sensitive(True)
			self.init_account_gpg()
		else:
			gpg_key_label.set_text(_('OpenPGP is not usable in this computer'))
			self.xml.get_widget('gpg_choose_button2').set_sensitive(False)

		for opt in ('first_name', 'last_name', 'jabber_id', 'email'):
			st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'zeroconf_' + opt)
			self.xml.get_widget(opt + '_entry2').set_text(st)

	def init_account_gpg(self):
		account = self.current_account
		keyid = gajim.config.get_per('accounts', account, 'keyid')
		keyname = gajim.config.get_per('accounts', account, 'keyname')
		use_gpg_agent = gajim.config.get('use_gpg_agent')

		if account == gajim.ZEROCONF_ACC_NAME:
			widget_name_add = '2'
		else:
			widget_name_add = '1'

		gpg_key_label = self.xml.get_widget('gpg_key_label' + widget_name_add)
		gpg_name_label = self.xml.get_widget('gpg_name_label' + widget_name_add)
		use_gpg_agent_checkbutton = self.xml.get_widget(
			'use_gpg_agent_checkbutton' + widget_name_add)

		if not keyid or not gajim.connections[account].gpg:
			use_gpg_agent_checkbutton.set_sensitive(False)
			gpg_key_label.set_text(_('No key selected'))
			gpg_name_label.set_text('')
			return

		gpg_key_label.set_text(keyid)
		gpg_name_label.set_text(keyname)
		use_gpg_agent_checkbutton.set_sensitive(True)
		use_gpg_agent_checkbutton.set_active(use_gpg_agent)

	def init_normal_account(self):
		account = self.current_account
		# Account tab
		jid = gajim.config.get_per('accounts', account, 'name') \
			+ '@' + gajim.config.get_per('accounts', account, 'hostname')
		self.xml.get_widget('jid_entry1').set_text(jid)
		savepass = gajim.config.get_per('accounts', account, 'savepass')
		self.xml.get_widget('save_password_checkbutton1').set_active(savepass)
		password_entry = self.xml.get_widget('password_entry1')
		if savepass:
			passstr = passwords.get_password(account) or ''
			password_entry.set_sensitive(True)
		else:
			passstr = ''
			password_entry.set_sensitive(False)
		password_entry.set_text(passstr)

		self.xml.get_widget('resource_entry1').set_text(gajim.config.get_per(
			'accounts', account, 'resource'))
		self.xml.get_widget('adjust_priority_with_status_checkbutton1').\
			set_active(gajim.config.get_per('accounts', account,
			'adjust_priority_with_status'))
		spinbutton = self.xml.get_widget('priority_spinbutton1')
		if gajim.config.get('enable_negative_priority'):
			spinbutton.set_range(-128, 127)
		else:
			spinbutton.set_range(0, 127)
		spinbutton.set_value(gajim.config.get_per('accounts', account,
			'priority'))

		# Connection tab
		usessl = gajim.config.get_per('accounts', account, 'usessl')
		self.xml.get_widget('use_ssl_checkbutton1').set_active(usessl)

		self.xml.get_widget('send_keepalive_checkbutton1').set_active(
			gajim.config.get_per('accounts', account, 'keep_alives_enabled'))

		use_custom_host = gajim.config.get_per('accounts', account,
			'use_custom_host')
		self.xml.get_widget('custom_host_port_checkbutton1').set_active(
			use_custom_host)
		custom_host = gajim.config.get_per('accounts', account, 'custom_host')
		if not custom_host:
			custom_host = gajim.config.get_per('accounts', account, 'hostname')
		self.xml.get_widget('custom_host_entry1').set_text(custom_host)
		custom_port = gajim.config.get_per('accounts', account, 'custom_port')
		if not custom_port:
			custom_port = 5222
		self.xml.get_widget('custom_port_entry1').set_text(unicode(custom_port))

		# Personal tab
		gpg_key_label = self.xml.get_widget('gpg_key_label1')
		if gajim.connections[account].gpg:
			self.xml.get_widget('gpg_choose_button1').set_sensitive(True)
			self.init_account_gpg()
		else:
			gpg_key_label.set_text(_('OpenPGP is not usable in this computer'))
			self.xml.get_widget('gpg_choose_button1').set_sensitive(False)

		# General tab
		self.xml.get_widget('autoconnect_checkbutton1').set_active(gajim.config.\
			get_per('accounts', account, 'autoconnect'))
		self.xml.get_widget('autoreconnect_checkbutton1').set_active(gajim.
			config.get_per('accounts', account, 'autoreconnect'))

		list_no_log_for = gajim.config.get_per('accounts', account,
			'no_log_for').split()
		if account in list_no_log_for:
			self.xml.get_widget('log_history_checkbutton1').set_active(False)
		else:
			self.xml.get_widget('log_history_checkbutton1').set_active(True)

		self.xml.get_widget('sync_with_global_status_checkbutton1').set_active(
			gajim.config.get_per('accounts', account, 'sync_with_global_status'))
		self.xml.get_widget('use_ft_proxies_checkbutton1').set_active(
			gajim.config.get_per('accounts', account, 'use_ft_proxies'))

	def on_add_button_clicked(self, widget):
		'''When add button is clicked: open an account information window'''
		if gajim.interface.instances.has_key('account_creation_wizard'):
			gajim.interface.instances['account_creation_wizard'].window.present()
		else:
			gajim.interface.instances['account_creation_wizard'] = \
				AccountCreationWizardWindow()

	def on_remove_button_clicked(self, widget):
		'''When delete button is clicked:
		Remove an account from the listStore and from the config file'''
		if not self.current_account:
			return
		account = self.current_account
		if len(gajim.events.get_events(account)):
			dialogs.ErrorDialog(_('Unread events'),
				_('Read all pending events before removing this account.'))
			return

		if gajim.config.get_per('accounts', account, 'is_zeroconf'):
			# Should never happen as button is insensitive
			return

		win_opened = False
		if gajim.interface.msg_win_mgr.get_controls(acct = account):
			win_opened = True
		else:
			for key in gajim.interface.instances[account]:
				if gajim.interface.instances[account][key] and key != \
				'remove_account':
					win_opened = True
					break
		# Detect if we have opened windows for this account
		def remove(account):
			if gajim.interface.instances[account].has_key('remove_account'):
				gajim.interface.instances[account]['remove_account'].window.\
					present()
			else:
				gajim.interface.instances[account]['remove_account'] = \
					RemoveAccountWindow(account)
		if win_opened:
			dialog = dialogs.ConfirmationDialog(
				_('You have opened chat in account %s') % account,
				_('All chat and groupchat windows will be closed. Do you want to '
				'continue?'),
				on_response_ok = (remove, account))
		else:
			remove(account)

	def on_rename_button_clicked(self, widget):
		if gajim.connections[self.current_account].connected != 0:
			dialogs.ErrorDialog(
				_('You are currently connected to the server'),
				_('To change the account name, you must be disconnected.'))
			return
		if len(gajim.events.get_events(self.current_account)):
			dialogs.ErrorDialog(_('Unread events'),
				_('To change the account name, you must read all pending '
				'events.'))
			return
		# Get the new name
		def on_renamed(new_name, old_name):
			if new_name in gajim.connections:
				dialogs.ErrorDialog(_('Account Name Already Used'),
					_('This name is already used by another of your accounts. '
					'Please choose another name.'))
				return
			if (new_name == ''):
				dialogs.ErrorDialog(_('Invalid account name'),
					_('Account name cannot be empty.'))
				return
			if new_name.find(' ') != -1:
				dialogs.ErrorDialog(_('Invalid account name'),
					_('Account name cannot contain spaces.'))
				return
			# update variables
			gajim.interface.instances[new_name] = gajim.interface.instances[
				old_name]
			gajim.interface.minimized_controls[new_name] = \
				gajim.interface.minimized_controls[old_name]
			gajim.nicks[new_name] = gajim.nicks[old_name]
			gajim.block_signed_in_notifications[new_name] = \
				gajim.block_signed_in_notifications[old_name]
			gajim.groups[new_name] = gajim.groups[old_name]
			gajim.gc_connected[new_name] = gajim.gc_connected[old_name]
			gajim.automatic_rooms[new_name] = gajim.automatic_rooms[old_name]
			gajim.newly_added[new_name] = gajim.newly_added[old_name]
			gajim.to_be_removed[new_name] = gajim.to_be_removed[old_name]
			gajim.sleeper_state[new_name] = gajim.sleeper_state[old_name]
			gajim.encrypted_chats[new_name] = gajim.encrypted_chats[old_name]
			gajim.last_message_time[new_name] = gajim.last_message_time[old_name]
			gajim.status_before_autoaway[new_name] = \
				gajim.status_before_autoaway[old_name]
			gajim.transport_avatar[new_name] = gajim.transport_avatar[old_name]

			gajim.contacts.change_account_name(old_name, new_name)
			gajim.events.change_account_name(old_name, new_name)

			# change account variable for chat / gc controls
			gajim.interface.msg_win_mgr.change_account_name(old_name, new_name)
			# upgrade account variable in opened windows
			for kind in ('infos', 'disco', 'gc_config', 'search'):
				for j in gajim.interface.instances[new_name][kind]:
					gajim.interface.instances[new_name][kind][j].account = new_name

			# ServiceCache object keep old property account
			if hasattr(gajim.connections[old_name], 'services_cache'):
				gajim.connections[old_name].services_cache.account = new_name
			del gajim.interface.instances[old_name]
			del gajim.interface.minimized_controls[old_name]
			del gajim.nicks[old_name]
			del gajim.block_signed_in_notifications[old_name]
			del gajim.groups[old_name]
			del gajim.gc_connected[old_name]
			del gajim.automatic_rooms[old_name]
			del gajim.newly_added[old_name]
			del gajim.to_be_removed[old_name]
			del gajim.sleeper_state[old_name]
			del gajim.encrypted_chats[old_name]
			del gajim.last_message_time[old_name]
			del gajim.status_before_autoaway[old_name]
			del gajim.transport_avatar[old_name]
			gajim.connections[old_name].name = new_name
			gajim.connections[new_name] = gajim.connections[old_name]
			del gajim.connections[old_name]
			gajim.config.add_per('accounts', new_name)
			old_config = gajim.config.get_per('accounts', old_name)
			for opt in old_config:
				gajim.config.set_per('accounts', new_name, opt, old_config[opt][1])
			gajim.config.del_per('accounts', old_name)
			if self.current_account == old_name:
				self.current_account = new_name
			# refresh roster
			gajim.interface.roster.draw_roster()
			self.init_accounts()
			self.select_account(new_name)

		title = _('Rename Account')
		message = _('Enter a new name for account %s') % self.current_account
		old_text = self.current_account
		dialogs.InputDialog(title, message, old_text, is_modal=False,
			ok_handler=(on_renamed, self.current_account))

	def option_changed(self, option, value):
		return gajim.config.get_per('accounts', self.current_account, option) != \
			value

	def on_jid_entry1_focus_out_event(self, widget, event):
		if self.ignore_events:
			return
		jid = widget.get_text()
		# check if jid is conform to RFC and stringprep it
		try:
			jid = helpers.parse_jid(jid)
		except helpers.InvalidFormat, s:
			if not widget.is_focus():
				pritext = _('Invalid Jabber ID')
				dialogs.ErrorDialog(pritext, str(s))
				gobject.idle_add(lambda: widget.grab_focus())
			return True

		jid_splited = jid.split('@', 1)
		if len(jid_splited) != 2:
			if not widget.is_focus():
				pritext = _('Invalid Jabber ID')
				sectext = _('A Jabber ID must be in the form "user@servername".')
				dialogs.ErrorDialog(pritext, sectext)
				gobject.idle_add(lambda: widget.grab_focus())
			return True

		if self.option_changed('name', jid_splited[0]) or \
		self.option_changed('hostname', jid_splited[1]):
			self.need_relogin = True

		gajim.config.set_per('accounts', self.current_account, 'name',
			jid_splited[0])
		gajim.config.set_per('accounts', self.current_account, 'hostname',
			jid_splited[1])

	def on_password_entry1_changed(self, widget):
		if self.ignore_events:
			return
		passwords.save_password(self.current_account, widget.get_text())

	def on_save_password_checkbutton1_toggled(self, widget):
		if self.ignore_events:
			return
		active = widget.get_active()
		gajim.config.set_per('accounts', self.current_account, 'savepass', active)
		if active:
			password = self.xml.get_widget('password_entry1').get_text()
			passwords.save_password(self.current_account, password)
		else:
			passwords.save_password(self.current_account, '')
		
	def on_resource_entry1_focus_out_event(self, widget, event):
		if self.ignore_events:
			return
		resource = self.xml.get_widget('resource_entry1').get_text().decode(
			'utf-8')
		try:
			resource = helpers.parse_resource(resource)
		except helpers.InvalidFormat, s:
			if not widget.is_focus():
				pritext = _('Invalid Jabber ID')
				dialogs.ErrorDialog(pritext, str(s))
				gobject.idle_add(lambda: widget.grab_focus())
			return True

		if self.option_changed('resource', resource):
			self.need_relogin = True

		gajim.config.set_per('accounts', self.current_account, 'resource',
			resource)

	def on_adjust_priority_with_status_checkbutton1_toggled(self, widget):
		self.xml.get_widget('priority_spinbutton1').set_sensitive(
			not widget.get_active())
		self.on_checkbutton_toggled(widget, 'adjust_priority_with_status',
			account = self.current_account)

	def on_priority_spinbutton1_value_changed(self, widget):
		prio = widget.get_value_as_int()

		if self.option_changed('priority', prio):
			self.resend_presence = True

		gajim.config.set_per('accounts', self.current_account, 'priority', prio)

	def on_synchronise_contacts_button1_clicked(self, widget):
		try:
			dialog = dialogs.SynchroniseSelectAccountDialog(self.current_account)
		except GajimGeneralException:
			# If we showed ErrorDialog, there will not be dialog instance
			return

	def on_change_password_button1_clicked(self, widget):
		try:
			dialog = dialogs.ChangePasswordDialog(self.current_account)
		except GajimGeneralException:
			# if we showed ErrorDialog, there will not be dialog instance
			return

		new_password = dialog.run()
		if new_password != -1:
			gajim.connections[self.current_account].change_password(new_password)
			if self.xml.get_widget('save_password_checkbutton1').get_active():
				self.xml.get_widget('password_entry1').set_text(new_password)

	def on_autoconnect_checkbutton_toggled(self, widget):
		if self.ignore_events:
			return
		self.on_checkbutton_toggled(widget, 'autoconnect',
			account=self.current_account)

	def on_autoreconnect_checkbutton_toggled(self, widget):
		if self.ignore_events:
			return
		self.on_checkbutton_toggled(widget, 'autoreconnect',
			account=self.current_account)

	def on_log_history_checkbutton_toggled(self, widget):
		if self.ignore_events:
			return
		list_no_log_for = gajim.config.get_per('accounts', self.current_account,
			'no_log_for').split()
		if self.current_account in list_no_log_for:
			list_no_log_for.remove(self.current_account)
		if not self.xml.get_widget('log_history_checkbutton').get_active():
			list_no_log_for.append(self.current_account)
		gajim.config.set_per('accounts', self.current_account, 'no_log_for',
			' '.join(list_no_log_for))

	def on_sync_with_global_status_checkbutton_toggled(self, widget):
		if self.ignore_events:
			return
		self.on_checkbutton_toggled(widget, 'sync_with_global_status',
			account=self.current_account)
		gajim.interface.roster.update_status_combobox()

	def on_use_ft_proxies_checkbutton1_toggled(self, widget):
		if self.ignore_events:
			return
		self.on_checkbutton_toggled(widget, 'use_ft_proxies',
			account=self.current_account)

	def on_proxies_combobox1_changed(self, widget):
		active = widget.get_active()
		proxy = widget.get_model()[active][0].decode('utf-8')
		if proxy == _('None'):
			proxy = ''

		if self.option_changed('proxy', proxy):
			self.need_relogin = True

		gajim.config.set_per('accounts', self.current_account, 'proxy', proxy)

	def on_manage_proxies_button1_clicked(self, widget):
		if gajim.interface.instances.has_key('manage_proxies'):
			gajim.interface.instances['manage_proxies'].window.present()
		else:
			gajim.interface.instances['manage_proxies'] = ManageProxiesWindow()

	def on_use_ssl_checkbutton1_toggled(self, widget):
		if self.ignore_events:
			return

		if self.option_changed('usessl', widget.get_active()):
			self.need_relogin = True

		isactive = widget.get_active()
		if isactive:
			self.xml.get_widget('custom_port_entry1').set_text('5223')
		else:
			self.xml.get_widget('custom_port_entry1').set_text('5222')

		self.on_checkbutton_toggled(widget, 'usessl',
			account=self.current_account)

	def on_send_keepalive_checkbutton1_toggled(self, widget):
		if self.ignore_events:
			return
		self.on_checkbutton_toggled(widget, 'keep_alives_enabled',
			account=self.current_account)

	def on_custom_host_port_checkbutton1_toggled(self, widget):
		if self.option_changed('use_custom_host', widget.get_active()):
			self.need_relogin = True

		self.on_checkbutton_toggled(widget, 'use_custom_host',
			account=self.current_account)
		active = widget.get_active()
		self.xml.get_widget('custom_host_port_hbox1').set_sensitive(active)

	def on_custom_host_entry1_changed(self, widget):
		if self.ignore_events:
			return
		host = widget.get_text().decode('utf-8')
		if self.option_changed('custom_host', host):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account, 'custom_host',
			host)

	def on_custom_port_entry_focus_out_event(self, widget, event):
		if self.ignore_events:
			return
		custom_port = widget.get_text()
		try:
			custom_port = int(custom_port)
		except:
			if not widget.is_focus():
				dialogs.ErrorDialog(_('Invalid entry'),
					_('Custom port must be a port number.'))
				gobject.idle_add(lambda: widget.grab_focus())
			return True
		if self.option_changed('custom_port', custom_port):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account, 'custom_port',
			custom_port)

	def on_gpg_choose_button_clicked(self, widget, data = None):
		if gajim.connections.has_key(self.current_account):
			secret_keys = gajim.connections[self.current_account].\
				ask_gpg_secrete_keys()

		# self.current_account is None and/or gajim.connections is {}
		else:
			from common import GnuPG
			if GnuPG.USE_GPG:
				secret_keys = GnuPG.GnuPG().get_secret_keys()
			else:
				secret_keys = []
		if not secret_keys:
			dialogs.ErrorDialog(_('Failed to get secret keys'),
				_('There was a problem retrieving your OpenPGP secret keys.'))
			return
		secret_keys[_('None')] = _('None')
		instance = dialogs.ChooseGPGKeyDialog(_('OpenPGP Key Selection'),
			_('Choose your OpenPGP key'), secret_keys)
		keyID = instance.run()
		if keyID is None:
			return
		if self.current_account == gajim.ZEROCONF_ACC_NAME:
			wiget_name_ext = '2'
		else:
			wiget_name_ext = '1'
		gpg_key_label = self.xml.get_widget('gpg_key_label' + wiget_name_ext)
		gpg_name_label = self.xml.get_widget('gpg_name_label' + wiget_name_ext)
		use_gpg_agent_checkbutton = self.xml.get_widget(
			'use_gpg_agent_checkbutton' + wiget_name_ext)
		if keyID[0] == _('None'):
			gpg_key_label.set_text(_('No key selected'))
			gpg_name_label.set_text('')
			use_gpg_agent_checkbutton.set_sensitive(False)
			if self.option_changed('keyid', ''):
				self.need_relogin = True
			gajim.config.set_per('accounts', self.current_account, 'keyname', '')
			gajim.config.set_per('accounts', self.current_account, 'keyid', '')
		else:
			gpg_key_label.set_text(keyID[0])
			gpg_name_label.set_text(keyID[1])
			use_gpg_agent_checkbutton.set_sensitive(True)
			if self.option_changed('keyid', keyID[0]):
				self.need_relogin = True
			gajim.config.set_per('accounts', self.current_account, 'keyname',
				keyID[1])
			gajim.config.set_per('accounts', self.current_account, 'keyid',
				keyID[0])

	def on_use_gpg_agent_checkbutton_toggled(self, widget):
		if self.current_account == gajim.ZEROCONF_ACC_NAME:
			wiget_name_ext = '2'
		else:
			wiget_name_ext = '1'
		self.on_checkbutton_toggled(widget, 'use_gpg_agent')

	def on_edit_details_button1_clicked(self, widget):
		if not gajim.interface.instances.has_key(self.current_account):
			dialogs.ErrorDialog(_('No such account available'),
				_('You must create your account before editing your personal '
				'information.'))
			return

		# show error dialog if account is newly created (not in gajim.connections)
		if not gajim.connections.has_key(self.current_account) or \
		gajim.connections[self.current_account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
			_('Without a connection, you can not edit your personal information.'))
			return

		if not gajim.connections[self.current_account].vcard_supported:
			dialogs.ErrorDialog(_("Your server doesn't support Vcard"),
			_("Your server can't save your personal information."))
			return

		gajim.interface.edit_own_details(self.current_account)

	def on_checkbutton_toggled(self, widget, config_name,
		change_sensitivity_widgets = None, account = None):
		if account:
			gajim.config.set_per('accounts', account, config_name,
				widget.get_active())
		else:
			gajim.config.set(config_name, widget.get_active())
		if change_sensitivity_widgets:
			for w in change_sensitivity_widgets:
				w.set_sensitive(widget.get_active())
		gajim.interface.save_config()

	def on_merge_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'mergeaccounts')
		if len(gajim.connections) >= 2: # Do not merge accounts if only one exists
			gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
		else:
			gajim.interface.roster.regroup = False
		gajim.interface.roster.draw_roster()

	def on_enable_zeroconf_checkbutton2_toggled(self, widget):
		# don't do anything if there is an account with the local name but is a 
		# normal account
		if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME) and not \
		gajim.connections[gajim.ZEROCONF_ACC_NAME].is_zeroconf:
			gajim.connections[gajim.ZEROCONF_ACC_NAME].dispatch('ERROR',
				(_('Account Local already exists.'),
				_('Please rename or remove it before enabling link-local messaging'
				'.')))
			return

		if gajim.config.get('enable_zeroconf') and not widget.get_active():
			self.xml.get_widget('zeroconf_notebook').set_sensitive(False)
			# disable
			gajim.interface.roster.close_all(gajim.ZEROCONF_ACC_NAME)
			gajim.connections[gajim.ZEROCONF_ACC_NAME].disable_account()
			del gajim.connections[gajim.ZEROCONF_ACC_NAME]
			gajim.interface.save_config()
			del gajim.interface.instances[gajim.ZEROCONF_ACC_NAME]
			del gajim.interface.minimized_controls[gajim.ZEROCONF_ACC_NAME]
			del gajim.nicks[gajim.ZEROCONF_ACC_NAME]
			del gajim.block_signed_in_notifications[gajim.ZEROCONF_ACC_NAME]
			del gajim.groups[gajim.ZEROCONF_ACC_NAME]
			gajim.contacts.remove_account(gajim.ZEROCONF_ACC_NAME)
			del gajim.gc_connected[gajim.ZEROCONF_ACC_NAME]
			del gajim.automatic_rooms[gajim.ZEROCONF_ACC_NAME]
			del gajim.to_be_removed[gajim.ZEROCONF_ACC_NAME]
			del gajim.newly_added[gajim.ZEROCONF_ACC_NAME]
			del gajim.sleeper_state[gajim.ZEROCONF_ACC_NAME]
			del gajim.encrypted_chats[gajim.ZEROCONF_ACC_NAME]
			del gajim.last_message_time[gajim.ZEROCONF_ACC_NAME]
			del gajim.status_before_autoaway[gajim.ZEROCONF_ACC_NAME]
			del gajim.transport_avatar[gajim.ZEROCONF_ACC_NAME]
			if len(gajim.connections) >= 2:
				# Do not merge accounts if only one exists
				gajim.interface.roster.regroup = gajim.config.get('mergeaccounts') 
			else: 
				gajim.interface.roster.regroup = False
			gajim.interface.roster.draw_roster()
			gajim.interface.roster.set_actions_menu_needs_rebuild()

		elif not gajim.config.get('enable_zeroconf') and widget.get_active():
			self.xml.get_widget('zeroconf_notebook').set_sensitive(True)
			# enable (will create new account if not present)
			gajim.connections[gajim.ZEROCONF_ACC_NAME] = common.zeroconf.\
				connection_zeroconf.ConnectionZeroconf(gajim.ZEROCONF_ACC_NAME)
			if gajim.connections[gajim.ZEROCONF_ACC_NAME].gpg:
				self.xml.get_widget('gpg_choose_button2').set_sensitive(True)
			self.init_account_gpg()
			# update variables
			gajim.interface.instances[gajim.ZEROCONF_ACC_NAME] = {'infos': {},
				'disco': {}, 'gc_config': {}, 'search': {}}
			gajim.interface.minimized_controls[gajim.ZEROCONF_ACC_NAME] = {}
			gajim.connections[gajim.ZEROCONF_ACC_NAME].connected = 0
			gajim.groups[gajim.ZEROCONF_ACC_NAME] = {}
			gajim.contacts.add_account(gajim.ZEROCONF_ACC_NAME)
			gajim.gc_connected[gajim.ZEROCONF_ACC_NAME] = {}
			gajim.automatic_rooms[gajim.ZEROCONF_ACC_NAME] = {}
			gajim.newly_added[gajim.ZEROCONF_ACC_NAME] = []
			gajim.to_be_removed[gajim.ZEROCONF_ACC_NAME] = []
			gajim.nicks[gajim.ZEROCONF_ACC_NAME] = gajim.ZEROCONF_ACC_NAME
			gajim.block_signed_in_notifications[gajim.ZEROCONF_ACC_NAME] = True
			gajim.sleeper_state[gajim.ZEROCONF_ACC_NAME] = 'off'
			gajim.encrypted_chats[gajim.ZEROCONF_ACC_NAME] = []
			gajim.last_message_time[gajim.ZEROCONF_ACC_NAME] = {}
			gajim.status_before_autoaway[gajim.ZEROCONF_ACC_NAME] = ''
			gajim.transport_avatar[gajim.ZEROCONF_ACC_NAME] = {}
			# refresh roster
			if len(gajim.connections) >= 2:
				# Do not merge accounts if only one exists
				gajim.interface.roster.regroup = gajim.config.get('mergeaccounts') 
			else: 
				gajim.interface.roster.regroup = False
			gajim.interface.roster.draw_roster()
			gajim.interface.roster.set_actions_menu_needs_rebuild()
			gajim.interface.save_config()

		self.on_checkbutton_toggled(widget, 'enable_zeroconf')

	def on_custom_port_checkbutton2_toggled(self, widget):
		self.xml.get_widget('custom_port_entry2').set_sensitive(
			widget.get_active())
		self.on_checkbutton_toggled(widget, 'use_custom_host',
			account = self.current_account)
		if not widget.get_active():
			self.xml.get_widget('custom_port_entry2').set_text('5298')

	def on_first_name_entry2_changed(self, widget):
		if self.ignore_events:
			return
		name = widget.get_text().decode('utf-8')
		if self.option_changed('zeroconf_first_name', name):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account,
			'zeroconf_first_name', name)

	def on_last_name_entry2_changed(self, widget):
		if self.ignore_events:
			return
		name = widget.get_text().decode('utf-8')
		if self.option_changed('zeroconf_last_name', name):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account,
			'zeroconf_last_name', name)

	def on_jabber_id_entry2_changed(self, widget):
		if self.ignore_events:
			return
		id = widget.get_text().decode('utf-8')
		if self.option_changed('zeroconf_jabber_id', id):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account,
			'zeroconf_jabber_id', id)

	def on_email_entry2_changed(self, widget):
		if self.ignore_events:
			return
		email = widget.get_text().decode('utf-8')
		if self.option_changed('zeroconf_email', email):
			self.need_relogin = True
		gajim.config.set_per('accounts', self.current_account,
			'zeroconf_email', email)

class FakeDataForm(gtk.Table, object):
	'''Class for forms that are in XML format <entry1>value1</entry1>
	infos in a table {entry1: value1, }'''
	def __init__(self, infos):
		gtk.Table.__init__(self)
		self.infos = infos
		self.entries = {}
		self._draw_table()

	def _draw_table(self):
		'''Draw the table'''
		nbrow = 0
		if self.infos.has_key('instructions'):
			nbrow = 1
			self.resize(rows = nbrow, columns = 2)
			label = gtk.Label(self.infos['instructions'])
			self.attach(label, 0, 2, 0, 1, 0, 0, 0, 0)
		for name in self.infos.keys():
			if name in ('key', 'instructions', 'x', 'registered'):
				continue
			if not name:
				continue

			nbrow = nbrow + 1
			self.resize(rows = nbrow, columns = 2)
			label = gtk.Label(name.capitalize() + ':')
			self.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
			entry = gtk.Entry()
			entry.set_activates_default(True)
			if self.infos[name]:
				entry.set_text(self.infos[name])
			if name == 'password':
				entry.set_visibility(False)
			self.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
			self.entries[name] = entry
			if nbrow == 1:
				entry.grab_focus()

	def get_infos(self):
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text().decode('utf-8')
		return self.infos

class ServiceRegistrationWindow:
	'''Class for Service registration window:
	Window that appears when we want to subscribe to a service
	if is_form we use dataforms_widget else we use service_registarion_window'''
	def __init__(self, service, infos, account, is_form):
		self.service = service
		self.account = account
		self.is_form = is_form
		self.xml = gtkgui_helpers.get_glade('service_registration_window.glade')
		self.window = self.xml.get_widget('service_registration_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		if self.is_form:
			dataform = dataforms.ExtendForm(node = infos)
			self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
			if self.data_form_widget.title:
				self.window.set_title('%s - Gajim' % self.data_form_widget.title)
			table = self.xml.get_widget('table')
			table.attach(self.data_form_widget, 0, 2, 0, 1)
		else:
			if infos.has_key('registered'):
				self.window.set_title(_('Edit %s') % service)
			else:
				self.window.set_title(_('Register to %s') % service)
			self.data_form_widget = FakeDataForm(infos)
			table = self.xml.get_widget('table')
			table.attach(self.data_form_widget, 0, 2, 0, 1)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_ok_button_clicked(self, widget):
		# send registration info to the core
		if self.is_form:
			form = self.data_form_widget.data_form
			gajim.connections[self.account].register_agent(self.service,
				form, True) # True is for is_form
		else:
			infos = self.data_form_widget.get_infos()
			if infos.has_key('instructions'):
				del infos['instructions']
			if infos.has_key('registered'):
				del infos['registered']
			gajim.connections[self.account].register_agent(self.service, infos)

		self.window.destroy()

class GroupchatConfigWindow:
	'''GroupchatConfigWindow class'''
	def __init__(self, account, room_jid, form = None):
		self.account = account
		self.room_jid = room_jid
		self.form = form
		self.remove_button = {}
		self.affiliation_treeview = {}
		self.list_init = {} # list at the beginning
		ui_list = {'outcast': _('Ban List'),
			'member': _('Member List'),
			'owner': _('Owner List'),
			'admin':_('Administrator List')}

		self.xml = gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_window')
		self.window = self.xml.get_widget('data_form_window')
		self.window.set_transient_for(gajim.interface.roster.window)

		if self.form:
			config_vbox = self.xml.get_widget('config_vbox')
			dataform = dataforms.ExtendForm(node = self.form)
			self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
			# hide scrollbar of this data_form_widget, we already have in this
			# widget
			sw = self.data_form_widget.xml.get_widget('single_form_scrolledwindow')
			sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)

			self.data_form_widget.show()
			config_vbox.pack_start(self.data_form_widget)

		# Draw the edit affiliation list things
		add_on_vbox = self.xml.get_widget('add_on_vbox')

		for affiliation in ('outcast', 'member', 'owner', 'admin'):
			self.list_init[affiliation] = {}
			hbox = gtk.HBox(spacing = 5)
			add_on_vbox.pack_start(hbox, False)

			label = gtk.Label(ui_list[affiliation])
			hbox.pack_start(label, False)

			bb = gtk.HButtonBox()
			bb.set_layout(gtk.BUTTONBOX_END)
			bb.set_spacing(5)
			hbox.pack_start(bb)
			add_button = gtk.Button(stock = gtk.STOCK_ADD)
			add_button.connect('clicked', self.on_add_button_clicked, affiliation)
			bb.pack_start(add_button)
			self.remove_button[affiliation] = gtk.Button(stock = gtk.STOCK_REMOVE)
			self.remove_button[affiliation].set_sensitive(False)
			self.remove_button[affiliation].connect('clicked',
				self.on_remove_button_clicked, affiliation)
			bb.pack_start(self.remove_button[affiliation])

			liststore = gtk.ListStore(str, str, str, str) # Jid, reason, nick, role
			self.affiliation_treeview[affiliation] = gtk.TreeView(liststore)
			self.affiliation_treeview[affiliation].get_selection().set_mode(
				gtk.SELECTION_MULTIPLE)
			self.affiliation_treeview[affiliation].connect('cursor-changed',
				self.on_affiliation_treeview_cursor_changed, affiliation)
			renderer = gtk.CellRendererText()
			col = gtk.TreeViewColumn(_('JID'), renderer)
			col.add_attribute(renderer, 'text', 0)
			self.affiliation_treeview[affiliation].append_column(col)

			if affiliation == 'outcast':
				renderer = gtk.CellRendererText()
				renderer.set_property('editable', True)
				renderer.connect('edited', self.on_cell_edited)
				col = gtk.TreeViewColumn(_('Reason'), renderer)
				col.add_attribute(renderer, 'text', 1)
				self.affiliation_treeview[affiliation].append_column(col)
			elif affiliation == 'member':
				renderer = gtk.CellRendererText()
				col = gtk.TreeViewColumn(_('Nick'), renderer)
				col.add_attribute(renderer, 'text', 2)
				self.affiliation_treeview[affiliation].append_column(col)
				renderer = gtk.CellRendererText()
				col = gtk.TreeViewColumn(_('Role'), renderer)
				col.add_attribute(renderer, 'text', 3)
				self.affiliation_treeview[affiliation].append_column(col)

			sw = gtk.ScrolledWindow()
			sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
			sw.add(self.affiliation_treeview[affiliation])
			add_on_vbox.pack_start(sw)
			gajim.connections[self.account].get_affiliation_list(self.room_jid,
				affiliation)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_cell_edited(self, cell, path, new_text):
		model = self.affiliation_treeview['outcast'].get_model()
		new_text = new_text.decode('utf-8')
		iter = model.get_iter(path)
		model[iter][1] = new_text

	def on_add_button_clicked(self, widget, affiliation):
		if affiliation == 'outcast':
			title = _('Banning...')
			#You can move '\n' before user@domain if that line is TOO BIG
			prompt = _('<b>Whom do you want to ban?</b>\n\n')
		elif affiliation == 'member':
			title = _('Adding Member...')
			prompt = _('<b>Whom do you want to make a member?</b>\n\n')
		elif affiliation == 'owner':
			title = _('Adding Owner...')
			prompt = _('<b>Whom do you want to make an owner?</b>\n\n')
		else:
			title = _('Adding Administrator...')
			prompt = _('<b>Whom do you want to make an administrator?</b>\n\n')
		prompt += _('Can be one of the following:\n'
				'1. user@domain/resource (only that resource matches).\n'
				'2. user@domain (any resource matches).\n'
				'3. domain/resource (only that resource matches).\n'
				'4. domain (the domain itself matches, as does any user@domain,\n'
				'domain/resource, or address containing a subdomain.')
			
		instance = dialogs.InputDialog(title, prompt)
		response = instance.get_response()
		if response != gtk.RESPONSE_OK:
			return
		jid = instance.input_entry.get_text().decode('utf-8')
		if not jid:
			return
		model = self.affiliation_treeview[affiliation].get_model()
		model.append((jid,'', '', ''))

	def on_remove_button_clicked(self, widget, affiliation):
		selection = self.affiliation_treeview[affiliation].get_selection()
		model, paths = selection.get_selected_rows()
		row_refs = []
		for path in paths:
			row_refs.append(gtk.TreeRowReference(model, path))
		for row_ref in row_refs:
			path = row_ref.get_path()
			iter = model.get_iter(path)
			jid = model[iter][0]
			model.remove(iter)
		self.remove_button[affiliation].set_sensitive(False)

	def on_affiliation_treeview_cursor_changed(self, widget, affiliation):
		self.remove_button[affiliation].set_sensitive(True)

	def affiliation_list_received(self, affiliation, list):
		'''Fill the affiliation treeview'''
		self.list_init[affiliation] = list
		if not affiliation:
			return
		tv = self.affiliation_treeview[affiliation]
		model = tv.get_model()
		for jid in list:
			reason = ''
			if list[jid].has_key('reason'):
				reason = list[jid]['reason']
			nick = ''
			if list[jid].has_key('nick'):
				nick = list[jid]['nick']
			role = ''
			if list[jid].has_key('role'):
				role = list[jid]['role']
			model.append((jid,reason, nick, role))

	def on_data_form_window_destroy(self, widget):
		del gajim.interface.instances[self.account]['gc_config'][self.room_jid]

	def on_ok_button_clicked(self, widget):
		if self.form:
			form = self.data_form_widget.data_form
			gajim.connections[self.account].send_gc_config(self.room_jid, form)
		for affiliation in ('outcast', 'member', 'owner', 'admin'):
			list = {}
			actual_jid_list = []
			model = self.affiliation_treeview[affiliation].get_model()
			iter = model.get_iter_first()
			# add new jid
			while iter:
				jid = model[iter][0].decode('utf-8')
				actual_jid_list.append(jid)
				if jid not in self.list_init[affiliation] or \
				(affiliation == 'outcast' and self.list_init[affiliation]\
				[jid].has_key('reason') and self.list_init[affiliation][jid]\
				['reason'] != model[iter][1].decode('utf-8')):
					list[jid] = {'affiliation': affiliation}
					if affiliation == 'outcast':
						list[jid]['reason'] = model[iter][1].decode('utf-8')
				iter = model.iter_next(iter)
			# remove removed one
			for jid in self.list_init[affiliation]:
				if jid not in actual_jid_list:
					list[jid] = {'affiliation': 'none'}
			if list:
				gajim.connections[self.account].send_gc_affiliation_list(
					self.room_jid, list)
		self.window.destroy()

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
	'''ask for removing from gajim only or from gajim and server too
	and do removing of the account given'''

	def on_remove_account_window_destroy(self, widget):
		if gajim.interface.instances.has_key(self.account):
			del gajim.interface.instances[self.account]['remove_account']

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, account):
		self.account = account
		xml = gtkgui_helpers.get_glade('remove_account_window.glade')
		self.window = xml.get_widget('remove_account_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.remove_and_unregister_radiobutton = xml.get_widget(
			'remove_and_unregister_radiobutton')
		self.window.set_title(_('Removing %s account') % self.account)
		xml.signal_autoconnect(self)
		self.window.show_all()

	def on_remove_button_clicked(self, widget):
		def remove():
			if gajim.connections[self.account].connected and \
			not self.remove_and_unregister_radiobutton.get_active():
				# change status to offline only if we will not remove this JID from
				# server
				gajim.connections[self.account].change_status('offline', 'offline')
			if self.remove_and_unregister_radiobutton.get_active():
				if not gajim.connections[self.account].password:
					passphrase = ''
					w = dialogs.PassphraseDialog(
						_('Password Required'),
						_('Enter your password for account %s') % self.account,
						_('Save password'))
					passphrase, save = w.run()
					if passphrase == -1:
						# We don't remove account cause we canceled pw window
						return
					gajim.connections[self.account].password = passphrase
				gajim.connections[self.account].unregister_account(
					self._on_remove_success)
			else:
				self._on_remove_success(True)

		if gajim.connections[self.account].connected:
			dialog = dialogs.ConfirmationDialog(
				_('Account "%s" is connected to the server') % self.account,
				_('If you remove it, the connection will be lost.'),
				on_response_ok = remove)
		else:
			remove()
	
	def _on_remove_success(self, res):
		# action of unregistration has failed, we don't remove the account
		# Error message is send by connect_and_auth()
		if not res:
			return
		# Close all opened windows
		gajim.interface.roster.close_all(self.account, force = True)
		gajim.connections[self.account].disconnect(on_purpose = True)
		del gajim.connections[self.account]
		gajim.config.del_per('accounts', self.account)
		gajim.interface.save_config()
		del gajim.interface.instances[self.account]
		del gajim.interface.minimized_controls[self.account]
		del gajim.nicks[self.account]
		del gajim.block_signed_in_notifications[self.account]
		del gajim.groups[self.account]
		gajim.contacts.remove_account(self.account)
		del gajim.gc_connected[self.account]
		del gajim.automatic_rooms[self.account]
		del gajim.to_be_removed[self.account]
		del gajim.newly_added[self.account]
		del gajim.sleeper_state[self.account]
		del gajim.encrypted_chats[self.account]
		del gajim.last_message_time[self.account]
		del gajim.status_before_autoaway[self.account]
		del gajim.transport_avatar[self.account]
		if len(gajim.connections) >= 2: # Do not merge accounts if only one exists
			gajim.interface.roster.regroup = gajim.config.get('mergeaccounts') 
		else: 
			gajim.interface.roster.regroup = False
		gajim.interface.roster.draw_roster()
		gajim.interface.roster.set_actions_menu_needs_rebuild()
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].init_accounts()
		self.window.destroy()

#---------- ManageBookmarksWindow class -------------#
class ManageBookmarksWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('manage_bookmarks_window.glade')
		self.window = self.xml.get_widget('manage_bookmarks_window')
		self.window.set_transient_for(gajim.interface.roster.window)

		# Account-JID, RoomName, Room-JID, Autojoin, Minimize, Passowrd, Nick,
		# Show_Status
		self.treestore = gtk.TreeStore(str, str, str, bool, bool, str, str, str)

		# Store bookmarks in treeview.
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1:
				continue
			if gajim.connections[account].is_zeroconf:
				continue
			if not gajim.connections[account].private_storage_supported:
				continue
			iter = self.treestore.append(None, [None, account, None, None,
				None, None, None, None])

			for bookmark in gajim.connections[account].bookmarks:
				if bookmark['name'] == '':
					# No name was given for this bookmark.
					# Use the first part of JID instead...
					name = bookmark['jid'].split("@")[0]
					bookmark['name'] = name

				# make '1', '0', 'true', 'false' (or other) to True/False
				autojoin = helpers.from_xs_boolean_to_python_boolean(
					bookmark['autojoin'])

				minimize = helpers.from_xs_boolean_to_python_boolean(
					bookmark['minimize'])

				print_status = bookmark.get('print_status', '')
				if print_status not in ('', 'all', 'in_and_out', 'none'):
					print_status = ''
				self.treestore.append( iter, [
						account,
						bookmark['name'],
						bookmark['jid'],
						autojoin,
						minimize,
						bookmark['password'],
						bookmark['nick'],
						print_status ])

		self.print_status_combobox = self.xml.get_widget('print_status_combobox')
		model = gtk.ListStore(str, str)

		self.option_list = {'': _('Default'), 'all': Q_('?print_status:All'),
			'in_and_out': _('Enter and leave only'),
			'none': Q_('?print_status:None')}
		opts = self.option_list.keys()
		opts.sort()
		for opt in opts:
			model.append([self.option_list[opt], opt])

		self.print_status_combobox.set_model(model)
		self.print_status_combobox.set_active(1)

		self.view = self.xml.get_widget('bookmarks_treeview')
		self.view.set_model(self.treestore)
		self.view.expand_all()

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn('Bookmarks', renderer, text=1)
		self.view.append_column(column)

		self.selection = self.view.get_selection()
		self.selection.connect('changed', self.bookmark_selected)

		#Prepare input fields
		self.title_entry = self.xml.get_widget('title_entry')
		self.title_entry.connect('changed', self.on_title_entry_changed)
		self.nick_entry = self.xml.get_widget('nick_entry')
		self.nick_entry.connect('changed', self.on_nick_entry_changed)
		self.server_entry = self.xml.get_widget('server_entry')
		self.server_entry.connect('changed', self.on_server_entry_changed)
		self.room_entry = self.xml.get_widget('room_entry')
		self.room_entry.connect('changed', self.on_room_entry_changed)
		self.pass_entry = self.xml.get_widget('pass_entry')
		self.pass_entry.connect('changed', self.on_pass_entry_changed)
		self.autojoin_checkbutton = self.xml.get_widget('autojoin_checkbutton')
		self.minimize_checkbutton = self.xml.get_widget('minimize_checkbutton')

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_bookmarks_treeview_button_press_event(self, widget, event):
		(model, iter) = self.selection.get_selected()
		if not iter:
			# Removed a bookmark before
			return

		if model.iter_parent(iter):
			# The currently selected node is a bookmark
			return not self.check_valid_bookmark()

	def on_manage_bookmarks_window_destroy(self, widget, event):
		del gajim.interface.instances['manage_bookmarks']

	def on_add_bookmark_button_clicked(self, widget):
		'''Add a new bookmark.'''
		# Get the account that is currently used
		# (the parent of the currently selected item)
		(model, iter) = self.selection.get_selected()
		if not iter: # Nothing selected, do nothing
			return

		parent = model.iter_parent(iter)

		if parent:
			# We got a bookmark selected, so we add_to the parent
			add_to = parent
		else:
			# No parent, so we got an account -> add to this.
			add_to = iter

		account = model[add_to][1].decode('utf-8')
		nick = gajim.nicks[account]
		iter_ = self.treestore.append(add_to, [account, _('New Group Chat'), '',
			False, False, '', nick, 'in_and_out'])

		self.view.expand_row(model.get_path(add_to), True)
		self.view.set_cursor(model.get_path(iter_))

	def on_remove_bookmark_button_clicked(self, widget):
		'''
		Remove selected bookmark.
		'''
		(model, iter) = self.selection.get_selected()
		if not iter: # Nothing selected
			return

		if not model.iter_parent(iter):
			# Don't remove account iters
			return

		model.remove(iter)
		self.clear_fields()

	def check_valid_bookmark(self):
		'''
		Check if all neccessary fields are entered correctly.
		'''
		(model, iter) = self.selection.get_selected()

		if not model.iter_parent(iter):
			#Account data can't be changed
			return

		if self.server_entry.get_text().decode('utf-8') == '' or \
		self.room_entry.get_text().decode('utf-8') == '':
			dialogs.ErrorDialog(_('This bookmark has invalid data'),
				_('Please be sure to fill out server and room fields or remove this'
				' bookmark.'))
			return False

		return True

	def on_ok_button_clicked(self, widget):
		'''
		Parse the treestore data into our new bookmarks array,
		then send the new bookmarks to the server.
		'''
		(model, iter) = self.selection.get_selected()
		if iter and model.iter_parent(iter):
			#bookmark selected, check it
			if not self.check_valid_bookmark():
				return

		for account in self.treestore:
			account_unicode = account[1].decode('utf-8')
			gajim.connections[account_unicode].bookmarks = []

			for bm in account.iterchildren():
				#Convert True/False/None to '1' or '0'
				autojoin = unicode(int(bm[3]))
				minimize = unicode(int(bm[4]))

				#create the bookmark-dict
				bmdict = { 'name': bm[1], 'jid': bm[2], 'autojoin': autojoin,
					'minimize': minimize, 'password': bm[5], 'nick': bm[6],
					'print_status': bm[7]}

				gajim.connections[account_unicode].bookmarks.append(bmdict)

			gajim.connections[account_unicode].store_bookmarks()
		gajim.interface.roster.set_actions_menu_needs_rebuild()
		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def bookmark_selected(self, selection):
		'''
		Fill in the bookmark's data into the fields.
		'''
		(model, iter) = selection.get_selected()

		if not iter:
			# After removing the last bookmark for one account
			# this will be None, so we will just:
			return

		widgets = [ self.title_entry, self.nick_entry, self.room_entry,
			self.server_entry, self.pass_entry, self.autojoin_checkbutton,
			self.minimize_checkbutton, self.print_status_combobox]

		if model.iter_parent(iter):
			# make the fields sensitive
			for field in widgets:
				field.set_sensitive(True)
		else:
			# Top-level has no data (it's the account fields)
			# clear fields & make them insensitive
			self.clear_fields()
			for field in widgets:
				field.set_sensitive(False)
			return

		# Fill in the data for childs
		self.title_entry.set_text(model[iter][1])
		room_jid = model[iter][2].decode('utf-8')
		try:
			(room, server) = room_jid.split('@')
		except ValueError:
			# We just added this one
			room = ''
			server = ''
		self.room_entry.set_text(room)
		self.server_entry.set_text(server)

		self.autojoin_checkbutton.set_active(model[iter][3])
		self.minimize_checkbutton.set_active(model[iter][4])
		# sensitive only if auto join is checked
		self.minimize_checkbutton.set_sensitive(model[iter][3])

		if model[iter][5] is not None:
			password = model[iter][5].decode('utf-8')
		else:
			password = None

		if password:
			self.pass_entry.set_text(password)
		else:
			self.pass_entry.set_text('')
		nick = model[iter][6]
		if nick:
			nick = nick.decode('utf-8')
			self.nick_entry.set_text(nick)
		else:
			self.nick_entry.set_text('')

		print_status = model[iter][7]
		opts = self.option_list.keys()
		opts.sort()
		self.print_status_combobox.set_active(opts.index(print_status))

	def on_title_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter: # After removing a bookmark, we got nothing selected
			if model.iter_parent(iter):
				# Don't clear the title field for account nodes
				model[iter][1] = self.title_entry.get_text()

	def on_nick_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model[iter][6] = self.nick_entry.get_text()

	def on_server_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			room_jid = self.room_entry.get_text().decode('utf-8') + '@' + \
				self.server_entry.get_text().decode('utf-8')
			model[iter][2] = room_jid

	def on_room_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			room_jid = self.room_entry.get_text().decode('utf-8') + '@' + \
				self.server_entry.get_text().decode('utf-8')
			model[iter][2] = room_jid

	def on_pass_entry_changed(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model[iter][5] = self.pass_entry.get_text()

	def on_autojoin_checkbutton_toggled(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model[iter][3] = self.autojoin_checkbutton.get_active()
			self.minimize_checkbutton.set_sensitive(model[iter][3])

	def on_minimize_checkbutton_toggled(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model[iter][4] = self.minimize_checkbutton.get_active()

	def on_print_status_combobox_changed(self, widget):
		active = widget.get_active()
		model = widget.get_model()
		print_status = model[active][1]
		(model2, iter) = self.selection.get_selected()
		if iter:
			model2[iter][7] = print_status

	def clear_fields(self):
		widgets = [ self.title_entry, self.nick_entry, self.room_entry,
			self.server_entry, self.pass_entry ]
		for field in widgets:
			field.set_text('')
		self.autojoin_checkbutton.set_active(False)
		self.minimize_checkbutton.set_active(False)
		self.print_status_combobox.set_active(1)

class AccountCreationWizardWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade(
			'account_creation_wizard_window.glade')
		self.window = self.xml.get_widget('account_creation_wizard_window')

		completion = gtk.EntryCompletion()
		# Connect events from comboboxentry.child
		server_comboboxentry = self.xml.get_widget('server_comboboxentry')
		entry = server_comboboxentry.child
		entry.connect('key_press_event',
			self.on_server_comboboxentry_key_press_event, server_comboboxentry)
		entry.set_completion(completion)
		# Do the same for the other server comboboxentry
		server_comboboxentry1 = self.xml.get_widget('server_comboboxentry1')
		entry = server_comboboxentry1.child
		entry.connect('key_press_event',
			self.on_server_comboboxentry_key_press_event, server_comboboxentry1)
		entry.set_completion(completion)

		self.update_proxy_list()

		# parse servers.xml
		servers_xml = os.path.join(gajim.DATA_DIR, 'other', 'servers.xml')
		servers = gtkgui_helpers.parse_server_xml(servers_xml)
		servers_model = gtk.ListStore(str, int)
		for server in servers:
			if not server[2]['hidden']:
				servers_model.append((str(server[0]), int(server[1])))

		completion.set_model(servers_model)
		completion.set_text_column(0)

		# Put servers into comboboxentries
		server_comboboxentry.set_model(servers_model)
		server_comboboxentry.set_text_column(0)
		server_comboboxentry1.set_model(servers_model)
		server_comboboxentry1.set_text_column(0)

		# Generic widgets
		self.notebook = self.xml.get_widget('notebook')
		self.cancel_button = self.xml.get_widget('cancel_button')
		self.back_button = self.xml.get_widget('back_button')
		self.forward_button = self.xml.get_widget('forward_button')
		self.finish_button = self.xml.get_widget('finish_button')
		self.advanced_button = self.xml.get_widget('advanced_button')
		self.finish_label = self.xml.get_widget('finish_label')
		self.go_online_checkbutton = self.xml.get_widget(
			'go_online_checkbutton')
		self.show_vcard_checkbutton = self.xml.get_widget(
			'show_vcard_checkbutton')
		self.progressbar = self.xml.get_widget('progressbar')

		# some vars
		self.update_progressbar_timeout_id = None

		self.notebook.set_current_page(0)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_wizard_window_destroy(self, widget):
		page = self.notebook.get_current_page()
		if page in (4, 5) and self.account in gajim.connections:
			# connection instance is saved in gajim.connections and we canceled the
			# addition of the account
			del gajim.connections[self.account]
		del gajim.interface.instances['account_creation_wizard']

	def on_register_server_features_button_clicked(self, widget):
		helpers.launch_browser_mailer('url',
			'http://www.jabber.org/network/oldnetwork.shtml')

	def on_save_password_checkbutton_toggled(self, widget):
		self.xml.get_widget('password_entry').grab_focus()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_back_button_clicked(self, widget):
		cur_page = self.notebook.get_current_page()
		if cur_page in (1, 2):
			self.notebook.set_current_page(0)
			self.back_button.set_sensitive(False)
		elif cur_page == 3:
			self.xml.get_widget('form_vbox').remove(self.data_form_widget)
			self.notebook.set_current_page(2) # show server page
		elif cur_page == 4:
			if self.account in gajim.connections:
				del gajim.connections[self.account]
			self.notebook.set_current_page(2)
			self.xml.get_widget('form_vbox').remove(self.data_form_widget)
		elif cur_page == 6: # finish page
			self.forward_button.show()
			if self.modify:
				self.notebook.set_current_page(1) # Go to parameters page
			else:
				self.notebook.set_current_page(2) # Go to server page

	def on_forward_button_clicked(self, widget):
		cur_page = self.notebook.get_current_page()

		if cur_page == 0:
			widget = self.xml.get_widget('use_existing_account_radiobutton')
			if widget.get_active():
				self.modify = True
				self.notebook.set_current_page(1)
			else:
				self.modify = False
				self.notebook.set_current_page(2)
			self.back_button.set_sensitive(True)
			return

		elif cur_page == 1:
			# We are adding an existing account
			username = self.xml.get_widget('username_entry').get_text().decode(
				'utf-8')
			if not username:
				pritext = _('Invalid username')
				sectext = _(
					'You must provide a username to configure this account.')
				dialogs.ErrorDialog(pritext, sectext)
				return
			server = self.xml.get_widget('server_comboboxentry').child.get_text().\
				decode('utf-8')
			savepass = self.xml.get_widget('save_password_checkbutton').\
				get_active()
			password = self.xml.get_widget('password_entry').get_text().decode(
				'utf-8')

			jid = username + '@' + server
			# check if jid is conform to RFC and stringprep it
			try:
				jid = helpers.parse_jid(jid)
			except helpers.InvalidFormat, s:
				pritext = _('Invalid Jabber ID')
				dialogs.ErrorDialog(pritext, str(s))
				return

			already_in_jids = []
			for account in gajim.connections:
				j = gajim.config.get_per('accounts', account, 'name')
				j += '@' + gajim.config.get_per('accounts', account, 'hostname')
				already_in_jids.append(j)

			if jid in already_in_jids:
				pritext = _('Duplicate Jabber ID')
				sectext = _('This account is already configured in Gajim.')
				dialogs.ErrorDialog(pritext, sectext)
				return

			self.account = server
			i = 1
			while self.account in gajim.connections:
				self.account = server + str(i)
				i += 1

			username, server = gajim.get_name_and_server_from_jid(jid)
			self.save_account(username, server, savepass, password)
			self.cancel_button.hide()
			self.back_button.hide()
			self.forward_button.hide()
			if self.modify:
				finish_text = '<big><b>%s</b></big>\n\n%s' % (
				_('Account has been added successfully'),
				_('You can set advanced account options by pressing the '
				'Advanced button, or later by choosing the Accounts menuitem '
					'under the Edit menu from the main window.'))
			self.finish_label.set_markup(finish_text)
			self.finish_button.show()
			self.finish_button.set_property('has-default', True)
			self.advanced_button.show()
			self.go_online_checkbutton.show()
			img = self.xml.get_widget('finish_image')
			img.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_DIALOG)
			self.notebook.set_current_page(6) # show finish page
			self.show_vcard_checkbutton.set_active(False)
		elif cur_page == 2:
			# We are creating a new account
			server = self.xml.get_widget('server_comboboxentry1').child.get_text()\
				.decode('utf-8')

			if not server:
				dialogs.ErrorDialog(_('Invalid server'),
					_('Please provide a server on which you want to register.'))
				return
			self.account = server
			i = 1
			while self.account in gajim.connections:
				self.account = server + str(i)
				i += 1

			config = self.get_config('', server, '', '')
			# Get advanced options
			proxies_combobox = self.xml.get_widget('proxies_combobox')
			active = proxies_combobox.get_active()
			proxy = proxies_combobox.get_model()[active][0].decode('utf-8')
			if proxy == _('None'):
				proxy = ''
			config['proxy'] = proxy

			config['use_custom_host'] = self.xml.get_widget(
				'custom_host_port_checkbutton').get_active()
			custom_port = self.xml.get_widget('custom_port_entry').get_text()
			try:
				custom_port = int(custom_port)
			except:
				dialogs.ErrorDialog(_('Invalid entry'),
					_('Custom port must be a port number.'))
				return
			config['custom_port'] = custom_port
			config['custom_host'] = self.xml.get_widget(
				'custom_host_entry').get_text().decode('utf-8')

			self.notebook.set_current_page(5) # show creating page
			self.back_button.hide()
			self.forward_button.hide()
			self.update_progressbar_timeout_id = gobject.timeout_add(100,
				self.update_progressbar)
			# Get form from serveur
			con = connection.Connection(self.account)
			con.new_account(self.account, config)
			gajim.connections[self.account] = con
		elif cur_page == 3:
			checked = self.xml.get_widget('ssl_checkbutton').get_active()
			if checked:
				hostname = gajim.connections[self.account].new_account_info[
					'hostname']
				f = open(gajim.MY_CACERTS, 'a')
				f.write(hostname + '\n')
				f.write(self.ssl_cert + '\n\n')
				f.close()
				gajim.connections[self.account].new_account_info[
					'ssl_fingerprint_sha1'] = self.ssl_fingerprint
			self.notebook.set_current_page(4) # show fom page
		elif cur_page == 4:
			if self.is_form:
				form = self.data_form_widget.data_form
			else:
				form = self.data_form_widget.get_infos()
			gajim.connections[self.account].send_new_account_infos(form,
				self.is_form)
			self.xml.get_widget('form_vbox').remove(self.data_form_widget)
			self.xml.get_widget('progressbar_label').set_markup('<b>Account is being created</b>\n\nPlease wait...')
			self.notebook.set_current_page(5) # show creating page
			self.back_button.hide()
			self.forward_button.hide()
			self.update_progressbar_timeout_id = gobject.timeout_add(100,
				self.update_progressbar)

	def update_proxy_list(self):
		proxies_combobox = self.xml.get_widget('proxies_combobox')
		model = gtk.ListStore(str)
		proxies_combobox.set_model(model)
		l = gajim.config.get_per('proxies')
		l.insert(0, _('None'))
		for i in xrange(len(l)):
			model.append([l[i]])
		proxies_combobox.set_active(0)

	def on_manage_proxies_button_clicked(self, widget):
		if gajim.interface.instances.has_key('manage_proxies'):
			gajim.interface.instances['manage_proxies'].window.present()
		else:
			gajim.interface.instances['manage_proxies'] = \
				ManageProxiesWindow()

	def on_custom_host_port_checkbutton_toggled(self, widget):
		self.xml.get_widget('custom_host_hbox').set_sensitive(widget.get_active())

	def update_progressbar(self):
		self.progressbar.pulse()
		return True # loop forever

	def new_acc_connected(self, form, is_form, ssl_msg, ssl_cert,
	ssl_fingerprint):
		'''connection to server succeded, present the form to the user.'''
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
		self.back_button.show()
		self.forward_button.show()
		self.is_form = is_form
		if is_form:
			dataform = dataforms.ExtendForm(node = form)
			self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
		else:
			self.data_form_widget = FakeDataForm(form)
		self.data_form_widget.show_all()
		self.xml.get_widget('form_vbox').pack_start(self.data_form_widget)
		self.ssl_fingerprint = ssl_fingerprint
		self.ssl_cert = ssl_cert
		if ssl_msg:
			# An SSL warning occured, show it
			hostname = gajim.connections[self.account].new_account_info['hostname']
			self.xml.get_widget('ssl_label').set_markup(_('<b>Security Warning</b>'
				'\n\nThe authenticity of the %s SSL certificate could be invalid.\n'
				'SSL Error: %s\n'
				'Do you still want to connect to this server?') % (hostname,
				ssl_msg))
			text = _('Add this certificate to the list of trusted certificates.\nSHA1 fingerprint of the certificate:\n%s') % ssl_fingerprint
			self.xml.get_widget('ssl_checkbutton').set_label(text)
			self.notebook.set_current_page(3) # show SSL page
		else:
			self.notebook.set_current_page(4) # show form page

	def new_acc_not_connected(self, reason):
		'''Account creation failed: connection to server failed'''
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
		del gajim.connections[self.account]
		self.back_button.show()
		self.cancel_button.show()
		self.go_online_checkbutton.hide()
		self.show_vcard_checkbutton.hide()
		img = self.xml.get_widget('finish_image')
		img.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG)
		finish_text = '<big><b>%s</b></big>\n\n%s' % (
			_('An error occurred during account creation') , reason)
		self.finish_label.set_markup(finish_text)
		self.notebook.set_current_page(6) # show finish page

	def acc_is_ok(self, config):
		'''Account creation succeeded'''
		self.create_vars(config)
		self.cancel_button.hide()
		self.back_button.hide()
		self.forward_button.hide()
		self.finish_button.show()
		self.finish_button.set_property('has-default', True)
		self.advanced_button.show()
		self.go_online_checkbutton.show()
		self.show_vcard_checkbutton.show()
		img = self.xml.get_widget('finish_image')
		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps', 'gajim.png')
		img.set_from_file(path_to_file)

		finish_text = '<big><b>%s</b></big>\n\n%s' % (
			_('Your new account has been created successfully'),
			_('You can set advanced account options by pressing the Advanced '
			'button, or later by choosing the Accounts menuitem under the Edit '
			'menu from the main window.'))
		self.finish_label.set_markup(finish_text)
		self.notebook.set_current_page(6) # show finish page

		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)

	def acc_is_not_ok(self, reason):
		'''Account creation failed'''
		self.back_button.show()
		self.cancel_button.show()
		self.go_online_checkbutton.hide()
		self.show_vcard_checkbutton.hide()
		del gajim.connections[self.account]
		img = self.xml.get_widget('finish_image')
		img.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG)
		finish_text = '<big><b>%s</b></big>\n\n%s' % (_('An error occurred during '
			'account creation') , reason)
		self.finish_label.set_markup(finish_text)
		self.notebook.set_current_page(6) # show finish page

		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)

	def on_advanced_button_clicked(self, widget):
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = AccountsWindow()
		gajim.interface.instances['accounts'].select_account(
			self.account)
		self.window.destroy()

	def on_finish_button_clicked(self, widget):
		go_online = self.xml.get_widget('go_online_checkbutton').get_active()
		show_vcard = self.xml.get_widget('show_vcard_checkbutton').get_active()
		self.window.destroy()
		if show_vcard:
			gajim.interface.show_vcard_when_connect.append(self.account)
		if go_online:
			gajim.interface.roster.send_status(self.account, 'online', '')

	def on_username_entry_changed(self, widget):
		self.update_jid(widget)

	def on_server_comboboxentry_changed(self, widget):
		self.update_jid(widget)

	def on_username_entry_key_press_event(self, widget, event):
		# Check for pressed @ and jump to combobox if found
		if event.keyval == gtk.keysyms.at:
			combobox = self.xml.get_widget('server_comboboxentry')
			combobox.grab_focus()
			combobox.child.set_position(-1)
			return True

	def on_server_comboboxentry_key_press_event(self, widget, event, combobox):
		# If backspace is pressed in empty field, return to the nick entry field
		backspace = event.keyval == gtk.keysyms.BackSpace
		empty = len(combobox.get_active_text()) == 0
		if backspace and empty and self.modify:
			username_entry = self.xml.get_widget('username_entry')
			username_entry.grab_focus()
			username_entry.set_position(-1)
			return True

	def update_jid(self,widget):
		username_entry = self.xml.get_widget('username_entry')
		name = username_entry.get_text().decode('utf-8')
		combobox = self.xml.get_widget('server_comboboxentry')
		server = combobox.get_active_text()
		jid_label = self.xml.get_widget('jid_label')
		if len(name) == 0 or len(server) == 0:
			jid_label.set_label('')
		else:
			string = '<b>%s@%s</b>' % (name, server)
			jid_label.set_label(string)

	def get_config(self, login, server, savepass, password):
		config = {}
		config['name'] = login
		config['hostname'] = server
		config['savepass'] = savepass
		config['password'] = password
		config['resource'] = 'Gajim'
		config['priority'] = 5
		config['autoconnect'] = True
		config['no_log_for'] = ''
		config['sync_with_global_status'] = True
		config['proxy'] = ''
		config['usessl'] = False
		config['use_custom_host'] = False
		config['custom_port'] = 0
		config['custom_host'] = ''
		config['keyname'] = ''
		config['keyid'] = ''
		return config

	def save_account(self, login, server, savepass, password):
		if self.account in gajim.connections:
			dialogs.ErrorDialog(_('Account name is in use'),
				_('You already have an account using this name.'))
			return
		con = connection.Connection(self.account)
		con.password = password

		config = self.get_config(login, server, savepass, password)

		if not self.modify:
			con.new_account(self.account, config)
			return
		gajim.connections[self.account] = con
		self.create_vars(config)

	def create_vars(self, config):
		gajim.config.add_per('accounts', self.account)

		if not config['savepass']:
			config['password'] = ''

		for opt in config:
			gajim.config.set_per('accounts', self.account, opt, config[opt])

		# update variables
		gajim.interface.instances[self.account] = {'infos': {}, 'disco': {},
			'gc_config': {}, 'search': {}}
		gajim.interface.minimized_controls[self.account] = {}
		gajim.connections[self.account].connected = 0
		gajim.groups[self.account] = {}
		gajim.contacts.add_account(self.account)
		gajim.gc_connected[self.account] = {}
		gajim.automatic_rooms[self.account] = {}
		gajim.newly_added[self.account] = []
		gajim.to_be_removed[self.account] = []
		gajim.nicks[self.account] = config['name']
		gajim.block_signed_in_notifications[self.account] = True
		gajim.sleeper_state[self.account] = 'off'
		gajim.encrypted_chats[self.account] = []
		gajim.last_message_time[self.account] = {}
		gajim.status_before_autoaway[self.account] = ''
		gajim.transport_avatar[self.account] = {}
		# refresh accounts window
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].init_accounts()
		# refresh roster
		if len(gajim.connections) >= 2: # Do not merge accounts if only one exists
			gajim.interface.roster.regroup = gajim.config.get('mergeaccounts') 
		else: 
			gajim.interface.roster.regroup = False
		gajim.interface.roster.draw_roster()
		gajim.interface.roster.set_actions_menu_needs_rebuild()
		gajim.interface.save_config()

#---------- ZeroconfPropertiesWindow class -------------#
class ZeroconfPropertiesWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('zeroconf_properties_window.glade')
		self.window = self.xml.get_widget('zeroconf_properties_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.xml.signal_autoconnect(self)

		self.init_account()
		self.init_account_gpg()

		self.xml.get_widget('save_button').grab_focus()
		self.window.show_all()
	
	def init_account(self):
		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'autoconnect')
		if st:
			self.xml.get_widget('autoconnect_checkbutton').set_active(st)
		
		list_no_log_for = gajim.config.get_per('accounts',
			gajim.ZEROCONF_ACC_NAME,'no_log_for').split()
		if gajim.ZEROCONF_ACC_NAME in list_no_log_for:
			self.xml.get_widget('log_history_checkbutton').set_active(0)
		else:
			self.xml.get_widget('log_history_checkbutton').set_active(1)


		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'sync_with_global_status')
		if st:
			self.xml.get_widget('sync_with_global_status_checkbutton').set_active(
				st)

		for opt in ('first_name', 'last_name', 'jabber_id', 'email'):
			st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'zeroconf_' + opt)
			if st:
				self.xml.get_widget(opt + '_entry').set_text(st)

		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'custom_port')
		if st:
			self.xml.get_widget('custom_port_entry').set_text(str(st))
		
		st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'use_custom_host')
		if st:
			self.xml.get_widget('custom_port_checkbutton').set_active(st)
	
		self.xml.get_widget('custom_port_entry').set_sensitive(bool(st))

		if not st:
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
				'custom_port', '5298')

	def init_account_gpg(self):
		keyid = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'keyid')
		keyname = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'keyname')
		savegpgpass = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'savegpgpass')

		if not keyid or not gajim.config.get('usegpg'):
			return

		self.xml.get_widget('gpg_key_label').set_text(keyid)
		self.xml.get_widget('gpg_name_label').set_text(keyname)
		gpg_save_password_checkbutton = \
			self.xml.get_widget('gpg_save_password_checkbutton')
		gpg_save_password_checkbutton.set_sensitive(True)
		gpg_save_password_checkbutton.set_active(savegpgpass)

		if savegpgpass:
			entry = self.xml.get_widget('gpg_password_entry')
			entry.set_sensitive(True)
			gpgpassword = gajim.config.get_per('accounts',
						gajim.ZEROCONF_ACC_NAME, 'gpgpassword')
			entry.set_text(gpgpassword)

	def on_zeroconf_properties_window_destroy(self, widget):
		# close window
		if gajim.interface.instances.has_key('zeroconf_properties'):
			del gajim.interface.instances['zeroconf_properties']
	
	def on_custom_port_checkbutton_toggled(self, widget):
		st = self.xml.get_widget('custom_port_checkbutton').get_active()
		self.xml.get_widget('custom_port_entry').set_sensitive(bool(st))
	
	def on_cancel_button_clicked(self, widget):
		self.window.destroy()
	
	def on_save_button_clicked(self, widget):
		config = {}

		st = self.xml.get_widget('autoconnect_checkbutton').get_active()
		config['autoconnect'] = st
		list_no_log_for = gajim.config.get_per('accounts',
				gajim.ZEROCONF_ACC_NAME, 'no_log_for').split()
		if gajim.ZEROCONF_ACC_NAME in list_no_log_for:
			list_no_log_for.remove(gajim.ZEROCONF_ACC_NAME)
		if not self.xml.get_widget('log_history_checkbutton').get_active():
			list_no_log_for.append(gajim.ZEROCONF_ACC_NAME)
		config['no_log_for'] =  ' '.join(list_no_log_for)
		
		st = self.xml.get_widget('sync_with_global_status_checkbutton').\
			get_active()
		config['sync_with_global_status'] = st

		st = self.xml.get_widget('first_name_entry').get_text()
		config['zeroconf_first_name'] = st.decode('utf-8')
		
		st = self.xml.get_widget('last_name_entry').get_text()
		config['zeroconf_last_name'] = st.decode('utf-8')

		st = self.xml.get_widget('jabber_id_entry').get_text()
		config['zeroconf_jabber_id'] = st.decode('utf-8')

		st = self.xml.get_widget('email_entry').get_text()
		config['zeroconf_email'] = st.decode('utf-8')

		use_custom_port = self.xml.get_widget('custom_port_checkbutton').\
			get_active()
		config['use_custom_host'] = use_custom_port

		old_port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
			'custom_port')
		if use_custom_port:
			port = self.xml.get_widget('custom_port_entry').get_text()
		else:
			port = 5298
			
		config['custom_port'] = port
	
		config['keyname'] = self.xml.get_widget('gpg_name_label').get_text().\
			decode('utf-8')
		if config['keyname'] == '': # no key selected
			config['keyid'] = ''
			config['savegpgpass'] = False
			config['gpgpassword'] = ''
		else:
			config['keyid'] = self.xml.get_widget('gpg_key_label').get_text().\
				decode('utf-8')
			config['savegpgpass'] = self.xml.get_widget(
					'gpg_save_password_checkbutton').get_active()
			config['gpgpassword'] = self.xml.get_widget('gpg_password_entry'
				).get_text().decode('utf-8')

		reconnect = False
		for opt in ('zeroconf_first_name','zeroconf_last_name',
			'zeroconf_jabber_id', 'zeroconf_email', 'custom_port'):
			if gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, opt) != \
			config[opt]:
				reconnect = True

		for opt	in config:
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, opt,
				config[opt])

		if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME):
			if port != old_port or reconnect:
				gajim.connections[gajim.ZEROCONF_ACC_NAME].update_details()

		self.window.destroy()

	def on_gpg_choose_button_clicked(self, widget, data = None):
		if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME):
			secret_keys = gajim.connections[gajim.ZEROCONF_ACC_NAME].\
				ask_gpg_secrete_keys()

		# self.account is None and/or gajim.connections is {}
		else:
			from common import GnuPG
			if GnuPG.USE_GPG:
				secret_keys = GnuPG.GnuPG().get_secret_keys()
			else:
				secret_keys = []
		if not secret_keys:
			dialogs.ErrorDialog(_('Failed to get secret keys'),
				_('There was a problem retrieving your OpenPGP secret keys.'))
			return
		secret_keys[_('None')] = _('None')
		instance = dialogs.ChooseGPGKeyDialog(_('OpenPGP Key Selection'),
			_('Choose your OpenPGP key'), secret_keys)
		keyID = instance.run()
		if keyID is None:
			return
		checkbutton = self.xml.get_widget('gpg_save_password_checkbutton')
		gpg_key_label = self.xml.get_widget('gpg_key_label')
		gpg_name_label = self.xml.get_widget('gpg_name_label')
		if keyID[0] == _('None'):
			gpg_key_label.set_text(_('No key selected'))
			gpg_name_label.set_text('')
			checkbutton.set_sensitive(False)
			self.xml.get_widget('gpg_password_entry').set_sensitive(False)
		else:
			gpg_key_label.set_text(keyID[0])
			gpg_name_label.set_text(keyID[1])
			checkbutton.set_sensitive(True)
		checkbutton.set_active(False)
		self.xml.get_widget('gpg_password_entry').set_text('')

	def on_gpg_save_password_checkbutton_toggled(self, widget):
		st = widget.get_active()
		w = self.xml.get_widget('gpg_password_entry')
		w.set_sensitive(bool(st))

class ManagePEPServicesWindow:
	def __init__(self, account):
		self.xml = gtkgui_helpers.get_glade('manage_pep_services_window.glade')
		self.window = self.xml.get_widget('manage_pep_services_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.xml.signal_autoconnect(self)
		self.account = account

		self.init_services()
		self.window.show_all()

	def on_manage_pep_services_window_destroy(self, widget):
		'''close window'''
		del gajim.interface.instances[self.account]['pep_services']

	def on_ok_button_clicked(self, widget):
		pass

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def cellrenderer_combo_edited(self, cellrenderer, path, new_text):
		self.treestore[path][1] = new_text

	def init_services(self):
		treeview = self.xml.get_widget('services_treeview')
		# service, access_model, group
		self.treestore = gtk.ListStore(str, str, str)
		treeview.set_model(self.treestore)

		col = gtk.TreeViewColumn('Service')
		treeview.append_column(col)

		cellrenderer_text = gtk.CellRendererText()
		col.pack_start(cellrenderer_text)
		col.add_attribute(cellrenderer_text, 'text', 0)

		col = gtk.TreeViewColumn('access model')
		treeview.append_column(col)

		model = gtk.ListStore(str)
		model.append(['open'])
		model.append(['presence'])
		model.append(['roster'])
		model.append(['whitelist'])
		cellrenderer_combo = gtk.CellRendererCombo()
		cellrenderer_combo.set_property('text-column', 0)
		cellrenderer_combo.set_property('model', model)
		cellrenderer_combo.set_property('has-entry', False)
		cellrenderer_combo.set_property('editable', True)
		cellrenderer_combo.connect('edited', self.cellrenderer_combo_edited)
		col.pack_start(cellrenderer_combo)
		col.add_attribute(cellrenderer_combo, 'text', 1)

		our_jid = gajim.get_jid_from_account(self.account)
		gajim.connections[self.account].discoverItems(our_jid)

	def items_received(self, items):
		our_jid = gajim.get_jid_from_account(self.account)
		for item in items:
			if 'jid' in item and item['jid'] == our_jid and 'node' in item:
				# ask <configure> to have access model
				gajim.connections[self.account].request_pb_configuration(
					item['jid'], item['node'])

	def new_service(self, node, model):
		self.treestore.append([node, model, ''])
