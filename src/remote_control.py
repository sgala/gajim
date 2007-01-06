##	remote_control.py
##
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2005-2006 Andrew Sayman <lorien420@myrealbox.com>
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

import gobject
import os

from common import gajim
from common import helpers
from time import time
from dialogs import AddNewContactWindow, NewChatDialog, JoinGroupchatWindow

from common import dbus_support
if dbus_support.supported:
	import dbus
	if dbus_support:
		import dbus.service
		import dbus.glib

INTERFACE = 'org.gajim.dbus.RemoteInterface'
OBJ_PATH = '/org/gajim/dbus/RemoteObject'
SERVICE = 'org.gajim.dbus'

# type mapping

# in most cases it is a utf-8 string
DBUS_STRING = dbus.String

# general type (for use in dicts, where all values should have the same type)
DBUS_BOOLEAN = dbus.Boolean
DBUS_DOUBLE = dbus.Double
DBUS_INT32 = dbus.Int32
# dictionary with string key and binary value
DBUS_DICT_SV = lambda : dbus.Dictionary({}, signature="sv")
# dictionary with string key and value
DBUS_DICT_SS = lambda : dbus.Dictionary({}, signature="ss")
# empty type (there is no equivalent of None on D-Bus, but historically gajim
# used 0 instead)
DBUS_NONE = lambda : dbus.Int32(0)

def get_dbus_struct(obj):
	''' recursively go through all the items and replace
	them with their casted dbus equivalents
	'''
	if obj is None:
		return DBUS_NONE()
	if isinstance(obj, (unicode, str)):
		return DBUS_STRING(obj)
	if isinstance(obj, int):
		return DBUS_INT32(obj)
	if isinstance(obj, float):
		return DBUS_DOUBLE(obj)
	if isinstance(obj, bool):
		return DBUS_BOOLEAN(obj)
	if isinstance(obj, (list, tuple)):
		result = dbus.Array([get_dbus_struct(i) for i in obj],
			signature='v')
		if result == []:
			return DBUS_NONE()
		return result
	if isinstance(obj, dict):
		result = DBUS_DICT_SV()
		for key, value in obj.items():
			result[DBUS_STRING(key)] = get_dbus_struct(value)
		if result == {}:
			return DBUS_NONE()
		return result
	# unknown type
	return DBUS_NONE() 

class Remote:
	def __init__(self):
		self.signal_object = None
		session_bus = dbus_support.session_bus.SessionBus()

		service = dbus.service.BusName(SERVICE, bus=session_bus)
		self.signal_object = SignalObject(service)

	def raise_signal(self, signal, arg):
		if self.signal_object:
			getattr(self.signal_object, signal)(get_dbus_struct(arg))


