##	history_window.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <kourem@gmail.com>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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
import time
import calendar

import gtkgui_helpers
import conversation_textview

from common import gajim
from common import helpers

from common.logger import Constants

constants = Constants()

# contact_name, date, message, time
(
C_CONTACT_NAME,
C_UNIXTIME,
C_MESSAGE,
C_TIME
) = range(4)

class HistoryWindow:
	'''Class for browsing logs of conversations with contacts'''

	def __init__(self, jid, account):
		self.jid = jid
		self.account = account
		self.mark_days_idle_call_id = None
		
		xml = gtkgui_helpers.get_glade('history_window.glade')
		self.window = xml.get_widget('history_window')
		
		self.calendar = xml.get_widget('calendar')
		scrolledwindow = xml.get_widget('scrolledwindow')
		self.history_textview = conversation_textview.ConversationTextview(
			account, used_in_history_window = True)
		scrolledwindow.add(self.history_textview.tv)
		self.history_buffer = self.history_textview.tv.get_buffer()
		self.history_buffer.create_tag('highlight', background = 'yellow')
		self.query_entry = xml.get_widget('query_entry')
		self.search_button = xml.get_widget('search_button')
		query_builder_button = xml.get_widget('query_builder_button')
		query_builder_button.hide()
		query_builder_button.set_no_show_all(True)
		self.expander_vbox = xml.get_widget('expander_vbox')
		
		self.results_treeview = xml.get_widget('results_treeview')
		# contact_name, date, message, time
		model = gtk.ListStore(str, str, str, str)
		self.results_treeview.set_model(model)
		col = gtk.TreeViewColumn(_('Name'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_CONTACT_NAME)
		col.set_sort_column_id(C_CONTACT_NAME) # user can click this header and sort
		col.set_resizable(True)
		
		col = gtk.TreeViewColumn(_('Date'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)
		
		col = gtk.TreeViewColumn(_('Message'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_MESSAGE)
		col.set_resizable(True)
		
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if contact:
			title = _('Conversation History with %s') % contact.get_shown_name()
		else:
			title = _('Conversation History with %s') % jid
		self.window.set_title(title)
		
		xml.signal_autoconnect(self)
		
		# fake event so we start mark days procedure for selected month
		# selected month is current month as calendar defaults to selecting
		# current date
		self.calendar.emit('month-changed')

		# select and show logs for last date we have logs with contact
		# and if we don't have logs at all, default to today
		result = gajim.logger.get_last_date_that_has_logs(self.jid, self.account)
		if result is None:
			date = time.localtime()
		else:
			tim = result
			date = time.localtime(tim)

		y, m, d = date[0], date[1], date[2]
		gtk_month = gtkgui_helpers.make_python_month_gtk_month(m)
		self.calendar.select_month(gtk_month, y)
		self.calendar.select_day(d)
		self.add_lines_for_date(y, m, d)
		
		self.window.show_all()

	def on_history_window_destroy(self, widget):
		if self.mark_days_idle_call_id:
			# if user destroys the window, and we have a generator filling mark days
			# stop him!
			gobject.source_remove(self.mark_days_idle_call_id)
		self.history_textview.del_handlers()
		del gajim.interface.instances['logs'][self.jid]

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_calendar_day_selected(self, widget):
		year, month, day = widget.get_date() # integers
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		self.add_lines_for_date(year, month, day)
		
	def do_possible_mark_for_days_in_this_month(self, widget, year, month):
		'''this is a generator and does pseudo-threading via idle_add()
		so it runs progressively! yea :)
		asks for days in this month if they have logs it bolds them (marks them)'''
		weekday, days_in_this_month = calendar.monthrange(year, month)
		log_days = gajim.logger.get_days_with_logs(self.jid, year,
			month, days_in_this_month, self.account)
		for day in log_days:
			widget.mark_day(day)
			yield True
		yield False
	
	def on_calendar_month_changed(self, widget):
		year, month, day = widget.get_date() # integers
		# in gtk January is 1, in python January is 0,
		# I want the second
		# first day of month is 1 not 0
		if self.mark_days_idle_call_id:
			# if user changed month, and we have a generator filling mark days
			# stop him from marking dates for the previously selected month
			gobject.source_remove(self.mark_days_idle_call_id)
		widget.clear_marks()
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		self.mark_days_idle_call_id = gobject.idle_add(
			self.do_possible_mark_for_days_in_this_month(widget, year, month).next)

	def get_string_show_from_constant_int(self, show):
		if show == constants.SHOW_ONLINE:
			show = 'online'
		elif show == constants.SHOW_CHAT:
			show = 'chat'
		elif show == constants.SHOW_AWAY:
			show = 'away'
		elif show == constants.SHOW_XA:
			show = 'xa'
		elif show == constants.SHOW_DND:
			show = 'dnd'
		elif show == constants.SHOW_OFFLINE:
			show = 'offline'

		return show

	def add_lines_for_date(self, year, month, day):
		'''adds all the lines for given date in textbuffer'''
		self.history_buffer.set_text('') # clear the buffer first
		self.last_time_printout = 0

		lines = gajim.logger.get_conversation_for_date(self.jid, year, month, day, self.account)
		# lines holds list with tupples that have:
		# contact_name, time, kind, show, message
		for line in lines:
			# line[0] is contact_name, line[1] is time of message
			# line[2] is kind, line[3] is show, line[4] is message
			self.add_new_line(line[0], line[1], line[2], line[3], line[4])
	
	def add_new_line(self, contact_name, tim, kind, show, message):
		'''add a new line in textbuffer'''
		if not message and kind not in (constants.KIND_STATUS,
			constants.KIND_GCSTATUS):
			return
		buf = self.history_buffer
		end_iter = buf.get_end_iter()
		
		if gajim.config.get('print_time') == 'always':
			timestamp_str = gajim.config.get('time_stamp')
			timestamp_str = helpers.from_one_line(timestamp_str)
			tim = time.strftime(timestamp_str, time.localtime(float(tim)))
			buf.insert(end_iter, tim) # add time
		elif gajim.config.get('print_time') == 'sometimes':
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = tim - self.last_time_printout
			if seconds_passed > every_foo_seconds:
				self.last_time_printout = tim
				tim = time.strftime('%X ', time.localtime(float(tim)))
				buf.insert_with_tags_by_name(end_iter, tim + '\n',
					'time_sometimes')

		tag_name = ''
		tag_msg = ''
		
		show = self.get_string_show_from_constant_int(show)
		
		if kind == constants.KIND_GC_MSG:
			tag_name = 'incoming'
		elif kind in (constants.KIND_SINGLE_MSG_RECV,
		constants.KIND_CHAT_MSG_RECV):
			contact = gajim.contacts.get_first_contact_from_jid(self.account,
				self.jid)
			if contact:
				# he is in our roster, use the name
				contact_name = contact.get_shown_name()
			else:
				room_jid, nick = gajim.get_room_and_nick_from_fjid(self.jid)
				# do we have him as gc_contact?
				gc_contact = gajim.contacts.get_gc_contact(self.account, room_jid,
					nick)
				if gc_contact:
					# so yes, it's pm!
					contact_name = nick
				else:
					contact_name = self.jid.split('@')[0]
			tag_name = 'incoming'
		elif kind in (constants.KIND_SINGLE_MSG_SENT,
		constants.KIND_CHAT_MSG_SENT):
			contact_name = gajim.nicks[self.account]
			tag_name = 'outgoing'
		elif kind == constants.KIND_GCSTATUS:
			# message here (if not None) is status message
			if message:
				message = _('%(nick)s is now %(status)s: %(status_msg)s') %\
					{'nick': contact_name, 'status': helpers.get_uf_show(show),
					'status_msg': message }
			else:
				message = _('%(nick)s is now %(status)s') % {'nick': contact_name,
					'status': helpers.get_uf_show(show) }
			tag_msg = 'status'
		else: # 'status'
			# message here (if not None) is status message
			if message:
				message = _('Status is now: %(status)s: %(status_msg)s') % \
					{'status': helpers.get_uf_show(show), 'status_msg': message}
			else:
				message = _('Status is now: %(status)s') % { 'status':
					helpers.get_uf_show(show) }
			tag_msg = 'status'

		# do not do this if gcstats, avoid dupping contact_name
		# eg. nkour: nkour is now Offline
		if contact_name and kind != constants.KIND_GCSTATUS:
			# add stuff before and after contact name
			before_str = gajim.config.get('before_nickname')
			before_str = helpers.from_one_line(before_str)
			after_str = gajim.config.get('after_nickname')
			after_str = helpers.from_one_line(after_str)
			format = before_str + contact_name + after_str + ' '
			buf.insert_with_tags_by_name(end_iter, format, tag_name)

		message = message + '\n'
		if tag_msg:
			self.history_textview.print_real_text(message, [tag_msg])
		else:
			self.history_textview.print_real_text(message)

	def set_unset_expand_on_expander(self, widget):
		'''expander has to have expand to TRUE so scrolledwindow resizes properly
		and does not have a static size. when expander is not expanded we set
		expand property (note the Box one) to FALSE
		to do this, we first get the box and then apply to expander widget
		the True/False thingy depending if it's expanded or not
		this function is called in a timeout just after expanded state changes'''
		parent = widget.get_parent() # vbox
		expanded = widget.get_expanded()
		w, h = self.window.get_size()
		if expanded: # resize to larger in height the window
			self.window.resize(w, int(h*1.3))
		else: # resize to smaller in height the window
			self.window.resize(w, int(h/1.3))
		# now set expand so if manually resizing scrolledwindow resizes too
		parent.child_set_property(widget, 'expand', expanded)
	
	def on_search_expander_activate(self, widget):
		if widget.get_expanded(): # it's the OPPOSITE!, it's not expanded
			gobject.timeout_add(200, self.set_unset_expand_on_expander, widget)
		else:
			gobject.timeout_add(200, self.set_unset_expand_on_expander, widget)
			self.search_button.grab_default()
			self.query_entry.grab_focus()
	
	def on_search_button_clicked(self, widget):
		text = self.query_entry.get_text()
		model = self.results_treeview.get_model()
		model.clear()
		if text == '':
			return
		# contact_name, time, kind, show, message, subject
		results = gajim.logger.get_search_results_for_query(
						self.jid, text, self.account)
		#FIXME:
		# add "subject:  | message: " in message column if kind is single
		# also do we need show at all? (we do not search on subject)
		for row in results:
			contact_name = row[0]
			if not contact_name:
				kind = row[2]
				if kind == constants.KIND_CHAT_MSG_SENT: # it's us! :)
					contact_name = gajim.nicks[self.account]
				else:
					contact = gajim.contacts.get_first_contact_from_jid(self.account,
						self.jid)
					if contact:
						contact_name = contact.get_shown_name()
					else:
						contact_name = self.jid
			tim = row[1]
			message = row[4]
			local_time = time.localtime(tim)
			date = time.strftime('%x', local_time)
			# name, date, message, time (full unix time)
			model.append((contact_name, date, message, tim))
			
	def on_results_treeview_row_activated(self, widget, path, column):
		'''a row was double clicked, get date from row, and select it in calendar
		which results to showing conversation logs for that date'''
		# get currently selected date
		cur_year, cur_month, cur_day = self.calendar.get_date()
		cur_month = gtkgui_helpers.make_gtk_month_python_month(cur_month)
		model = widget.get_model()
		# make it a tupple (Y, M, D, 0, 0, 0...)
		tim = time.strptime(model[path][C_UNIXTIME], '%x')
		year = tim[0]
		gtk_month = tim[1]
		month = gtkgui_helpers.make_python_month_gtk_month(gtk_month)
		day = tim[2]
		
		# avoid reruning mark days algo if same month and year!
		if year != cur_year or gtk_month != cur_month:
			self.calendar.select_month(month, year)
		
		self.calendar.select_day(day)
		unix_time = model[path][C_TIME]
		self.scroll_to_result(unix_time)
		#FIXME: one day do not search just for unix_time but the whole and user
		# specific format of the textbuffer line [time] nick: message
		# and highlight all that

	def scroll_to_result(self, unix_time):
		'''scrolls to the result using unix_time and highlight line'''
		start_iter = self.history_buffer.get_start_iter()
		local_time = time.localtime(float(unix_time))
		tim = time.strftime('%X', local_time)
		result = start_iter.forward_search(tim, gtk.TEXT_SEARCH_VISIBLE_ONLY,
			None)
		if result is not None:
			match_start_iter, match_end_iter = result
			match_start_iter.backward_char() # include '[' or other character before time
			match_end_iter.forward_line() # highlight all message not just time
			self.history_buffer.apply_tag_by_name('highlight', match_start_iter,
				match_end_iter)
				
			match_start_mark = self.history_buffer.create_mark('match_start',
				match_start_iter, True)
			self.history_textview.tv.scroll_to_mark(match_start_mark, 0, True)
