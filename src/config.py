##	config.py
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2003-2005 Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

import gtk
import gobject
import os
import common.config
import common.sleepy
from common.i18n import Q_

import gtkgui_helpers
import dialogs
import cell_renderer_image
import message_control
import chat_control

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
		self.iconset_combobox = self.xml.get_widget('iconset_combobox')
		self.notify_on_new_message_radiobutton = self.xml.get_widget(
			'notify_on_new_message_radiobutton')
		self.popup_new_message_radiobutton = self.xml.get_widget(
			'popup_new_message_radiobutton')
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
		self.trayicon_checkbutton = self.xml.get_widget('trayicon_checkbutton')
		self.notebook = self.xml.get_widget('preferences_notebook')
		self.one_window_type_combobox =\
			self.xml.get_widget('one_window_type_combobox')
		self.treat_incoming_messages_combobox =\
			self.xml.get_widget('treat_incoming_messages_combobox')

		#FIXME: remove when ANC will be implemented
		w = self.xml.get_widget('hbox3020')
		w.set_no_show_all(True)
		w.hide()

		# trayicon
		if gajim.interface.systray_capabilities:
			st = gajim.config.get('trayicon')
			self.trayicon_checkbutton.set_active(st)
		else:
			self.trayicon_checkbutton.set_sensitive(False)

		# Save position
		st = gajim.config.get('saveposition')
		self.xml.get_widget('save_position_checkbutton').set_active(st)

		# Sort contacts by show
		st = gajim.config.get('sort_by_show')
		self.xml.get_widget('sort_by_show_checkbutton').set_active(st)

		# Display avatars in roster
		st = gajim.config.get('show_avatars_in_roster')
		self.xml.get_widget('show_avatars_in_roster_checkbutton').set_active(st)

		# Display status msg under contact name in roster
		st = gajim.config.get('show_status_msgs_in_roster')
		self.xml.get_widget('show_status_msgs_in_roster_checkbutton').set_active(
			st)

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

		# iconset
		iconsets_list = os.listdir(os.path.join(gajim.DATA_DIR, 'iconsets'))
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
			if not os.path.isdir(os.path.join(gajim.DATA_DIR, 'iconsets', dir)):
				continue
			if dir != '.svn' and dir != 'transports':
				l.append(dir)
		if l.count == 0:
			l.append(' ')
		for i in xrange(len(l)):
			preview = gtk.Image()
			files = []
			files.append(os.path.join(gajim.DATA_DIR, 'iconsets', l[i], '16x16',
				'online.png'))
			files.append(os.path.join(gajim.DATA_DIR, 'iconsets', l[i], '16x16',
				'online.gif'))
			for file in files:
				if os.path.exists(file):
					preview.set_from_file(file)
			model.append([preview, l[i]])
			if gajim.config.get('iconset') == l[i]:
				self.iconset_combobox.set_active(i)

		# Set default for single window type
		choices = common.config.opt_one_window_types
		type = gajim.config.get('one_message_window')
		if type in choices:
			self.one_window_type_combobox.set_active(choices.index(type))
		else:
			self.one_window_type_combobox.set_active(0)

		# Set default for treat incoming messages
		choices = common.config.opt_treat_incoming_messages
		type = gajim.config.get('treat_incoming_messages')
		if type in choices:
			self.treat_incoming_messages_combobox.set_active(choices.index(type))
		else:
			self.treat_incoming_messages_combobox.set_active(0)

		# Use transports iconsets
		st = gajim.config.get('use_transports_iconsets')
		self.xml.get_widget('transports_iconsets_checkbutton').set_active(st)

		# Themes
		theme_combobox = self.xml.get_widget('theme_combobox')
		cell = gtk.CellRendererText()
		theme_combobox.pack_start(cell, True)
		theme_combobox.add_attribute(cell, 'text', 0)
		model = gtk.ListStore(str)
		theme_combobox.set_model(model)

		i = 0
		for config_theme in gajim.config.get_per('themes'):
			theme = config_theme.replace('_', ' ')
			model.append([theme])
			if gajim.config.get('roster_theme') == config_theme:
				theme_combobox.set_active(i)
			i += 1

		# use speller
		if os.name == 'nt':
			self.xml.get_widget('speller_checkbutton').set_no_show_all(True)
		else:
			if HAS_GTK_SPELL:
				st = gajim.config.get('use_speller')
				self.xml.get_widget('speller_checkbutton').set_active(st)
			else:
				self.xml.get_widget('speller_checkbutton').set_sensitive(False)

		# Ignore XHTML
		st = gajim.config.get('ignore_incoming_xhtml')
		self.xml.get_widget('xhtml_checkbutton').set_active(st)

		# Print time
		st = gajim.config.get('print_ichat_every_foo_minutes')
		text = _('Every %s _minutes') % st
		self.xml.get_widget('time_sometimes_radiobutton').set_label(text)

		if gajim.config.get('print_time') == 'never':
			self.xml.get_widget('time_never_radiobutton').set_active(True)
		elif gajim.config.get('print_time') == 'sometimes':
			self.xml.get_widget('time_sometimes_radiobutton').set_active(True)
		else:
			self.xml.get_widget('time_always_radiobutton').set_active(True)

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

		# on new message
		only_in_roster = True
		if gajim.config.get('notify_on_new_message'):
			self.xml.get_widget('notify_on_new_message_radiobutton').set_active(
				True)
			only_in_roster = False
		if gajim.config.get('autopopup'):
			self.xml.get_widget('popup_new_message_radiobutton').set_active(True)
			only_in_roster = False
		if only_in_roster:
			self.xml.get_widget('only_in_roster_radiobutton').set_active(True)

		# notify on online statuses
		st = gajim.config.get('notify_on_signin')
		self.notify_on_signin_checkbutton.set_active(st)

		# notify on offline statuses
		st = gajim.config.get('notify_on_signout')
		self.notify_on_signout_checkbutton.set_active(st)

		# autopopupaway
		st = gajim.config.get('autopopupaway')
		self.auto_popup_away_checkbutton.set_active(st)

		# Ignore messages from unknown contacts
		self.xml.get_widget('ignore_events_from_unknown_contacts_checkbutton').\
			set_active(gajim.config.get('ignore_unknown_contacts'))

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

		# sounds
		if os.name == 'nt':
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

		#Autoaway
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
			if gajim.config.get('autodetect_browser_mailer'):
				self.applications_combobox.set_active(0)
			# else autodetect_browser_mailer is False.
			# so user has 'Always Use GNOME/KDE/XFCE4' or Custom
			elif gajim.config.get('openwith') == 'gnome-open':
				self.applications_combobox.set_active(1)
			elif gajim.config.get('openwith') == 'kfmclient exec':
				self.applications_combobox.set_active(2)
			elif gajim.config.get('openwith') == 'exo-open':
				self.applications_combobox.set_active(3)				
			elif gajim.config.get('openwith') == 'custom':
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
		
		# Notify user of new gmail e-mail messages,
		# only show checkbox if user has a gtalk account
		frame_gmail = self.xml.get_widget('frame_gmail')
		notify_gmail_checkbutton = self.xml.get_widget('notify_gmail_checkbutton')
		notify_gmail_extra_checkbutton = self.xml.get_widget(
			'notify_gmail_extra_checkbutton')
		frame_gmail.set_no_show_all(True)
		
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

	def on_trayicon_checkbutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('trayicon', True)
			gajim.interface.show_systray()
			show = helpers.get_global_show()
			gajim.interface.systray.change_status(show)
		else:
			gajim.config.set('trayicon', False)
			if not gajim.interface.roster.window.get_property('visible'):
				gajim.interface.roster.window.present()
			gajim.interface.hide_systray()
			# no tray, show roster!
			gajim.config.set('show_roster_on_startup', True)
		gajim.interface.roster.draw_roster()
		gajim.interface.save_config()

	def on_save_position_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'saveposition')

	def on_sort_by_show_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sort_by_show')
		gajim.interface.roster.draw_roster()

	def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
		gajim.interface.roster.draw_roster()
		for ctl in gajim.interface.msg_win_mgr.controls():
			if ctl.type_id == message_control.TYPE_GC:
				ctl.update_ui()

	def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
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

	def on_manage_theme_button_clicked(self, widget):
		if self.theme_preferences is None:
			self.theme_preferences = dialogs.GajimThemesWindow()
		else:
			self.theme_preferences.window.present()
			self.theme_preferences.select_active_theme()

	def on_theme_combobox_changed(self, widget):
		model = widget.get_model()
		active = widget.get_active()
		config_theme = model[active][0].decode('utf-8').replace(' ', '_')

		gajim.config.set('roster_theme', config_theme)

		# begin repainting themed widgets throughout
		gajim.interface.roster.repaint_themed_widgets()
		gajim.interface.roster.change_roster_style(None)
		gajim.interface.save_config()

	def on_open_advanced_notifications_button_clicked(self, widget):
		dialogs.AdvancedNotificationsWindow()

	def on_one_window_type_combo_changed(self, widget):
		active = widget.get_active()
		config_type = common.config.opt_one_window_types[active]
		gajim.config.set('one_message_window', config_type)
		gajim.interface.save_config()
		gajim.interface.msg_win_mgr.reconfig()

	def on_treat_incoming_messages_combobox_changed(self, widget):
		active = widget.get_active()
		config_type = common.config.opt_treat_incoming_messages[active]
		gajim.config.set('treat_incoming_messages', config_type)

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

	def on_xhtml_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_incoming_xhtml')
		
	def on_time_never_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'never')
		gajim.interface.save_config()

	def on_time_sometimes_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'sometimes')
		gajim.interface.save_config()

	def on_time_always_radiobutton_toggled(self, widget):
		if widget.get_active():
			gajim.config.set('print_time', 'always')
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
			gajim.config.set(i, gajim.interface.default_values[i])

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

	def on_notify_on_new_message_radiobutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_new_message',
					[self.auto_popup_away_checkbutton])

	def on_popup_new_message_radiobutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopup',
					[self.auto_popup_away_checkbutton])

	def on_only_in_roster_radiobutton_toggled(self, widget):
		if widget.get_active():
			self.auto_popup_away_checkbutton.set_sensitive(False)

	def on_notify_on_signin_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signin')

	def on_notify_on_signout_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'notify_on_signout')

	def on_auto_popup_away_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'autopopupaway')

	def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ignore_unknown_contacts')

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

	def on_play_sounds_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'sounds_on',
				[self.xml.get_widget('soundplayer_hbox'),
				self.xml.get_widget('sounds_scrolledwindow'),
				self.xml.get_widget('browse_sounds_hbox')])

	def on_soundplayer_entry_changed(self, widget):
		gajim.config.set('soundplayer', widget.get_text().decode('utf-8'))
		gajim.interface.save_config()

	def on_prompt_online_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_online_status')

	def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled(widget, 'ask_offline_status')

	def on_sounds_treemodel_row_changed(self, model, path, iter):
		sound_event = model[iter][3].decode('utf-8')
		gajim.config.set_per('soundevents', sound_event, 'enabled',
					bool(model[path][0]))
		gajim.config.set_per('soundevents', sound_event, 'path',
					model[iter][2].decode('utf-8'))
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