class SignalObject(dbus.service.Object):
	''' Local object definition for /org/gajim/dbus/RemoteObject.
	(This docstring is not be visible, because the clients can access only the remote object.)'''

	def __init__(self, service):
		self.first_show = True
		self.vcard_account = None

		# register our dbus API
		dbus.service.Object.__init__(self, service, OBJ_PATH)

	# FIXME: what are the signatures for these signals?

	@dbus.service.signal(INTERFACE)
	def Roster(self, account_and_data):
		pass

	@dbus.service.signal(INTERFACE)
	def AccountPresence(self, status_and_account):
		pass

	@dbus.service.signal(INTERFACE)
	def ContactPresence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def ContactAbsence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def NewMessage(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def Subscribe(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def Subscribed(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def Unsubscribed(self, account_and_jid):
		pass

	@dbus.service.signal(INTERFACE)
	def NewAccount(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def VcardInfo(self, account_and_vcard):
		pass

	@dbus.service.signal(INTERFACE)
	def LastStatusTime(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def OsInfo(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def GCPresence(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def GCMessage(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def RosterInfo(self, account_and_array):
		pass

	@dbus.service.signal(INTERFACE)
	def NewGmail(self, account_and_array):
		pass

	def raise_signal(self, signal, arg):
		'''raise a signal, with a single argument of unspecified type

		Instead of obj.raise_signal("Foo", bar), use obj.Foo(bar).'''
		getattr(self, signal)(arg)

	# FIXME: can't specify any introspect signature for any of these
	# since they take a variable number of arguments (this is not
	# recommended in a D-Bus interface)

	@dbus.service.method(INTERFACE)
	def get_status(self, *args):
		'''get_status(account = None)
		returns status (show to be exact) which is the global one
		unless account is given'''
		account = self._get_real_arguments(args, 1)[0]
		if not account:
			# If user did not ask for account, returns the global status
			return helpers.get_global_show()
		# return show for the given account
		index = gajim.connections[account].connected
		return DBUS_STRING(gajim.SHOW_LIST[index])

	@dbus.service.method(INTERFACE)
	def get_status_message(self, *args):
		'''get_status(account = None)
		returns status which is the global one
		unless account is given'''
		account = self._get_real_arguments(args, 1)[0]
		if not account:
			# If user did not ask for account, returns the global status
			return str(helpers.get_global_status())
		# return show for the given account
		status = gajim.connections[account].status
		return DBUS_STRING(status)

	@dbus.service.method(INTERFACE)
	def get_account_and_contact(self, account, jid):
		''' get the account (if not given) and contact instance from jid'''
		connected_account = None
		contact = None
		accounts = gajim.contacts.get_accounts()
		# if there is only one account in roster, take it as default
		# if user did not ask for account
		if not account and len(accounts) == 1:
			account = accounts[0]
		if account:
			if gajim.connections[account].connected > 1: # account is connected
				connected_account = account
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
		else:
			for account in accounts:
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
				if contact and gajim.connections[account].connected > 1:
					# account is connected
					connected_account = account
					break
		if not contact:
			contact = jid

		return connected_account, contact

	@dbus.service.method(INTERFACE)
	def send_file(self, *args):
		'''send_file(file_path, jid, account=None) 
		send file, located at 'file_path' to 'jid', using account 
		(optional) 'account' '''
		file_path, jid, account = self._get_real_arguments(args, 3)
		jid = self._get_real_jid(jid, account)
		connected_account, contact = self.get_account_and_contact(account, jid)

		if connected_account:
			if file_path[:7] == 'file://':
				file_path=file_path[7:]
			if os.path.isfile(file_path): # is it file?
				gajim.interface.instances['file_transfers'].send_file(
					connected_account, contact, file_path)
				return True
		return False

	def _send_message(self, jid, message, keyID, account, type = 'chat', subject = None):
		'''can be called from send_chat_message (default when send_message)
		or send_single_message'''
		if not jid or not message:
			return None # or raise error
		if not keyID:
			keyID = ''

		connected_account, contact = self.get_account_and_contact(account, jid)
		if connected_account:
			connection = gajim.connections[connected_account]
			connection.send_message(jid, message, keyID, type, subject)
			return True
		return False

	@dbus.service.method(INTERFACE)
	def send_chat_message(self, *args):
		'''send_message(jid, message, keyID=None, account=None)
		send chat 'message' to 'jid', using account (optional) 'account'.
		if keyID is specified, encrypt the message with the pgp key '''
		jid, message, keyID, account = self._get_real_arguments(args, 4)
		jid = self._get_real_jid(jid, account)
		return self._send_message(jid, message, keyID, account)

	@dbus.service.method(INTERFACE)
	def send_single_message(self, *args):
		'''send_single_message(jid, subject, message, keyID=None, account=None)
		send single 'message' to 'jid', using account (optional) 'account'.
		if keyID is specified, encrypt the message with the pgp key '''
		jid, subject, message, keyID, account = self._get_real_arguments(args, 5)
		jid = self._get_real_jid(jid, account)
		return self._send_message(jid, message, keyID, account, type, subject)

	@dbus.service.method(INTERFACE)
	def open_chat(self, *args):
		''' start_chat(jid, account=None) -> shows the tabbed window for new 
		message to 'jid', using account(optional) 'account' '''
		jid, account = self._get_real_arguments(args, 2)
		if not jid:
			raise MissingArgument
			return None
		jid = self._get_real_jid(jid, account)
		try:
			jid = helpers.parse_jid(jid)
		except:
			# Jid is not conform, ignore it
			return None

		if account:
			accounts = [account]
		else:
			accounts = gajim.connections.keys()
			if len(accounts) == 1:
				account = accounts[0]
		connected_account = None
		first_connected_acct = None
		for acct in accounts:
			if gajim.connections[acct].connected > 1: # account is  online
				contact = gajim.contacts.get_first_contact_from_jid(acct, jid)
				if gajim.interface.msg_win_mgr.has_window(jid, acct):
					connected_account = acct
					break
				# jid is in roster
				elif contact:
					connected_account = acct
					break
				# we send the message to jid not in roster, because account is
				# specified, or there is only one account
				elif account: 
					connected_account = acct
				elif first_connected_acct is None:
					first_connected_acct = acct

		# if jid is not a conntact, open-chat with first connected account
		if connected_account is None and first_connected_acct:
			connected_account = first_connected_acct

		if connected_account:
			gajim.interface.roster.new_chat_from_jid(connected_account, jid)
			# preserve the 'steal focus preservation'
			win = gajim.interface.msg_win_mgr.get_window(jid, connected_account).window
			if win.get_property('visible'):
				win.window.focus()
			return True
		return False

	@dbus.service.method(INTERFACE)
	def change_status(self, *args, **keywords):
		''' change_status(status, message, account). account is optional -
		if not specified status is changed for all accounts. '''
		status, message, account = self._get_real_arguments(args, 3)
		if status not in ('offline', 'online', 'chat', 
			'away', 'xa', 'dnd', 'invisible'):
			raise InvalidArgument
			return None
		if account:
			gobject.idle_add(gajim.interface.roster.send_status, account, 
				status, message)
		else:
			# account not specified, so change the status of all accounts
			for acc in gajim.contacts.get_accounts():
				if not gajim.config.get_per('accounts', acc, 'sync_with_global_status'):
					continue
				gobject.idle_add(gajim.interface.roster.send_status, acc, 
					status, message)
		return None

	@dbus.service.method(INTERFACE)
	def show_next_pending_event(self, *args):
		'''Show the window(s) with next pending event in tabbed/group chats.'''
		if gajim.events.get_nb_events():
			gajim.interface.systray.handle_first_event()

	@dbus.service.method(INTERFACE)
	def contact_info(self, *args):
		'''get vcard info for a contact. Return cached value of the vcard.
		'''
		[jid] = self._get_real_arguments(args, 1)
		if not isinstance(jid, unicode):
			jid = unicode(jid)
		if not jid:
			raise MissingArgument
			return None
		jid = self._get_real_jid(jid)

		cached_vcard = gajim.connections.values()[0].get_cached_vcard(jid)
		if cached_vcard:
			return get_dbus_struct(cached_vcard)

		# return empty dict
		return DBUS_DICT_SV()

	@dbus.service.method(INTERFACE)
	def list_accounts(self, *args):
		'''list register accounts'''
		result = gajim.contacts.get_accounts()
		if result and len(result) > 0:
			result_array = []
			for account in result:
				result_array.append(DBUS_STRING(account))
			return result_array
		return None

	@dbus.service.method(INTERFACE)
	def account_info(self, *args):
		'''show info on account: resource, jid, nick, prio, message'''
		[for_account] = self._get_real_arguments(args, 1)
		if not gajim.connections.has_key(for_account):
			# account is invalid
			return None
		account = gajim.connections[for_account]
		result = DBUS_DICT_SS()
		index = account.connected
		result['status'] = DBUS_STRING(gajim.SHOW_LIST[index])
		result['name'] = DBUS_STRING(account.name)
		result['jid'] = DBUS_STRING(gajim.get_jid_from_account(account.name))
		result['message'] = DBUS_STRING(account.status)
		result['priority'] = DBUS_STRING(unicode(account.priority))
		result['resource'] = DBUS_STRING(unicode(gajim.config.get_per('accounts', 
			account.name, 'resource')))
		return result

	@dbus.service.method(INTERFACE)
	def list_contacts(self, *args):
		'''list all contacts in the roster. If the first argument is specified,
		then return the contacts for the specified account'''
		[for_account] = self._get_real_arguments(args, 1)
		result = []
		accounts = gajim.contacts.get_accounts()
		if len(accounts) == 0:
			return None
		if for_account:
			accounts_to_search = [for_account]
		else:
			accounts_to_search = accounts
		for account in accounts_to_search:
			if account in accounts:
				for jid in gajim.contacts.get_jid_list(account):
					item = self._contacts_as_dbus_structure(
						gajim.contacts.get_contact(account, jid))
					if item:
						result.append(item)
		# dbus 0.40 does not support return result as empty list
		if result == []:
			return None
		return result

	@dbus.service.method(INTERFACE)
	def toggle_roster_appearance(self, *args):
		''' shows/hides the roster window '''
		win = gajim.interface.roster.window
		if win.get_property('visible'):
			gobject.idle_add(win.hide)
		else:
			win.present()
			# preserve the 'steal focus preservation'
			if self._is_first():
				win.window.focus()
			else:
				win.window.focus(long(time()))

	@dbus.service.method(INTERFACE)
	def prefs_list(self, *args):
		prefs_dict = DBUS_DICT_SS()
		def get_prefs(data, name, path, value):
			if value is None:
				return
			key = ""
			if path is not None:
				for node in path:
					key += node + "#"
			key += name
			prefs_dict[DBUS_STRING(key)] = DBUS_STRING(value[1])
		gajim.config.foreach(get_prefs)
		return prefs_dict

	@dbus.service.method(INTERFACE)
	def prefs_store(self, *args):
		try:
			gajim.interface.save_config()
		except Exception, e:
			return False
		return True

	@dbus.service.method(INTERFACE)
	def prefs_del(self, *args):
		[key] = self._get_real_arguments(args, 1)
		if not key:
			return False
		key_path = key.split('#', 2)
		if len(key_path) != 3:
			return False
		if key_path[2] == '*':
			gajim.config.del_per(key_path[0], key_path[1])
		else:
			gajim.config.del_per(key_path[0], key_path[1], key_path[2])
		return True

	@dbus.service.method(INTERFACE)
	def prefs_put(self, *args):
		[key] = self._get_real_arguments(args, 1)
		if not key:
			return False
		key_path = key.split('#', 2)
		if len(key_path) < 3:
			subname, value = key.split('=', 1)
			gajim.config.set(subname, value)
			return True
		subname, value = key_path[2].split('=', 1)
		gajim.config.set_per(key_path[0], key_path[1], subname, value)
		return True

	@dbus.service.method(INTERFACE)
	def add_contact(self, *args):
		[jid, account] = self._get_real_arguments(args, 2)
		if account:
			if account in gajim.connections and \
				gajim.connections[account].connected > 1:
				# if given account is active, use it 
				AddNewContactWindow(account = account, jid = jid)
			else:
				# wrong account
				return False
		else:
			# if account is not given, show account combobox
			AddNewContactWindow(account = None, jid = jid)
		return True

	@dbus.service.method(INTERFACE)
	def remove_contact(self, *args):
		[jid, account] = self._get_real_arguments(args, 2)
		jid = self._get_real_jid(jid, account)
		accounts = gajim.contacts.get_accounts()

		# if there is only one account in roster, take it as default
		if account:
			accounts = [account]
		contact_exists = False
		for account in accounts:
			contacts = gajim.contacts.get_contact(account, jid)
			if contacts:
				gajim.connections[account].unsubscribe(jid)
				for contact in contacts:
					gajim.interface.roster.remove_contact(contact, account)
				gajim.contacts.remove_jid(account, jid)
				contact_exists = True
		return contact_exists

	def _is_first(self):
		if self.first_show:
			self.first_show = False
			return True
		return False

	def _get_real_arguments(self, args, desired_length):
		''' extend, or descend the length of args to match desired_length 
		'''
		args = list(args)
		for i in range(len(args)):
			if args[i]: 
				args[i] = unicode(args[i])
			else:
				args[i] = None
		if desired_length > 0:
			args.extend([None] * (desired_length - len(args)))
			args = args[:desired_length]
		return args

	def _get_real_jid(self, jid, account = None):
		'''get the real jid from the given one: removes xmpp: or get jid from nick
		if account is specified, search only in this account
		'''
		if account:
			accounts = [account]
		else:
			accounts = gajim.connections.keys()
		if jid.startswith('xmpp:'):
			return jid[5:] # len('xmpp:') = 5
		nick_in_roster = None # Is jid a nick ?
		for account in accounts:
			# Does jid exists in roster of one account ?
			if gajim.contacts.get_contacts_from_jid(account, jid):
				return jid
			if not nick_in_roster:
				# look in all contact if one has jid as nick
				for jid_ in gajim.contacts.get_jid_list(account):
					c = gajim.contacts.get_contacts_from_jid(account, jid_)
					if c[0].name == jid:
						nick_in_roster = jid_
						break
		if nick_in_roster:
			# We have not found jid in roster, but we found is as a nick
			return nick_in_roster
		# We have not found it as jid nor as nick, probably a not in roster jid
		return jid

	def _contacts_as_dbus_structure(self, contacts):
		''' get info from list of Contact objects and create dbus dict '''
		if not contacts:
			return None
		prim_contact = None # primary contact
		for contact in contacts:
			if prim_contact == None or contact.priority > prim_contact.priority:
				prim_contact = contact
		contact_dict = DBUS_DICT_SV()
		contact_dict['name'] = DBUS_STRING(prim_contact.name)
		contact_dict['show'] = DBUS_STRING(prim_contact.show)
		contact_dict['jid'] = DBUS_STRING(prim_contact.jid)
		if prim_contact.keyID:
			keyID = None
			if len(prim_contact.keyID) == 8:
				keyID = prim_contact.keyID
			elif len(prim_contact.keyID) == 16:
				keyID = prim_contact.keyID[8:]
			if keyID:
				contact_dict['openpgp'] = keyID
		contact_dict['resources'] = dbus.Array([], signature='(sis)')
		for contact in contacts:
			resource_props = dbus.Struct((DBUS_STRING(contact.resource), contact.priority, DBUS_STRING(contact.status)), signature='sis')
			contact_dict['resources'].append(resource_props)
		return contact_dict

	@dbus.service.method(INTERFACE)
	def get_unread_msgs_number(self, *args):
		return str(gajim.events.get_nb_events())

	@dbus.service.method(INTERFACE)
	def start_chat(self, *args):
		[account] = self._get_real_arguments(args, 1)
		if not account:
			# error is shown in gajim-remote check_arguments(..)
			return None
		NewChatDialog(account)
		return True

	@dbus.service.method(INTERFACE)
	def send_xml(self, *args):
		xml, account = self._get_real_arguments(args, 2)
		if account:
			gajim.connections[account[0]].send_stanza(xml)
		else:
			for acc in gajim.contacts.get_accounts():
				gajim.connections[acc].send_stanza(xml)

	@dbus.service.method(INTERFACE)
	def join_room(self, *args):
		room_jid, nick, passwd, account = self._get_real_arguments(args, 4)
		if not account:
			# get the first connected account
			accounts = gajim.connections.keys()
			for acct in accounts:
				if gajim.account_is_connected(acct):
					account = acct
					break
			if not account:
				account = gajim.contacts.get_accounts()[0]
		if nick is None:
			nick = ''
			gajim.interface.instances[account]['join_gc'] = \
					JoinGroupchatWindow(account, room_jid, nick)
		else:
			gajim.connections[account].join_gc(nick, room_jid, password)
