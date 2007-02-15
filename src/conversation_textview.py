##	conversation_textview.py
##
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Travis Shirk <travis@pobox.com>
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
import pango
import gobject
import time
import os
import tooltips
import dialogs
import locale

import gtkgui_helpers
from common import gajim
from common import helpers
from calendar import timegm
from common.fuzzyclock import FuzzyClock

from htmltextview import HtmlTextView
from common.exceptions import GajimGeneralException

class ConversationTextview:
	'''Class for the conversation textview (where user reads already said messages)
	for chat/groupchat windows'''
	
	path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps', 'muc_separator.png')
	FOCUS_OUT_LINE_PIXBUF = gtk.gdk.pixbuf_new_from_file(path_to_file)

	def __init__(self, account, used_in_history_window = False):
		'''if used_in_history_window is True, then we do not show
		Clear menuitem in context menu'''
		self.used_in_history_window = used_in_history_window
		
		# no need to inherit TextView, use it as atrribute is safer
		self.tv = HtmlTextView()
		self.tv.html_hyperlink_handler = self.html_hyperlink_handler

		# set properties
		self.tv.set_border_width(1)
		self.tv.set_accepts_tab(True)
		self.tv.set_editable(False)
		self.tv.set_cursor_visible(False)
		self.tv.set_wrap_mode(gtk.WRAP_WORD_CHAR)
		self.tv.set_left_margin(2)
		self.tv.set_right_margin(2)
		self.handlers = {}

		# connect signals
		id = self.tv.connect('motion_notify_event',
			self.on_textview_motion_notify_event)
		self.handlers[id] = self.tv
		id = self.tv.connect('populate_popup', self.on_textview_populate_popup)
		self.handlers[id] = self.tv
		id = self.tv.connect('button_press_event',
			self.on_textview_button_press_event)
		self.handlers[id] = self.tv

		self.account = account
		self.change_cursor = None
		self.last_time_printout = 0

		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.tv.modify_font(font)
		buffer = self.tv.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, False)

		self.tagIn = buffer.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		self.tagIn.set_property('foreground', color)
		self.tagOut = buffer.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		self.tagOut.set_property('foreground', color)
		self.tagStatus = buffer.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		self.tagStatus.set_property('foreground', color)

		colors = gajim.config.get('gc_nicknames_colors')
		colors = colors.split(':')
		for color in xrange(len(colors)):
			tagname = 'gc_nickname_color_' + str(color)
			tag = buffer.create_tag(tagname)
			color = colors[color]
			tag.set_property('foreground', color)

		tag = buffer.create_tag('marked')
		color = gajim.config.get('markedmsgcolor')
		tag.set_property('foreground', color)
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer.create_tag('time_sometimes')
		tag.set_property('foreground', 'darkgrey')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)

		tag = buffer.create_tag('small')
		tag.set_property('scale', pango.SCALE_SMALL)

		tag = buffer.create_tag('restored_message')
		color = gajim.config.get('restored_messages_color')
		tag.set_property('foreground', color)

		self.tagURL = buffer.create_tag('url')
		color = gajim.config.get('urlmsgcolor')
		self.tagURL.set_property('foreground', color)
		self.tagURL.set_property('underline', pango.UNDERLINE_SINGLE)
		id = self.tagURL.connect('event', self.hyperlink_handler, 'url')
		self.handlers[id] = self.tagURL

		self.tagMail = buffer.create_tag('mail')
		self.tagMail.set_property('foreground', color)
		self.tagMail.set_property('underline', pango.UNDERLINE_SINGLE)
		id = self.tagMail.connect('event', self.hyperlink_handler, 'mail')
		self.handlers[id] = self.tagMail

		tag = buffer.create_tag('bold')
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer.create_tag('italic')
		tag.set_property('style', pango.STYLE_ITALIC)

		tag = buffer.create_tag('underline')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)

		buffer.create_tag('focus-out-line', justification = gtk.JUSTIFY_CENTER)

		self.allow_focus_out_line = True
		# holds the iter's offset which points to the end of --- line
		self.focus_out_end_iter_offset = None

		self.line_tooltip = tooltips.BaseTooltip()
		# use it for hr too
		self.tv.focus_out_line_pixbuf = ConversationTextview.FOCUS_OUT_LINE_PIXBUF

	def del_handlers(self):
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
		del self.handlers
		self.tv.destroy()
		#FIXME:
		# self.line_tooltip.destroy()
	
	def update_tags(self):
		self.tagIn.set_property('foreground', gajim.config.get('inmsgcolor'))
		self.tagOut.set_property('foreground', gajim.config.get('outmsgcolor'))
		self.tagStatus.set_property('foreground',
			gajim.config.get('statusmsgcolor'))
		self.tagURL.set_property('foreground', gajim.config.get('urlmsgcolor'))
		self.tagMail.set_property('foreground', gajim.config.get('urlmsgcolor'))

	def at_the_end(self):
		buffer = self.tv.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = self.tv.get_iter_location(end_iter)
		visible_rect = self.tv.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			return True
		return False

	def scroll_to_end(self):
		parent = self.tv.get_parent()
		buffer = self.tv.get_buffer()
		end_mark = buffer.get_mark('end')
		if not end_mark:
			return False
		self.tv.scroll_to_mark(end_mark, 0, True, 0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		return False # when called in an idle_add, just do it once

	def bring_scroll_to_end(self, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		buffer = self.tv.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = self.tv.get_iter_location(end_iter)
		visible_rect = self.tv.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			gobject.idle_add(self.scroll_to_end_iter)

	def scroll_to_end_iter(self):
		buffer = self.tv.get_buffer()
		end_iter = buffer.get_end_iter()
		if not end_iter:
			return False
		self.tv.scroll_to_iter(end_iter, 0, False, 1, 1)
		return False # when called in an idle_add, just do it once

	def show_focus_out_line(self):
		if not self.allow_focus_out_line:
			# if room did not receive focus-in from the last time we added
			# --- line then do not readd
			return

		print_focus_out_line = False
		buffer = self.tv.get_buffer()

		if self.focus_out_end_iter_offset is None:
			# this happens only first time we focus out on this room
			print_focus_out_line = True

		else:
			if self.focus_out_end_iter_offset != buffer.get_end_iter().\
			get_offset():
				# this means after last-focus something was printed
				# (else end_iter's offset is the same as before)
				# only then print ---- line (eg. we avoid printing many following
				# ---- lines)
				print_focus_out_line = True

		if print_focus_out_line and buffer.get_char_count() > 0:
			buffer.begin_user_action()

			# remove previous focus out line if such focus out line exists
			if self.focus_out_end_iter_offset is not None:
				end_iter_for_previous_line = buffer.get_iter_at_offset(
					self.focus_out_end_iter_offset)
				begin_iter_for_previous_line = end_iter_for_previous_line.copy()
				# img_char+1 (the '\n')
				begin_iter_for_previous_line.backward_chars(2)

				# remove focus out line
				buffer.delete(begin_iter_for_previous_line,
					end_iter_for_previous_line)

			# add the new focus out line
			end_iter = buffer.get_end_iter()
			buffer.insert(end_iter, '\n')
			buffer.insert_pixbuf(end_iter, 
				ConversationTextview.FOCUS_OUT_LINE_PIXBUF)

			end_iter = buffer.get_end_iter()
			before_img_iter = end_iter.copy()
			before_img_iter.backward_char() # one char back (an image also takes one char)
			buffer.apply_tag_by_name('focus-out-line', before_img_iter, end_iter)

			self.allow_focus_out_line = False

			# update the iter we hold to make comparison the next time
			self.focus_out_end_iter_offset = buffer.get_end_iter().get_offset()

			buffer.end_user_action()

			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.scroll_to_end)

	def show_line_tooltip(self):
		pointer = self.tv.get_pointer()
		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer[0],
			pointer[1])
		tags = self.tv.get_iter_at_location(x, y).get_tags()
		tag_table = self.tv.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag == tag_table.lookup('focus-out-line'):
				over_line = True
				break
		if over_line and not self.line_tooltip.win:
			# check if the current pointer is still over the line
			position = self.tv.window.get_origin()
			self.line_tooltip.show_tooltip(_('Text below this line is what has '
			'been said since the last time you paid attention to this group chat'),	8, position[1] + pointer[1])

	def on_textview_motion_notify_event(self, widget, event):
		'''change the cursor to a hand when we are over a mail or an url'''
		pointer_x, pointer_y, spam = self.tv.window.get_pointer()
		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer_x,
			pointer_y)
		tags = self.tv.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = None
		tag_table = self.tv.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag in (tag_table.lookup('url'), tag_table.lookup('mail')):
				self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = tag
			elif tag == tag_table.lookup('focus-out-line'):
				over_line = True

		if self.line_tooltip.timeout != 0:
			# Check if we should hide the line tooltip
			if not over_line:
				self.line_tooltip.hide_tooltip()
		if over_line and not self.line_tooltip.win:
			self.line_tooltip.timeout = gobject.timeout_add(500,
				self.show_line_tooltip)
			self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
			self.change_cursor = tag

	def clear(self, tv = None):
		'''clear text in the textview'''
		buffer = self.tv.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.focus_out_end_iter_offset = None

	def visit_url_from_menuitem(self, widget, link):
		'''basically it filters out the widget instance'''
		helpers.launch_browser_mailer('url', link)

	def on_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		(only if used_in_history_window is False)
		and if we have sth selected we show a submenu with actions on the phrase
		(see on_conversation_textview_button_press_event)'''

		separator_menuitem_was_added = False
		if not self.used_in_history_window:
			item = gtk.SeparatorMenuItem()
			menu.prepend(item)
			separator_menuitem_was_added = True

			item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
			menu.prepend(item)
			id = item.connect('activate', self.clear)
			self.handlers[id] = item

		if self.selected_phrase:
			if not separator_menuitem_was_added:
				item = gtk.SeparatorMenuItem()
				menu.prepend(item)

			self.selected_phrase = helpers.reduce_chars_newlines(
				self.selected_phrase, 25, 2)
			item = gtk.MenuItem(_('_Actions for "%s"') % self.selected_phrase)
			menu.prepend(item)
			submenu = gtk.Menu()
			item.set_submenu(submenu)

			always_use_en = gajim.config.get('always_english_wikipedia')
			if always_use_en:
				link = 'http://en.wikipedia.org/wiki/Special:Search?search=%s'\
					% self.selected_phrase
			else:
				link = 'http://%s.wikipedia.org/wiki/Special:Search?search=%s'\
					% (gajim.LANG, self.selected_phrase)
			item = gtk.MenuItem(_('Read _Wikipedia Article'))
			id = item.connect('activate', self.visit_url_from_menuitem, link)
			self.handlers[id] = item
			submenu.append(item)

			item = gtk.MenuItem(_('Look it up in _Dictionary'))
			dict_link = gajim.config.get('dictionary_url')
			if dict_link == 'WIKTIONARY':
				# special link (yeah undocumented but default)
				always_use_en = gajim.config.get('always_english_wiktionary')
				if always_use_en:
					link = 'http://en.wiktionary.org/wiki/Special:Search?search=%s'\
						% self.selected_phrase
				else:
					link = 'http://%s.wiktionary.org/wiki/Special:Search?search=%s'\
						% (gajim.LANG, self.selected_phrase)
				id = item.connect('activate', self.visit_url_from_menuitem, link)
				self.handlers[id] = item
			else:
				if dict_link.find('%s') == -1:
					# we must have %s in the url if not WIKTIONARY
					item = gtk.MenuItem(_('Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
					item.set_property('sensitive', False)
				else:
					link = dict_link % self.selected_phrase
					id = item.connect('activate', self.visit_url_from_menuitem,
						link)
					self.handlers[id] = item
			submenu.append(item)


			search_link = gajim.config.get('search_engine')
			if search_link.find('%s') == -1:
				# we must have %s in the url
				item = gtk.MenuItem(_('Web Search URL is missing an "%s"'))
				item.set_property('sensitive', False)
			else:
				item = gtk.MenuItem(_('Web _Search for it'))
				link =  search_link % self.selected_phrase
				id = item.connect('activate', self.visit_url_from_menuitem, link)
				self.handlers[id] = item
			submenu.append(item)
			
			item = gtk.MenuItem(_('Open as _Link'))
			id = item.connect('activate', self.visit_url_from_menuitem, link)
			self.handlers[id] = item
			submenu.append(item)

		menu.show_all()

	def on_textview_button_press_event(self, widget, event):
		# If we clicked on a taged text do NOT open the standard popup menu
		# if normal text check if we have sth selected
		self.selected_phrase = '' # do not move belove event button check!

		if event.button != 3: # if not right click
			return False

		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			int(event.x), int(event.y))
		iter = self.tv.get_iter_at_location(x, y)
		tags = iter.get_tags()


		if tags: # we clicked on sth special (it can be status message too)
			for tag in tags:
				tag_name = tag.get_property('name')
				if tag_name in ('url', 'mail'):
					return True # we block normal context menu

		# we check if sth was selected and if it was we assign
		# selected_phrase variable
		# so on_conversation_textview_populate_popup can use it
		buffer = self.tv.get_buffer()
		return_val = buffer.get_selection_bounds()
		if return_val: # if sth was selected when we right-clicked
			# get the selected text
			start_sel, finish_sel = return_val[0], return_val[1]
			self.selected_phrase = buffer.get_text(start_sel, finish_sel).decode('utf-8')

	def on_open_link_activate(self, widget, kind, text):
		helpers.launch_browser_mailer(kind, text)

	def on_copy_link_activate(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def on_start_chat_activate(self, widget, jid):
		gajim.interface.roster.new_chat_from_jid(self.account, jid)

	def on_join_group_chat_menuitem_activate(self, widget, room_jid):
		if 'join_gc' in gajim.interface.instances[self.account]:
			instance = gajim.interface.instances[self.account]['join_gc']
			instance.xml.get_widget('room_jid_entry').set_text(room_jid)
			gajim.interface.instances[self.account]['join_gc'].window.present()
		else:
			try:
				gajim.interface.instances[self.account]['join_gc'] = \
				dialogs.JoinGroupchatWindow(self.account, room_jid)
			except GajimGeneralException:
				pass

	def on_add_to_roster_activate(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def make_link_menu(self, event, kind, text):
		xml = gtkgui_helpers.get_glade('chat_context_menu.glade')
		menu = xml.get_widget('chat_context_menu')
		childs = menu.get_children()
		if kind == 'url':
			id = childs[0].connect('activate', self.on_copy_link_activate, text)
			self.handlers[id] = childs[0]
			id = childs[1].connect('activate', self.on_open_link_activate, kind, text)
			self.handlers[id] = childs[1]
			childs[2].hide() # copy mail address
			childs[3].hide() # open mail composer
			childs[4].hide() # jid section separator
			childs[5].hide() # start chat
			childs[6].hide() # join group chat
			childs[7].hide() # add to roster
		else: # It's a mail or a JID
			# load muc icon
			join_group_chat_menuitem = xml.get_widget('join_group_chat_menuitem')
			muc_icon = gajim.interface.roster.load_icon('muc_active')
			if muc_icon: 
				join_group_chat_menuitem.set_image(muc_icon) 

			text = text.lower()
			id = childs[2].connect('activate', self.on_copy_link_activate, text)
			self.handlers[id] = childs[2]
			id = childs[3].connect('activate', self.on_open_link_activate, kind, text)
			self.handlers[id] = childs[3]
			id = childs[5].connect('activate', self.on_start_chat_activate, text)
			self.handlers[id] = childs[5]
			id = childs[6].connect('activate',
				self.on_join_group_chat_menuitem_activate, text)
			self.handlers[id] = childs[6]

			allow_add = False
			c = gajim.contacts.get_first_contact_from_jid(self.account, text)
			if c and not gajim.contacts.is_pm_from_contact(self.account, c):
				if _('Not in Roster') in c.groups:
					allow_add = True
			else: # he or she's not at all in the account contacts
				allow_add = True

			if allow_add:
				id = childs[7].connect('activate', self.on_add_to_roster_activate, text)
				self.handlers[id] = childs[7]
				childs[7].show() # show add to roster menuitem
			else:
				childs[7].hide() # hide add to roster menuitem

			childs[0].hide() # copy link location
			childs[1].hide() # open link in browser

		menu.popup(None, None, None, event.button, event.time)

	def hyperlink_handler(self, texttag, widget, event, iter, kind):
		if event.type == gtk.gdk.BUTTON_PRESS:
			begin_iter = iter.copy()
			# we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter.copy()
			# we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = self.tv.get_buffer().get_text(begin_iter, end_iter).decode('utf-8')
			if event.button == 3: # right click
				self.make_link_menu(event, kind, word)
			else:
				# we launch the correct application
				helpers.launch_browser_mailer(kind, word)

	def html_hyperlink_handler(self, texttag, widget, event, iter, kind, href):
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3: # right click
				self.make_link_menu(event, kind, href)
			else:
				# we launch the correct application
				helpers.launch_browser_mailer(kind, href)


	def detect_and_print_special_text(self, otext, other_tags):
		'''detects special text (emots & links & formatting)
		prints normal text before any special text it founts,
		then print special text (that happens many times until
		last special text is printed) and then returns the index
		after *last* special text, so we can print it in
		print_conversation_line()'''

		buffer = self.tv.get_buffer()

		start = 0
		end = 0
		index = 0

		# basic: links + mail + formatting is always checked (we like that)
		if gajim.config.get('emoticons_theme'): # search for emoticons & urls
			iterator = gajim.interface.emot_and_basic_re.finditer(otext)
		else: # search for just urls + mail + formatting
			iterator = gajim.interface.basic_pattern_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start != 0:
				text_before_special_text = otext[index:start]
				end_iter = buffer.get_end_iter()
				# we insert normal text
				buffer.insert_with_tags_by_name(end_iter,
					text_before_special_text, *other_tags)
			index = end # update index

			# now print it
			self.print_special_text(special_text, other_tags)

		return index # the position after *last* special text

	def print_special_text(self, special_text, other_tags):
		'''is called by detect_and_print_special_text and prints
		special text (emots, links, formatting)'''
		tags = []
		use_other_tags = True
		show_ascii_formatting_chars = \
			gajim.config.get('show_ascii_formatting_chars')
		buffer = self.tv.get_buffer()

		possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
		if gajim.config.get('emoticons_theme') and \
		possible_emot_ascii_caps in gajim.interface.emoticons.keys():
			# it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			end_iter = buffer.get_end_iter()
			anchor = buffer.create_child_anchor(end_iter)
			img = gtk.Image()
			animations = gajim.interface.emoticons_animations
			if not emot_ascii in animations:
				animations[emot_ascii] = gtk.gdk.PixbufAnimation(
					gajim.interface.emoticons[emot_ascii])
			img.set_from_animation(animations[emot_ascii])
			img.show()
			# add with possible animation
			self.tv.add_child_at_anchor(img, anchor)
		#FIXME: one day, somehow sync with regexp in gajim.py
		elif special_text.startswith('http://') or \
			special_text.startswith('www.') or \
			special_text.startswith('ftp://') or \
			special_text.startswith('ftp.') or \
			special_text.startswith('https://') or \
			special_text.startswith('gopher://') or \
			special_text.startswith('news://') or \
			special_text.startswith('ed2k://') or \
			special_text.startswith('irc://') or \
			special_text.startswith('sip:') or \
			special_text.startswith('magnet:'):
			# it's a url
			tags.append('url')
			use_other_tags = False
		elif special_text.startswith('mailto:') or \
		gajim.interface.sth_at_sth_dot_sth_re.match(special_text):
			# it's a mail
			tags.append('mail')
			use_other_tags = False
		elif special_text.startswith('*'): # it's a bold text
			tags.append('bold')
			if special_text[1] == '/' and special_text[-2] == '/' and len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove */ /*
			elif special_text[1] == '_' and special_text[-2] == '_' and len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove *_ _*
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove * *
		elif special_text.startswith('/'): # it's an italic text
			tags.append('italic')
			if special_text[1] == '*' and special_text[-2] == '*' and len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /* */
			elif special_text[1] == '_' and special_text[-2] == '_' and len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /_ _/
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove / /
		elif special_text.startswith('_'): # it's an underlined text
			tags.append('underline')
			if special_text[1] == '*' and special_text[-2] == '*' and len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _* *_
			elif special_text[1] == '/' and special_text[-2] == '/' and len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _/ /_
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove _ _
		else:
			#it's a url
			tags.append('url')
			use_other_tags = False

		if len(tags) > 0:
			end_iter = buffer.get_end_iter()
			all_tags = tags[:]
			if use_other_tags:
				all_tags += other_tags
			buffer.insert_with_tags_by_name(end_iter, special_text, *all_tags)

	def print_empty_line(self):
		buffer = self.tv.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.insert_with_tags_by_name(end_iter, '\n', 'eol')

	def print_conversation_line(self, text, jid, kind, name, tim,
	other_tags_for_name = [], other_tags_for_time = [], other_tags_for_text = [],
	subject = None, old_kind = None, xhtml = None):
		'''prints 'chat' type messages'''
		buffer = self.tv.get_buffer()
		buffer.begin_user_action()
		end_iter = buffer.get_end_iter()
		at_the_end = False
		if self.at_the_end():
			at_the_end = True

		if buffer.get_char_count() > 0:
			buffer.insert_with_tags_by_name(end_iter, '\n', 'eol')
		if kind == 'incoming_queue':
			kind = 'incoming'
		if old_kind == 'incoming_queue':
			old_kind = 'incoming'
		# print the time stamp
		if not tim:
			# We don't have tim for outgoing messages...
			tim = time.localtime()
		current_print_time = gajim.config.get('print_time')
		if current_print_time == 'always' and kind != 'info':
			timestamp_str = self.get_time_to_show(tim)
			timestamp = time.strftime(timestamp_str, tim)
			buffer.insert_with_tags_by_name(end_iter, timestamp,
				*other_tags_for_time)
		elif current_print_time == 'sometimes' and kind != 'info':
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = time.mktime(tim) - self.last_time_printout
			if seconds_passed > every_foo_seconds:
				self.last_time_printout = time.mktime(tim)
				end_iter = buffer.get_end_iter()
				if gajim.config.get('print_time_fuzzy') > 0:
					fc = FuzzyClock()
					fc.setTime(time.strftime('%H:%M', tim))
					ft = fc.getFuzzyTime(gajim.config.get('print_time_fuzzy'))
					tim_format = ft.decode(locale.getpreferredencoding())
				else:
					tim_format = self.get_time_to_show(tim)
				buffer.insert_with_tags_by_name(end_iter, tim_format + '\n',
					'time_sometimes')
		# kind = info, we print things as if it was a status: same color, ...
		if kind == 'info':
			kind = 'status'
		other_text_tag = self.detect_other_text_tag(text, kind)
		text_tags = other_tags_for_text[:] # create a new list
		if other_text_tag:
			# note that color of /me may be overwritten in gc_control
			text_tags.append(other_text_tag)
		else: # not status nor /me
			if gajim.config.get(
				'chat_merge_consecutive_nickname'):
				if kind != old_kind:
					self.print_name(name, kind, other_tags_for_name)
				else:
					self.print_real_text(gajim.config.get(
						'chat_merge_consecutive_nickname_indent'))
			else:
				self.print_name(name, kind, other_tags_for_name)
		self.print_subject(subject)
		self.print_real_text(text, text_tags, name, xhtml)

		# scroll to the end of the textview
		if at_the_end or kind == 'outgoing':
			# we are at the end or we are sending something
			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.scroll_to_end)

		buffer.end_user_action()

	def get_time_to_show(self, tim):
		'''Get the time, with the day before if needed and return it.
		It DOESN'T format a fuzzy time'''
		format = ''
		# get difference in days since epoch (86400 = 24*3600)
		# number of days since epoch for current time (in GMT) -
		# number of days since epoch for message (in GMT)
		diff_day = int(timegm(time.localtime())) / 86400 -\
			int(timegm(tim)) / 86400
		if diff_day == 0:
			day_str = ''
		elif diff_day == 1:
			day_str = _('Yesterday')
		else:
			#the number is >= 2
			# %i is day in year (1-365), %d (1-31) we want %i
			day_str = _('%i days ago') % diff_day
		if day_str:
			format += day_str + ' '
		timestamp_str = gajim.config.get('time_stamp')
		timestamp_str = helpers.from_one_line(timestamp_str)
		format += timestamp_str
		tim_format = time.strftime(format, tim)
		if locale.getpreferredencoding() != 'KOI8-R':
			# if tim_format comes as unicode because of day_str.
			# we convert it to the encoding that we want (and that is utf-8)
			tim_format = helpers.ensure_utf8_string(tim_format)
		return tim_format

	def detect_other_text_tag(self, text, kind):
		if kind == 'status':
			return kind
		elif text.startswith('/me ') or text.startswith('/me\n'):
			return kind

	def print_name(self, name, kind, other_tags_for_name):
		if name:
			buffer = self.tv.get_buffer()
			end_iter = buffer.get_end_iter()
			name_tags = other_tags_for_name[:] # create a new list
			name_tags.append(kind)
			before_str = gajim.config.get('before_nickname')
			before_str = helpers.from_one_line(before_str)
			after_str = gajim.config.get('after_nickname')
			after_str = helpers.from_one_line(after_str)
			format = before_str + name + after_str + ' '
			buffer.insert_with_tags_by_name(end_iter, format, *name_tags)

	def print_subject(self, subject):
		if subject: # if we have subject, show it too!
			subject = _('Subject: %s\n') % subject
			buffer = self.tv.get_buffer()
			end_iter = buffer.get_end_iter()
			buffer.insert(end_iter, subject)
			self.print_empty_line()

	def print_real_text(self, text, text_tags = [], name = None, xhtml = None):
		'''this adds normal and special text. call this to add text'''
		if xhtml:
			try:
				if name and (text.startswith('/me ') or text.startswith('/me\n')):
					xhtml = xhtml.replace('/me', '<dfn>%s</dfn>'% (name,), 1)
				self.tv.display_html(xhtml.encode('utf-8'))
				return
			except Exception, e:
				gajim.log.debug(str("Error processing xhtml")+str(e))
				gajim.log.debug(str("with |"+xhtml+"|"))

		buffer = self.tv.get_buffer()
		# /me is replaced by name if name is given
		if name and (text.startswith('/me ') or text.startswith('/me\n')):
			text = '* ' + name + text[3:]
		# detect urls formatting and if the user has it on emoticons
		index = self.detect_and_print_special_text(text, text_tags)

		# add the rest of text located in the index and after
		end_iter = buffer.get_end_iter()
		buffer.insert_with_tags_by_name(end_iter, text[index:], *text_tags)