#---------- AccountModificationWindow class -------------#
class AccountModificationWindow:
	'''Class for account informations'''
	def on_account_modification_window_destroy(self, widget):
		'''close window'''
		if gajim.interface.instances.has_key(self.account):
			if gajim.interface.instances[self.account].has_key(
			'account_modification'):
				del gajim.interface.instances[self.account]['account_modification']
				return
		if gajim.interface.instances.has_key('account_modification'):
			del gajim.interface.instances['account_modification']

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, account):
		self.xml = gtkgui_helpers.get_glade('account_modification_window.glade')
		self.window = self.xml.get_widget('account_modification_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.account = account

		# init proxy list
		self.update_proxy_list()

		self.xml.signal_autoconnect(self)
		self.init_account()
		self.xml.get_widget('save_button').grab_focus()
		self.window.show_all()

	def on_checkbutton_toggled(self, widget, widgets):
		'''set or unset sensitivity of widgets when widget is toggled'''
		for w in widgets:
			w.set_sensitive(widget.get_active())

	def init_account_gpg(self):
		keyid = gajim.config.get_per('accounts', self.account, 'keyid')
		keyname = gajim.config.get_per('accounts', self.account, 'keyname')
		savegpgpass = gajim.config.get_per('accounts', self.account,
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
						self.account, 'gpgpassword')
			entry.set_text(gpgpassword)

	def update_proxy_list(self):
		if self.account:
			our_proxy = gajim.config.get_per('accounts', self.account, 'proxy')
		else:
			our_proxy = ''
		if not our_proxy:
			our_proxy = _('None')
		self.proxy_combobox = self.xml.get_widget('proxies_combobox')
		model = gtk.ListStore(str)
		self.proxy_combobox.set_model(model)
		l = gajim.config.get_per('proxies')
		l.insert(0, _('None'))
		for i in xrange(len(l)):
			model.append([l[i]])
			if our_proxy == l[i]:
				self.proxy_combobox.set_active(i)

	def init_account(self):
		'''Initialize window with defaults values'''
		self.xml.get_widget('name_entry').set_text(self.account)
		jid = gajim.config.get_per('accounts', self.account, 'name') \
			+ '@' + gajim.config.get_per('accounts',
						self.account, 'hostname')
		self.xml.get_widget('jid_entry').set_text(jid)
		self.xml.get_widget('save_password_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account, 'savepass'))
		if gajim.config.get_per('accounts', self.account, 'savepass'):
			passstr = passwords.get_password(self.account)
			password_entry = self.xml.get_widget('password_entry')
			password_entry.set_sensitive(True)
			password_entry.set_text(passstr)

		self.xml.get_widget('resource_entry').set_text(gajim.config.get_per(
			'accounts', self.account, 'resource'))
		self.xml.get_widget('adjust_priority_with_status_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account,
			'adjust_priority_with_status'))
		spinbutton = self.xml.get_widget('priority_spinbutton')
		if gajim.config.get('enable_negative_priority'):
			spinbutton.set_range(-128, 127)
		spinbutton.set_value(gajim.config.get_per('accounts', self.account,
			'priority'))

		usessl = gajim.config.get_per('accounts', self.account, 'usessl')
		self.xml.get_widget('use_ssl_checkbutton').set_active(usessl)

		self.xml.get_widget('send_keepalive_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account,
			'keep_alives_enabled'))

		use_custom_host = gajim.config.get_per('accounts', self.account,
			'use_custom_host')
		self.xml.get_widget('custom_host_port_checkbutton').set_active(
			use_custom_host)
		custom_host = gajim.config.get_per('accounts', self.account,
			'custom_host')
		if not custom_host:
			custom_host = gajim.config.get_per('accounts',
				self.account, 'hostname')
		self.xml.get_widget('custom_host_entry').set_text(custom_host)
		custom_port = gajim.config.get_per('accounts', self.account,
			'custom_port')
		if not custom_port:
			custom_port = 5222
		self.xml.get_widget('custom_port_entry').set_text(unicode(custom_port))

		gpg_key_label = self.xml.get_widget('gpg_key_label')
		if gajim.config.get('usegpg'):
			self.init_account_gpg()
		else:
			gpg_key_label.set_text(_('OpenPGP is not usable in this computer'))
			self.xml.get_widget('gpg_choose_button').set_sensitive(False)
		self.xml.get_widget('autoconnect_checkbutton').set_active(gajim.config.\
			get_per('accounts', self.account, 'autoconnect'))
		self.xml.get_widget('autoreconnect_checkbutton').set_active(gajim.config.\
			get_per('accounts', self.account, 'autoreconnect'))

		self.xml.get_widget('sync_with_global_status_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account,
			'sync_with_global_status'))
		self.xml.get_widget('autoconnect_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account, 'autoconnect'))
		self.xml.get_widget('use_ft_proxies_checkbutton').set_active(
			gajim.config.get_per('accounts', self.account, 'use_ft_proxies'))
		list_no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.account in list_no_log_for:
			self.xml.get_widget('log_history_checkbutton').set_active(0)

	def option_changed(self, config, opt): 
		if gajim.config.get_per('accounts', self.account, opt) != config[opt]:
			return True
		return False

	def options_changed_need_relogin(self, config, options):
		'''accepts configuration and options
		(tupple of strings of the name of options changed)
		and returns True or False depending on if at least one of the options
		need relogin to server to apply'''
		for option in options:
			if self.option_changed(config, option):
				return True
		return False

	def on_adjust_priority_with_status_checkbutton_toggled(self, widget):
		self.xml.get_widget('priority_spinbutton').set_sensitive(
			not widget.get_active())

	def on_save_button_clicked(self, widget):
		'''When save button is clicked: Save information in config file'''
		config = {}
		name = self.xml.get_widget('name_entry').get_text().decode('utf-8')
		if gajim.connections.has_key(self.account):
			if name != self.account:
				if gajim.connections[self.account].connected != 0:
					dialogs.ErrorDialog(
						_('You are currently connected to the server'),
						_('To change the account name, you must be disconnected.'))
					return
				if len(gajim.events.get_events(self.account)):
					dialogs.ErrorDialog(_('Unread events'),
						_('To change the account name, you must read all pending '
						'events.'))
					return
				if name in gajim.connections:
					dialogs.ErrorDialog(_('Account Name Already Used'),
						_('This name is already used by another of your accounts. '
						'Please choose another name.'))
					return
		if (name == ''):
			dialogs.ErrorDialog(_('Invalid account name'),
				_('Account name cannot be empty.'))
			return
		if name.find(' ') != -1:
			dialogs.ErrorDialog(_('Invalid account name'),
				_('Account name cannot contain spaces.'))
			return
		jid = self.xml.get_widget('jid_entry').get_text().decode('utf-8')

		# check if jid is conform to RFC and stringprep it
		try:
			jid = helpers.parse_jid(jid)
		except helpers.InvalidFormat, s:
			pritext = _('Invalid Jabber ID')
			dialogs.ErrorDialog(pritext, str(s))
			return

		n, hn = jid.split('@', 1)
		if not n:
			pritext = _('Invalid Jabber ID')
			sectext = _('A Jabber ID must be in the form "user@servername".')
			dialogs.ErrorDialog(pritext, sectext)
			return

		resource = self.xml.get_widget('resource_entry').get_text().decode(
			'utf-8')
		try:
			resource = helpers.parse_resource(resource)
		except helpers.InvalidFormat, s:
			pritext = _('Invalid Jabber ID')
			dialogs.ErrorDialog(pritext, (s))
			return

		config['savepass'] = self.xml.get_widget(
				'save_password_checkbutton').get_active()
		config['password'] = self.xml.get_widget('password_entry').get_text().\
			decode('utf-8')
		config['resource'] = resource
		config['adjust_priority_with_status'] = self.xml.get_widget(
			'adjust_priority_with_status_checkbutton').get_active()
		config['priority'] = self.xml.get_widget('priority_spinbutton').\
			get_value_as_int()
		config['autoconnect'] = self.xml.get_widget('autoconnect_checkbutton').\
			get_active()
		config['autoreconnect'] = self.xml.get_widget(
			'autoreconnect_checkbutton').get_active()

		if self.account:
			list_no_log_for = gajim.config.get_per('accounts', self.account,
				'no_log_for').split()
		else:
			list_no_log_for = []
		if self.account in list_no_log_for:
			list_no_log_for.remove(self.account)
		if not self.xml.get_widget('log_history_checkbutton').get_active():
			list_no_log_for.append(name)
		config['no_log_for'] = ' '.join(list_no_log_for)

		config['sync_with_global_status'] = self.xml.get_widget(
			'sync_with_global_status_checkbutton').get_active()
		config['use_ft_proxies'] = self.xml.get_widget(
			'use_ft_proxies_checkbutton').get_active()

		active = self.proxy_combobox.get_active()
		proxy = self.proxy_combobox.get_model()[active][0].decode('utf-8')
		if proxy == _('None'):
			proxy = ''
		config['proxy'] = proxy

		config['usessl'] = self.xml.get_widget('use_ssl_checkbutton').get_active()
		config['name'] = n
		config['hostname'] = hn

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

		# update in case the name was changed to local account's name
		config['is_zeroconf'] = False

		config['keyname'] = self.xml.get_widget('gpg_name_label').get_text().\
			decode('utf-8')
		if config['keyname'] == '': #no key selected
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
		#if we modify the name of the account
		if name != self.account:
			#update variables
			gajim.interface.instances[name] = gajim.interface.instances[
				self.account]
			gajim.nicks[name] = gajim.nicks[self.account]
			gajim.block_signed_in_notifications[name] = \
				gajim.block_signed_in_notifications[self.account]
			gajim.groups[name] = gajim.groups[self.account]
			gajim.gc_connected[name] = gajim.gc_connected[self.account]
			gajim.automatic_rooms[name] = gajim.automatic_rooms[self.account]
			gajim.newly_added[name] = gajim.newly_added[self.account]
			gajim.to_be_removed[name] = gajim.to_be_removed[self.account]
			gajim.sleeper_state[name] = gajim.sleeper_state[self.account]
			gajim.encrypted_chats[name] = gajim.encrypted_chats[self.account]
			gajim.last_message_time[name] = \
				gajim.last_message_time[self.account]
			gajim.status_before_autoaway[name] = \
				gajim.status_before_autoaway[self.account]
			gajim.transport_avatar[name] = gajim.transport_avatar[self.account]

			gajim.contacts.change_account_name(self.account, name)
			gajim.events.change_account_name(self.account, name)

			# change account variable for chat / gc controls
			gajim.interface.msg_win_mgr.change_account_name(self.account, name)
			# upgrade account variable in opened windows
			for kind in ('infos', 'disco', 'gc_config'):
				for j in gajim.interface.instances[name][kind]:
					gajim.interface.instances[name][kind][j].account = name

			# ServiceCache object keep old property account
			if hasattr(gajim.connections[self.account], 'services_cache'):
				gajim.connections[self.account].services_cache.account = name
			del gajim.interface.instances[self.account]
			del gajim.nicks[self.account]
			del gajim.block_signed_in_notifications[self.account]
			del gajim.groups[self.account]
			del gajim.gc_connected[self.account]
			del gajim.automatic_rooms[self.account]
			del gajim.newly_added[self.account]
			del gajim.to_be_removed[self.account]
			del gajim.sleeper_state[self.account]
			del gajim.encrypted_chats[self.account]
			del gajim.last_message_time[self.account]
			del gajim.status_before_autoaway[self.account]
			del gajim.transport_avatar[self.account]
			gajim.connections[self.account].name = name
			gajim.connections[name] = gajim.connections[self.account]
			del gajim.connections[self.account]
			gajim.config.del_per('accounts', self.account)
			gajim.config.add_per('accounts', name)
			self.account = name

		resend_presence = False
		if gajim.connections[self.account].connected == 0: # we're disconnected
			relogin_needed = False
		else: # we're connected to the account we want to apply changes
			# check if relogin is needed
			relogin_needed = False
			if self.options_changed_need_relogin(config,
			('resource', 'proxy', 'usessl', 'keyname',
			'use_custom_host', 'custom_host')):
				relogin_needed = True

			elif config['use_custom_host'] and (self.option_changed(config,
			'custom_host') or self.option_changed(config, 'custom_port')):
				relogin_needed = True

			if self.option_changed(config, 'use_ft_proxies') and \
			config['use_ft_proxies']:
				gajim.connections[self.account].discover_ft_proxies()

			if self.option_changed(config, 'priority') or self.option_changed(
			config, 'adjust_priority_with_status'):
				resend_presence = True

		for opt in config:
			gajim.config.set_per('accounts', name, opt, config[opt])
		if config['savepass']:
			passwords.save_password(name, config['password'])
		else:
			passwords.save_password(name, '')
		# refresh accounts window
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].init_accounts()
		# refresh roster
		gajim.interface.roster.draw_roster()
		gajim.interface.save_config()
		self.window.destroy()

		if relogin_needed:
			def login(account, show_before, status_before):
				''' login with previous status'''
				# first make sure connection is really closed, 
				# 0.5 may not be enough
				gajim.connections[account].disconnect(True)
				gajim.interface.roster.send_status(account, show_before, 
					status_before)

			def relog(widget):
				self.dialog.destroy()
				show_before = gajim.SHOW_LIST[gajim.connections[self.account].\
					connected]
				status_before = gajim.connections[self.account].status
				gajim.interface.roster.send_status(self.account, 'offline',
					_('Be right back.'))
				gobject.timeout_add(500, login, self.account, show_before, 
					status_before)

			def resend(widget):
				self.resend_presence()

			on_no = None
			if resend_presence:
				on_no = resend
			self.dialog = dialogs.YesNoDialog(_('Relogin now?'),
				_('If you want all the changes to apply instantly, '
				'you must relogin.'), on_response_yes = relog,
					on_response_no = on_no)
		elif resend_presence:
			self.resend_presence()

	def resend_presence(self):
		show = gajim.SHOW_LIST[gajim.connections[self.account].connected]
		status = gajim.connections[self.account].status
		gajim.connections[self.account].change_status(show, status)

	def on_change_password_button_clicked(self, widget):
		try:
			dialog = dialogs.ChangePasswordDialog(self.account)
		except GajimGeneralException:
			#if we showed ErrorDialog, there will not be dialog instance
			return

		new_password = dialog.run()
		if new_password != -1:
			gajim.connections[self.account].change_password(new_password)
			if self.xml.get_widget('save_password_checkbutton').get_active():
				self.xml.get_widget('password_entry').set_text(new_password)

	def on_edit_details_button_clicked(self, widget):
		if not gajim.interface.instances.has_key(self.account):
			dialogs.ErrorDialog(_('No such account available'),
				_('You must create your account before editing your personal '
				'information.'))
			return

		# show error dialog if account is newly created (not in gajim.connections)
		if not gajim.connections.has_key(self.account) or \
			gajim.connections[self.account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
			_('Without a connection, you can not edit your personal information.'))
			return

		if not gajim.connections[self.account].vcard_supported:
			dialogs.ErrorDialog(_("Your server doesn't support Vcard"),
			_("Your server can't save your personal information."))
			return

		gajim.interface.edit_own_details(self.account)

	def on_manage_proxies_button_clicked(self, widget):
		if gajim.interface.instances.has_key('manage_proxies'):
			gajim.interface.instances['manage_proxies'].window.present()
		else:
			gajim.interface.instances['manage_proxies'] = \
				ManageProxiesWindow()

	def on_gpg_choose_button_clicked(self, widget, data = None):
		if gajim.connections.has_key(self.account):
			secret_keys = gajim.connections[self.account].ask_gpg_secrete_keys()

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

	def on_checkbutton_toggled_and_clear(self, widget, widgets):
		self.on_checkbutton_toggled(widget, widgets)
		for w in widgets:
			if not widget.get_active():
				w.set_text('')

	def on_use_ssl_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		if isactive:
			self.xml.get_widget('custom_port_entry').set_text('5223')
		else:
			self.xml.get_widget('custom_port_entry').set_text('5222')

	def on_send_keepalive_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		gajim.config.set_per('accounts', self.account,
			'keep_alives_enabled', isactive)

	def on_custom_host_port_checkbutton_toggled(self, widget):
		isactive = widget.get_active()
		self.xml.get_widget('custom_host_port_hbox').set_sensitive(isactive)

	def on_gpg_save_password_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled_and_clear(widget, [
			self.xml.get_widget('gpg_password_entry')])

	def on_save_password_checkbutton_toggled(self, widget):
		self.on_checkbutton_toggled_and_clear(widget,
			[self.xml.get_widget('password_entry')])
		self.xml.get_widget('password_entry').grab_focus()

#---------- ManageProxiesWindow class -------------#
class ManageProxiesWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('manage_proxies_window.glade')
		self.window = self.xml.get_widget('manage_proxies_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.proxies_treeview = self.xml.get_widget('proxies_treeview')
		self.proxyname_entry = self.xml.get_widget('proxyname_entry')
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
		self.xml.get_widget('proxytype_combobox').set_sensitive(False)
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
		for account in gajim.connections:
			if gajim.interface.instances[account].has_key('account_modification'):
				gajim.interface.instances[account]['account_modification'].\
					update_proxy_list()
		if gajim.interface.instances.has_key('account_modification'):
			gajim.interface.instances['account_modification'].update_proxy_list()
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
			#FIXME: if we have several proxy types, set the combobox
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
		#FIXME: if we have several proxy types take them into account
		pass

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
		self.modify_button = self.xml.get_widget('modify_button')
		self.remove_button = self.xml.get_widget('remove_button')
		model = gtk.ListStore(str, str, bool)
		self.accounts_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Name'), renderer, text = 0)
		renderer = gtk.CellRendererText()
		self.accounts_treeview.insert_column_with_attributes(-1,
					_('Server'), renderer, text = 1)
		self.xml.signal_autoconnect(self)
		self.init_accounts()
		self.window.show_all()

		#Merge accounts
		st = gajim.config.get('mergeaccounts')
		self.xml.get_widget('merge_checkbutton').set_active(st)

		import os

		avahi_error = False
		try:
			import avahi
		except ImportError:
			avahi_error = True

		# enable zeroconf
		st = gajim.config.get('enable_zeroconf')
		w = self.xml.get_widget('enable_zeroconf_checkbutton')
		w.set_active(st)
		if os.name == 'nt' or (avahi_error and not w.get_active()):
			w.set_sensitive(False)
		self.zeroconf_toggled_id = w.connect('toggled',
			self.on_enable_zeroconf_checkbutton_toggled)

	def on_accounts_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def init_accounts(self):
		'''initialize listStore with existing accounts'''
		self.modify_button.set_sensitive(False)
		self.remove_button.set_sensitive(False)
		model = self.accounts_treeview.get_model()
		model.clear()
		for account in gajim.connections:
			iter = model.append()
			model.set(iter, 0, account, 1, gajim.get_hostname_from_account(
				account))

	def on_accounts_treeview_cursor_changed(self, widget):
		'''Activate delete and modify buttons when a row is selected'''
		self.modify_button.set_sensitive(True)
		self.remove_button.set_sensitive(True)

	def on_new_button_clicked(self, widget):
		'''When new button is clicked: open an account information window'''
		if gajim.interface.instances.has_key('account_creation_wizard'):
			gajim.interface.instances['account_creation_wizard'].window.present()
		else:
			gajim.interface.instances['account_creation_wizard'] = \
				AccountCreationWizardWindow()

	def on_remove_button_clicked(self, widget):
		'''When delete button is clicked:
		Remove an account from the listStore and from the config file'''
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		if not iter:
			return
		account = model.get_value(iter, 0).decode('utf-8')
		if len(gajim.events.get_events(account)):
			dialogs.ErrorDialog(_('Unread events'),
				_('Read all pending events before removing this account.'))
			return

		if gajim.config.get_per('accounts', account, 'is_zeroconf'):
			w = self.xml.get_widget('enable_zeroconf_checkbutton')
			w.set_active(False)
			return
		else:
			if gajim.interface.instances[account].has_key('remove_account'):
				gajim.interface.instances[account]['remove_account'].window.present(
					)
			else:
				gajim.interface.instances[account]['remove_account'] = \
					RemoveAccountWindow(account)

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
		self.dialog = None
		def remove(widget, account):
			if self.dialog:
				self.dialog.destroy()
			if gajim.interface.instances[account].has_key('remove_account'):
				gajim.interface.instances[account]['remove_account'].window.\
					present()
			else:
				gajim.interface.instances[account]['remove_account'] = \
					RemoveAccountWindow(account)
		if win_opened:
			self.dialog = dialogs.ConfirmationDialog(
				_('You have opened chat in account %s') % account,
				_('All chat and groupchat windows will be closed. Do you want to '
				'continue?'),
				on_response_ok = (remove, account))
		else:
			remove(widget, account)

	def on_modify_button_clicked(self, widget):
		'''When modify button is clicked:
		open/show the account modification window for this account'''
		sel = self.accounts_treeview.get_selection()
		(model, iter) = sel.get_selected()
		if not iter:
			return
		account = model[iter][0].decode('utf-8')
		self.show_modification_window(account)

	def on_accounts_treeview_row_activated(self, widget, path, column):
		model = widget.get_model()
		account = model[path][0].decode('utf-8')
		self.show_modification_window(account)

	def show_modification_window(self, account):
		if gajim.config.get_per('accounts', account, 'is_zeroconf'):
			if gajim.interface.instances.has_key('zeroconf_properties'):
				gajim.interface.instances['zeroconf_properties'].window.present()
			else:
				gajim.interface.instances['zeroconf_properties'] = \
					ZeroconfPropertiesWindow()
		else:
			if gajim.interface.instances[account].has_key('account_modification'):
				gajim.interface.instances[account]['account_modification'].window.\
					present()
			else:
				gajim.interface.instances[account]['account_modification'] = \
					AccountModificationWindow(account)

	def on_checkbutton_toggled(self, widget, config_name,
		change_sensitivity_widgets = None):
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

	
	def on_enable_zeroconf_checkbutton_toggled(self, widget):
		# don't do anything if there is an account with the local name but is a 
		# normal account
		if gajim.connections.has_key(gajim.ZEROCONF_ACC_NAME) and not \
		gajim.connections[gajim.ZEROCONF_ACC_NAME].is_zeroconf:
			gajim.connections[gajim.ZEROCONF_ACC_NAME].dispatch('ERROR',
				(_('Account Local already exists.'),
				_('Please rename or remove it before enabling link-local messaging'
				'.')))
			widget.disconnect(self.zeroconf_toggled_id)
			widget.set_active(False)
			self.zeroconf_toggled_id = widget.connect('toggled',
				self.on_enable_zeroconf_checkbutton_toggled)
			return

		if gajim.config.get('enable_zeroconf'):
			#disable
			gajim.interface.roster.close_all(gajim.ZEROCONF_ACC_NAME)
			gajim.connections[gajim.ZEROCONF_ACC_NAME].disable_account()
			del gajim.connections[gajim.ZEROCONF_ACC_NAME]
			gajim.interface.save_config()
			del gajim.interface.instances[gajim.ZEROCONF_ACC_NAME]
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
			gajim.interface.roster.actions_menu_needs_rebuild = True
			if gajim.interface.instances.has_key('accounts'):
				gajim.interface.instances['accounts'].init_accounts()
			
		else:
			# enable (will create new account if not present)
			gajim.connections[gajim.ZEROCONF_ACC_NAME] = common.zeroconf.\
				connection_zeroconf.ConnectionZeroconf(gajim.ZEROCONF_ACC_NAME)
			# update variables
			gajim.interface.instances[gajim.ZEROCONF_ACC_NAME] = {'infos': {},
				'disco': {}, 'gc_config': {}}
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
			# refresh accounts window
			if gajim.interface.instances.has_key('accounts'):
				gajim.interface.instances['accounts'].init_accounts()
			# refresh roster
			if len(gajim.connections) >= 2:
				# Do not merge accounts if only one exists
				gajim.interface.roster.regroup = gajim.config.get('mergeaccounts') 
			else: 
				gajim.interface.roster.regroup = False
			gajim.interface.roster.draw_roster()
			gajim.interface.roster.actions_menu_needs_rebuild = True
			gajim.interface.save_config()
			gajim.connections[gajim.ZEROCONF_ACC_NAME].change_status('online', '')

		self.on_checkbutton_toggled(widget, 'enable_zeroconf')
		
class DataFormWindow:
	def __init__(self, account, config):
		self.account = account
		self.config = config
		self.xml = gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_window')
		self.window = self.xml.get_widget('data_form_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		self.config_vbox = self.xml.get_widget('config_vbox')
		if config:
			self.fill_vbox()
		else:
			self.config_vbox.set_no_show_all(True)
			self.config_vbox.hide()
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()
	
	def on_ok_button_clicked(self, widget):
		'''NOTE: child class should implement this'''
		pass

	def on_data_form_window_destroy(self, widget):
		'''NOTE: child class should implement this'''
		pass

	def on_checkbutton_toggled(self, widget, index):
		self.config[index]['values'][0] = widget.get_active()

	def on_checkbutton_toggled2(self, widget, index1, index2):
		val = self.config[index1]['options'][index2]['values'][0]
		if widget.get_active() and val not in self.config[index1]['values']:
			self.config[index1]['values'].append(val)
		elif not widget.get_active() and val in self.config[index1]['values']:
			self.config[index1]['values'].remove(val)

	def on_combobox_changed(self, widget, index):
		self.config[index]['values'][0] = self.config[index]['options'][ \
			widget.get_active()]['values'][0]

	def on_entry_changed(self, widget, index):
		self.config[index]['values'][0] = widget.get_text().decode('utf-8')

	def on_textbuffer_changed(self, widget, index):
		begin, end = widget.get_bounds()
		self.config[index]['values'][0] = widget.get_text(begin, end)

	def fill_vbox(self):
		'''see JEP0004'''
		if self.config.has_key('title'):
			self.window.set_title(self.config['title'])
		if self.config.has_key('instructions'):
			self.xml.get_widget('instructions_label').set_text(
				self.config['instructions'])
		i = 0
		while self.config.has_key(i):
			if not self.config[i].has_key('type'):
				i += 1
				continue
			ctype = self.config[i]['type']
			if ctype == 'hidden':
				i += 1
				continue
			hbox = gtk.HBox(spacing = 5)
			label = gtk.Label('')
			label.set_line_wrap(True)
			label.set_alignment(0.0, 0.5)
			label.set_property('width_request', 150)
			hbox.pack_start(label, False)
			if self.config[i].has_key('label'):
				label.set_text(self.config[i]['label'])
			if ctype == 'boolean':
				desc = None
				if self.config[i].has_key('desc'):
					desc = self.config[i]['desc']
				widget = gtk.CheckButton(desc, False)
				activ = False
				if self.config[i].has_key('values'):
					activ = self.config[i]['values'][0]
				widget.set_active(activ)
				widget.connect('toggled', self.on_checkbutton_toggled, i)
			elif ctype == 'fixed':
				widget = gtk.Label('\n'.join(self.config[i]['values']))
				widget.set_line_wrap(True)
				widget.set_alignment(0.0, 0.5)
			elif ctype == 'jid-multi':
				#FIXME
				widget = gtk.Label('')
			elif ctype == 'jid-single':
				#FIXME
				widget = gtk.Label('')
			elif ctype == 'list-multi':
				j = 0
				widget = gtk.Table(1, 1)
				while self.config[i]['options'].has_key(j):
					widget.resize(j + 1, 1)
					child = gtk.CheckButton(self.config[i]['options'][j]['label'],
						False)
					if self.config[i]['options'][j]['values'][0] in \
					self.config[i]['values']:
						child.set_active(True)
					child.connect('toggled', self.on_checkbutton_toggled2, i, j)
					widget.attach(child, 0, 1, j, j+1)
					j += 1
			elif ctype == 'list-single':
				widget = gtk.combo_box_new_text()
				widget.connect('changed', self.on_combobox_changed, i)
				index = 0
				j = 0
				while self.config[i]['options'].has_key(j):
					if self.config[i]['options'][j]['values'][0] == \
						self.config[i]['values'][0]:
						index = j
					widget.append_text(self.config[i]['options'][j]['label'])
					j += 1
				widget.set_active(index)
			elif ctype == 'text-multi':
				widget = gtk.TextView()
				widget.set_size_request(100, -1)
				widget.get_buffer().connect('changed', self.on_textbuffer_changed, \
					i)
				widget.get_buffer().set_text('\n'.join(self.config[i]['values']))
			elif ctype == 'text-private':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				if not self.config[i].has_key('values'):
					self.config[i]['values'] = ['']
				widget.set_text(self.config[i]['values'][0])
				widget.set_visibility(False)
			elif ctype == 'text-single':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				if not self.config[i].has_key('values'):
					self.config[i]['values'] = ['']
				widget.set_text(self.config[i]['values'][0])
			i += 1
			hbox.pack_start(widget, False)
			hbox.pack_start(gtk.Label('')) # So that widhet doesn't take all space
			self.config_vbox.pack_start(hbox, False)
		self.config_vbox.show_all()

class ServiceRegistrationWindow(DataFormWindow):
	'''Class for Service registration window:
	Window that appears when we want to subscribe to a service
	if is_form we use DataFormWindow else we use service_registarion_window'''
	def __init__(self, service, infos, account, is_form):
		self.service = service
		self.infos = infos
		self.account = account
		self.is_form = is_form
		if self.is_form:
			DataFormWindow.__init__(self, account, infos)
		else:
			self.xml = gtkgui_helpers.get_glade(
				'service_registration_window.glade')
			self.window = self.xml.get_widget('service_registration_window')
			self.window.set_transient_for(gajim.interface.roster.window)
			if infos.has_key('registered'):
				self.window.set_title(_('Edit %s') % service)
			else:
				self.window.set_title(_('Register to %s') % service)
			self.xml.get_widget('label').set_text(infos['instructions'])
			self.entries = {}
			self.draw_table()
			self.xml.signal_autoconnect(self)
			self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def draw_table(self):
		'''Draw the table in the window'''
		nbrow = 0
		table = self.xml.get_widget('table')
		for name in self.infos.keys():
			if name in ('key', 'instructions', 'x', 'registered'):
				continue
			if not name:
				continue

			nbrow = nbrow + 1
			table.resize(rows = nbrow, columns = 2)
			label = gtk.Label(name.capitalize() + ':')
			table.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
			entry = gtk.Entry()
			entry.set_activates_default(True)
			if self.infos[name]:
				entry.set_text(self.infos[name])
			if name == 'password':
				entry.set_visibility(False)
			table.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
			self.entries[name] = entry
			if nbrow == 1:
				entry.grab_focus()
		table.show_all()

	def on_ok_button_clicked(self, widget):
		if self.is_form:
			# We pressed OK button of the DataFormWindow
			if self.infos.has_key('registered'):
				del self.infos['registered']
			gajim.connections[self.account].register_agent(self.service,
				self.infos, True) # True is for is_form
		else:
			# we pressed OK of service_registration_window
			# send registration info to the core
			for name in self.entries.keys():
				self.infos[name] = self.entries[name].get_text().decode('utf-8')
			if self.infos.has_key('instructions'):
				del self.infos['instructions']
			if self.infos.has_key('registered'):
				del self.infos['registered']
			gajim.connections[self.account].register_agent(self.service,
				self.infos)
		
		self.window.destroy()


class GroupchatConfigWindow(DataFormWindow):
	'''GroupchatConfigWindow class'''
	def __init__(self, account, room_jid, config = None):
		DataFormWindow.__init__(self, account, config)
		self.room_jid = room_jid
		self.remove_button = {}
		self.affiliation_treeview = {}
		self.list_init = {} # list at the beginning
		ui_list = {'outcast': _('Ban List'),
			'member': _('Member List'),
			'owner': _('Owner List'),
			'admin':_('Administrator List')}

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

		add_on_vbox.show_all() 

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
		# We pressed OK button of the DataFormWindow
		if self.config:
			gajim.connections[self.account].send_gc_config(self.room_jid,
				self.config)
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
		def remove(widget):
			if self.dialog:
				self.dialog.destroy()
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

		self.dialog = None
		if gajim.connections[self.account].connected:
			self.dialog = dialogs.ConfirmationDialog(
				_('Account "%s" is connected to the server') % self.account,
				_('If you remove it, the connection will be lost.'),
				on_response_ok = remove)
		else:
			remove(None)
	
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
		gajim.interface.roster.actions_menu_needs_rebuild = True
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].init_accounts()
		self.window.destroy()

#---------- ManageBookmarksWindow class -------------#
class ManageBookmarksWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('manage_bookmarks_window.glade')
		self.window = self.xml.get_widget('manage_bookmarks_window')
		self.window.set_transient_for(gajim.interface.roster.window)

		# Account-JID, RoomName, Room-JID, Autojoin, Passowrd, Nick, Show_Status
		self.treestore = gtk.TreeStore(str, str, str, bool, str, str, str)

		# Store bookmarks in treeview.
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1:
				continue
			if gajim.connections[account].is_zeroconf:
				continue
			iter = self.treestore.append(None, [None, account,None,
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

				print_status = bookmark.get('print_status', '')
				if print_status not in ('', 'all', 'in_and_out', 'none'):
					print_status = ''
				self.treestore.append( iter, [
						account,
						bookmark['name'],
						bookmark['jid'],
						autojoin,
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
			False, '', nick, 'in_and_out'])
		self.view.set_cursor(model.get_path(iter_))

		self.view.expand_row(model.get_path(add_to), True)

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

				#create the bookmark-dict
				bmdict = { 'name': bm[1], 'jid': bm[2], 'autojoin': autojoin,
					'password': bm[4], 'nick': bm[5], 'print_status': bm[6]}

				gajim.connections[account_unicode].bookmarks.append(bmdict)

			gajim.connections[account_unicode].store_bookmarks()
		gajim.interface.roster.actions_menu_needs_rebuild = True
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
			self.print_status_combobox]

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
		if model[iter][4] is not None:
			password = model[iter][4].decode('utf-8')
		else:
			password = None

		if password:
			self.pass_entry.set_text(password)
		else:
			self.pass_entry.set_text('')
		nick = model[iter][5]
		if nick:
			nick = nick.decode('utf-8')
			self.nick_entry.set_text(nick)
		else:
			self.nick_entry.set_text('')

		print_status = model[iter][6]
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
			model[iter][5] = self.nick_entry.get_text()

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
			model[iter][4] = self.pass_entry.get_text()

	def on_autojoin_checkbutton_toggled(self, widget):
		(model, iter) = self.selection.get_selected()
		if iter:
			model[iter][3] = self.autojoin_checkbutton.get_active()

	def on_print_status_combobox_changed(self, widget):
		active = widget.get_active()
		model = widget.get_model()
		print_status = model[active][1]
		(model2, iter) = self.selection.get_selected()
		if iter:
			model2[iter][6] = print_status

	def clear_fields(self):
		widgets = [ self.title_entry, self.nick_entry, self.room_entry,
			self.server_entry, self.pass_entry ]
		for field in widgets:
			field.set_text('')
		self.autojoin_checkbutton.set_active(False)
		self.print_status_combobox.set_active(1)

class AccountCreationWizardWindow:
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade(
			'account_creation_wizard_window.glade')
		self.window = self.xml.get_widget('account_creation_wizard_window')

		# Connect events from comboboxentry.child
		server_comboboxentry = self.xml.get_widget('server_comboboxentry')
		entry = server_comboboxentry.child
		entry.connect('key_press_event',
			self.on_server_comboboxentry_key_press_event)
		completion = gtk.EntryCompletion()
		entry.set_completion(completion)

		# parse servers.xml
		servers_xml = os.path.join(gajim.DATA_DIR, 'other', 'servers.xml')
		servers = gtkgui_helpers.parse_server_xml(servers_xml)
		servers_model = gtk.ListStore(str, int)
		for server in servers:
			servers_model.append((str(server[0]), int(server[1])))

		completion.set_model(servers_model)
		completion.set_text_column(0)

		# Put servers into comboboxentries
		server_comboboxentry.set_model(servers_model)
		server_comboboxentry.set_text_column(0)

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
		self.advanced_button.set_no_show_all(True)
		self.finish_button.set_no_show_all(True)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_wizard_window_destroy(self, widget):
		del gajim.interface.instances['account_creation_wizard']

	def on_register_server_features_button_clicked(self, widget):
		helpers.launch_browser_mailer('url',
			'http://www.jabber.org/network/oldnetwork.shtml')

	def on_save_password_checkbutton_toggled(self, widget):
		self.xml.get_widget('pass1_entry').grab_focus()

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_back_button_clicked(self, widget):
		if self.notebook.get_current_page() == 1:
			self.notebook.set_current_page(0)
			self.back_button.set_sensitive(False)
		elif self.notebook.get_current_page() == 3: # finish page
			self.forward_button.show()
			self.notebook.set_current_page(1) # Goto parameters page

	def get_widgets(self):
		widgets = {}
		for widget in (
						'username_entry',
						'server_comboboxentry',
						'pass1_entry',
						'pass2_entry',
						'save_password_checkbutton',
						'proxyhost_entry',
						'proxyport_entry',
						'proxyuser_entry',
						'proxypass_entry',
						'jid_label'):
			widgets[widget] = self.xml.get_widget(widget)
		return widgets

	def on_forward_button_clicked(self, widget):
		cur_page = self.notebook.get_current_page()

		if cur_page == 0:
			widget = self.xml.get_widget('use_existing_account_radiobutton')
			if widget.get_active():
				self.modify = True
				self.xml.get_widget('server_features_button').hide()
				self.xml.get_widget('pass2_entry').hide()
				self.xml.get_widget('pass2_label').hide()
			else:
				self.modify = False
				self.xml.get_widget('server_features_button').show()
				self.xml.get_widget('pass2_entry').show()
				self.xml.get_widget('pass2_label').show()
			self.notebook.set_current_page(1)
			self.back_button.set_sensitive(True)
			return

		else:
			widgets = self.get_widgets()
			username = widgets['username_entry'].get_text().decode('utf-8')
			if not username:
				pritext = _('Invalid username')
				sectext = _('You must provide a username to configure this account'
				'.')
				dialogs.ErrorDialog(pritext, sectext)
				return
			server = widgets['server_comboboxentry'].child.get_text().decode('utf-8')
			savepass = widgets['save_password_checkbutton'].get_active()
			password = widgets['pass1_entry'].get_text().decode('utf-8')

			if not self.modify:
				if password == '':
					dialogs.ErrorDialog(_('Invalid password'),
						_('You must enter a password for the new account.'))
					return

				if widgets['pass2_entry'].get_text() != password:
					dialogs.ErrorDialog(_('Passwords do not match'),
						_('The passwords typed in both fields must be identical.'))
					return

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
				self.notebook.set_current_page(3) # show finish page
				self.show_vcard_checkbutton.set_active(False)
			else:
				self.notebook.set_current_page(2) # show creating page
				self.update_progressbar_timeout_id = gobject.timeout_add(100,
					self.update_progressbar)

	def update_progressbar(self):
		self.progressbar.pulse()
		return True # loop forever

	def acc_is_ok(self, config):
		'''Account creation succeeded'''
		self.create_vars(config)
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
		self.notebook.set_current_page(3) # show finish page

		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)

	def acc_is_not_ok(self, reason):
		'''Account creation failed'''
		self.back_button.show()
		self.cancel_button.show()
		self.go_online_checkbutton.hide()
		self.show_vcard_checkbutton.hide()
		img = self.xml.get_widget('finish_image')
		img.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG)
		finish_text = '<big><b>%s</b></big>\n\n%s' % (_('An error occurred during '
			'account creation') , reason)
		self.finish_label.set_markup(finish_text)
		self.notebook.set_current_page(3) # show finish page

	def on_advanced_button_clicked(self, widget):
		gajim.interface.instances[self.account]['account_modification'] = \
			AccountModificationWindow(self.account)
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

	def on_server_comboboxentry_key_press_event(self, widget, event):
		# If backspace is pressed in empty field, return to the nick entry field
		backspace = event.keyval == gtk.keysyms.BackSpace
		combobox = self.xml.get_widget('server_comboboxentry')
		empty = len(combobox.get_active_text()) == 0
		if backspace and empty:
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

	def save_account(self, login, server, savepass, password):
		if self.account in gajim.connections:
			dialogs.ErrorDialog(_('Account name is in use'),
				_('You already have an account using this name.'))
			return
		con = connection.Connection(self.account)
		con.password = password

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
		config['savegpgpass'] = False
		config['gpgpassword'] = ''

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
			'gc_config': {}}
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
		gajim.interface.roster.actions_menu_needs_rebuild = True
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
		if config['keyname'] == '': #no key selected
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
