## common/contacts.py
##
## Copyright (C) 2006 Yann Leboulanger <asterix@lagaule.org>
##                    Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2007 Lukas Petrovicky <lukas@petrovicky.net>
##                    Julien Pivotto <roidelapluie@gmail.com>
##                    Stephan Erb <steve-e@h3c.de> 
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

import common.gajim

class Contact:
	'''Information concerning each contact'''
	def __init__(self, jid='', name='', groups=[], show='', status='', sub='',
	ask='', resource='', priority=0, keyID='', our_chatstate=None,
	chatstate=None, last_status_time=None, msg_id = None, composing_xep = None):
		self.jid = jid
		self.name = name
		self.contact_name = '' # nick choosen by contact
		self.groups = groups
		self.show = show
		self.status = status
		# FIXME
		self.mood = dict()
		self.activity = dict()
		self.tune = dict()
		self.sub = sub
		self.ask = ask
		self.resource = resource
		self.priority = priority
		self.keyID = keyID

		# Capabilities; filled by caps.py/ConnectionCaps object
		# every time it gets these from presence stanzas
		self.caps_node = None
		self.caps_ver = None
		self.caps_exts = None

		# please read jep-85 http://www.jabber.org/jeps/jep-0085.html
		# we keep track of jep85 support with the peer by three extra states:
		# None, False and 'ask'
		# None if no info about peer
		# False if peer does not support jep85
		# 'ask' if we sent the first 'active' chatstate and are waiting for reply
		# this holds what WE SEND to contact (our current chatstate)
		self.our_chatstate = our_chatstate
		self.msg_id = msg_id
		# tell which JEP we're using for composing state
		# None = have to ask, XEP-0022 = use this jep,
		# XEP-0085 = use this jep, False = no composing support
		self.composing_xep = composing_xep
		# this is contact's chatstate
		self.chatstate = chatstate
		self.last_status_time = last_status_time

	def get_full_jid(self):
		if self.resource:
			return self.jid + '/' + self.resource
		return self.jid

	def get_shown_name(self):
		if self.name:
			return self.name
		if self.contact_name:
			return self.contact_name
		return self.jid.split('@')[0]

	def is_hidden_from_roster(self):
		'''if contact should not be visible in roster'''
		# XEP-0162: http://www.xmpp.org/extensions/xep-0162.html
		if self.is_transport():
			return False
		if self.sub in ('both', 'to'):
			return False
		if self.sub in ('none', 'from') and self.ask == 'subscribe':
			return False
		if self.sub in ('none', 'from') and (self.name or len(self.groups)):
			return False
		if _('Not in Roster') in self.groups:
			return False
		return True

	def is_observer(self):
		# XEP-0162: http://www.xmpp.org/extensions/xep-0162.html
		is_observer = False
		if self.sub == 'from' and not self.is_transport()\
		and self.is_hidden_from_roster():
			is_observer = True
		return is_observer

	def is_groupchat(self):
		if _('Groupchats') in self.groups:
			return True
		return False

	def is_transport(self):
		# if not '@' or '@' starts the jid then contact is transport
		if self.jid.find('@') <= 0:
			return True
		return False


class GC_Contact:
	'''Information concerning each groupchat contact'''
	def __init__(self, room_jid='', name='', show='', status='', role='',
	affiliation='', jid = '', resource = ''):
		self.room_jid = room_jid
		self.name = name
		self.show = show
		self.status = status
		self.role = role
		self.affiliation = affiliation
		self.jid = jid
		self.resource = resource

	def get_full_jid(self):
		return self.room_jid + '/' + self.name

	def get_shown_name(self):
		return self.name

class Contacts:
	'''Information concerning all contacts and groupchat contacts'''
	def __init__(self):
		self._contacts = {} # list of contacts {acct: {jid1: [C1, C2]}, } one Contact per resource
		self._gc_contacts = {} # list of contacts that are in gc {acct: {room_jid: {nick: C}}}

		# For meta contacts:
		self._metacontacts_tags = {}

	def change_account_name(self, old_name, new_name):
		self._contacts[new_name] = self._contacts[old_name]
		self._gc_contacts[new_name] = self._gc_contacts[old_name]
		self._metacontacts_tags[new_name] = self._metacontacts_tags[old_name]
		del self._contacts[old_name]
		del self._gc_contacts[old_name]
		del self._metacontacts_tags[old_name]

	def add_account(self, account):
		self._contacts[account] = {}
		self._gc_contacts[account] = {}
		if not self._metacontacts_tags.has_key(account):
			self._metacontacts_tags[account] = {}

	def get_accounts(self):
		return self._contacts.keys()

	def remove_account(self, account):
		del self._contacts[account]
		del self._gc_contacts[account]
		del self._metacontacts_tags[account]

	def create_contact(self, jid='', name='', groups=[], show='', status='',
		sub='', ask='', resource='', priority=0, keyID='', our_chatstate=None,
		chatstate=None, last_status_time=None, composing_xep=None):
		return Contact(jid, name, groups, show, status, sub, ask, resource,
			priority, keyID, our_chatstate, chatstate, last_status_time,
			composing_xep)
	
	def copy_contact(self, contact):
		return self.create_contact(jid = contact.jid, name = contact.name,
			groups = contact.groups, show = contact.show, status =
			contact.status, sub = contact.sub, ask = contact.ask, resource = contact.resource,
			priority = contact.priority, keyID = contact.keyID,
			our_chatstate = contact.our_chatstate, chatstate = contact.chatstate,
			last_status_time = contact.last_status_time)

	def add_contact(self, account, contact):
		# No such account before ?
		if not self._contacts.has_key(account):
			self._contacts[account] = {contact.jid : [contact]}
			return
		# No such jid before ?
		if not self._contacts[account].has_key(contact.jid):
			self._contacts[account][contact.jid] = [contact]
			return
		contacts = self._contacts[account][contact.jid]
		# We had only one that was offline, remove it
		if len(contacts) == 1 and contacts[0].show == 'offline':
			# Do not use self.remove_contact: it deteles
			# self._contacts[account][contact.jid]
			contacts.remove(contacts[0])
		# If same JID with same resource already exists, use the new one
		for c in contacts:
			if c.resource == contact.resource:
				self.remove_contact(account, c)
				break
		contacts.append(contact)

	def remove_contact(self, account, contact):
		if not self._contacts.has_key(account):
			return
		if not self._contacts[account].has_key(contact.jid):
			return
		if contact in self._contacts[account][contact.jid]:
			self._contacts[account][contact.jid].remove(contact)
		if len(self._contacts[account][contact.jid]) == 0:
			del self._contacts[account][contact.jid]

	def clear_contacts(self, account):
		self._contacts[account] = {}

	def remove_jid(self, account, jid):
		'''Removes all contacts for a given jid'''
		if not self._contacts.has_key(account):
			return
		if not self._contacts[account].has_key(jid):
			return
		del self._contacts[account][jid]
		# remove metacontacts info
		self.remove_metacontact(account, jid)

	def get_contacts(self, account, jid):
		'''Returns the list of contact instances for this jid.'''
		if jid in self._contacts[account]:
			return self._contacts[account][jid]
		else:
			return []
	
	def get_contact(self, account, jid, resource = None):
		'''Returns the contact instance for the given resource if it's given else
		the first contact is no resource is given or None if there is not'''
		if jid in self._contacts[account]:
			if not resource:
				return self._contacts[account][jid][0]
			for c in self._contacts[account][jid]:
				if c.resource == resource:
					return c
		return None

	def get_contact_from_full_jid(self, account, fjid):
		''' Get Contact object for specific resource of given jid'''
		barejid, resource = common.gajim.get_room_and_nick_from_fjid(fjid)
		return self.get_contact(account, barejid, resource)

	def get_highest_prio_contact_from_contacts(self, contacts):
		if not contacts:
			return None
		prim_contact = contacts[0]
		for contact in contacts[1:]:
			if int(contact.priority) > int(prim_contact.priority):
				prim_contact = contact
		return prim_contact

	def get_contact_with_highest_priority(self, account, jid):
		contacts = self.get_contacts(account, jid)
		if not contacts and '/' in jid:
			# jid may be a fake jid, try it
			room, nick = jid.split('/', 1)
			contact = self.get_gc_contact(account, room, nick)
			return contact
		return self.get_highest_prio_contact_from_contacts(contacts)

	def get_first_contact_from_jid(self, account, jid):
		if jid in self._contacts[account]:
			return self._contacts[account][jid][0]
		return None

	def get_contacts_from_group(self, account, group):
		'''Returns all contacts in the given group'''
		group_contacts = []
		for jid in self._contacts[account]:
			contacts = self.get_contacts(account, jid)
			if group in contacts[0].groups:
				group_contacts += contacts
		return group_contacts

	def get_nb_online_total_contacts(self, accounts = [], groups = []):
		'''Returns the number of online contacts and the total number of
		contacts'''
		if accounts == []:
			accounts = self.get_accounts()
		nbr_online = 0
		nbr_total = 0
		for account in accounts:
			our_jid = common.gajim.get_jid_from_account(account)
			for jid in self.get_jid_list(account):
				if self.has_brother(account, jid) and not \
					self.is_big_brother(account, jid):
					# count metacontacts only once
					continue
				if jid == our_jid:
					continue
				if common.gajim.jid_is_transport(jid) and not \
					_('Transports') in groups:
					# do not count transports
					continue
				contact = self.get_contact_with_highest_priority(account, jid)
				if _('Not in roster') in contact.groups:
					continue
				in_groups = False
				if groups == []:
					in_groups = True
				else:
					contact_groups = contact.groups
					if not contact_groups:
						# Contact is not in a group, so count it in General or
						# Transports group
						if common.gajim.jid_is_transport(jid):
							contact_groups = [_('Transports')]
						if contact.is_observer():
							contact_groups = [_('Observers')]
						else:
							contact_groups = [_('General')]
					for group in groups:
						if group in contact_groups:
							in_groups = True
							break

				if in_groups:
					if contact.show not in ('offline', 'error'):
						nbr_online += 1
					nbr_total += 1
		return nbr_online, nbr_total

	def define_metacontacts(self, account, tags_list):
		self._metacontacts_tags[account] = tags_list

	def get_new_metacontacts_tag(self, jid):
		if not jid in self._metacontacts_tags.keys():
			return jid
		#FIXME: can this append ?
		assert False

	def get_metacontacts_tag(self, account, jid):
		'''Returns the tag of a jid'''
		if not self._metacontacts_tags.has_key(account):
			return None
		for tag in self._metacontacts_tags[account]:
			for data in self._metacontacts_tags[account][tag]:
				if data['jid'] == jid:
					return tag
		return None

	def add_metacontact(self, brother_account, brother_jid, account, jid):
		tag = self.get_metacontacts_tag(brother_account, brother_jid)
		if not tag:
			tag = self.get_new_metacontacts_tag(brother_jid)
			self._metacontacts_tags[brother_account][tag] = [{'jid': brother_jid,
				'tag': tag}]
			if brother_account != account:
				common.gajim.connections[brother_account].store_metacontacts(
					self._metacontacts_tags[brother_account])
		# be sure jid has no other tag
		old_tag = self.get_metacontacts_tag(account, jid)
		while old_tag:
			self.remove_metacontact(account, jid)
			old_tag = self.get_metacontacts_tag(account, jid)
		if not self._metacontacts_tags[account].has_key(tag):
			self._metacontacts_tags[account][tag] = [{'jid': jid, 'tag': tag}]
		else:
			self._metacontacts_tags[account][tag].append({'jid': jid,
				'tag': tag})
		common.gajim.connections[account].store_metacontacts(
			self._metacontacts_tags[account])

	def remove_metacontact(self, account, jid):
		found = None
		for tag in self._metacontacts_tags[account]:
			for data in self._metacontacts_tags[account][tag]:
				if data['jid'] == jid:
					found = data
					break
			if found:
				self._metacontacts_tags[account][tag].remove(found)
				break
		common.gajim.connections[account].store_metacontacts(
			self._metacontacts_tags[account])

	def has_brother(self, account, jid):
		for account in self._metacontacts_tags:
			tag = self.get_metacontacts_tag(account, jid)
			if tag and len(self._metacontacts_tags[account][tag]) > 1:
				return True
		return False

	def is_big_brother(self, account, jid):
		tag = self.get_metacontacts_tag(account, jid)
		if tag:
			family = self.get_metacontacts_family(account, jid)
			bb_data = self.get_metacontacts_big_brother(family)
			bb_jid = bb_data['jid']
			bb_account = bb_data['account']
			if bb_jid == jid and bb_account == account: 
				return True
		return False

	def get_metacontacts_jids(self, tag):
		'''Returns all jid for the given tag in the form {acct: [jid1, jid2],.}'''
		answers = {}
		for account in self._metacontacts_tags:
			if self._metacontacts_tags[account].has_key(tag):
				answers[account] = []
				for data in self._metacontacts_tags[account][tag]:
					answers[account].append(data['jid'])
		return answers

	def get_metacontacts_family(self, account, jid):
		'''return the family of the given jid, including jid in the form:
		[{'account': acct, 'jid': jid, 'order': order}, ]
		'order' is optional'''
		tag = self.get_metacontacts_tag(account, jid)
		if not tag:
			return []
		answers = []
		for account in self._metacontacts_tags:
			if self._metacontacts_tags[account].has_key(tag):
				for data in self._metacontacts_tags[account][tag]:
					data['account'] = account
					answers.append(data)
		return answers

	def compare_metacontacts(self, data1, data2):
		'''compare 2 metacontacts.
		Data is {'jid': jid, 'account': account, 'order': order}
		order is optional'''
		jid1 = data1['jid']
		jid2 = data2['jid']
		account1 = data1['account']
		account2 = data2['account']
		contact1 = self.get_contact_with_highest_priority(account1, jid1)
		contact2 = self.get_contact_with_highest_priority(account2, jid2)
		show_list = ['not in roster', 'error', 'offline', 'invisible', 'dnd',
			'xa', 'away', 'chat', 'online', 'requested', 'message']
		# contact can be null when we fill the roster on connection
		if not contact1:
			show1 = 0
			priority1 = 0
		else:
			show1 = show_list.index(contact1.show)
			priority1 = contact1.priority
		if not contact2:
			show2 = 0
			priority2 = 0
		else:
			show2 = show_list.index(contact2.show)
			priority2 = contact2.priority
		# If only one is offline, it's always second
		if show1 > 2 and show2 < 3:
			return 1
		if show2 > 2 and show1 < 3:
			return -1
		if 'order' in data1 and 'order' in data2:
			if data1['order'] > data2['order']:
				return 1
			if data1['order'] < data2['order']:
				return -1
		transport1 = common.gajim.get_transport_name_from_jid(jid1)
		transport2 = common.gajim.get_transport_name_from_jid(jid2)
		if transport2 and not transport1:
			return 1
		if transport1 and not transport2:
			return -1
		if priority1 > priority2:
			return 1
		if priority2 > priority1:
			return -1
		if show1 > show2:
			return 1
		if show2 > show1:
			return -1
		if jid1 > jid2:
			return 1
		if jid2 > jid1:
			return -1
		# If all is the same, compare accounts, they can't be the same
		if account1 > account2:
			return 1
		if account2 > account1:
			return -1
		return 0

	def get_metacontacts_big_brother(self, family):
		'''which of the family will be the big brother under wich all
		others will be ?'''
		family.sort(cmp=self.compare_metacontacts)
		return family[-1]

	def is_pm_from_jid(self, account, jid):
		'''Returns True if the given jid is a private message jid'''
		if jid in self._contacts[account]:
			return False
		return True

	def is_pm_from_contact(self, account, contact):
		'''Returns True if the given contact is a private message contact'''
		if isinstance(contact, Contact):
			return False
		return True

	def get_jid_list(self, account):
		return self._contacts[account].keys()

	def contact_from_gc_contact(self, gc_contact):
		'''Create a Contact instance from a GC_Contact instance'''
		jid = gc_contact.get_full_jid()
		return Contact(jid = jid, resource = '', name = gc_contact.name,
			groups = [], show = gc_contact.show, status = gc_contact.status,
			sub = 'none')

	def create_gc_contact(self, room_jid='', name='', show='', status='',
		role='', affiliation='', jid='', resource=''):
		return GC_Contact(room_jid, name, show, status, role, affiliation, jid,
			resource)
	
	def add_gc_contact(self, account, gc_contact):
		# No such account before ?
		if not self._gc_contacts.has_key(account):
			self._contacts[account] = {gc_contact.room_jid : {gc_contact.name: \
				gc_contact}}
			return
		# No such room_jid before ?
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			self._gc_contacts[account][gc_contact.room_jid] = {gc_contact.name: \
				gc_contact}
			return
		self._gc_contacts[account][gc_contact.room_jid][gc_contact.name] = \
				gc_contact

	def remove_gc_contact(self, account, gc_contact):
		if not self._gc_contacts.has_key(account):
			return
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			return
		if not self._gc_contacts[account][gc_contact.room_jid].has_key(
			gc_contact.name):
			return
		del self._gc_contacts[account][gc_contact.room_jid][gc_contact.name]
		# It was the last nick in room ?
		if not len(self._gc_contacts[account][gc_contact.room_jid]):
			del self._gc_contacts[account][gc_contact.room_jid]

	def remove_room(self, account, room_jid):
		if not self._gc_contacts.has_key(account):
			return
		if not self._gc_contacts[account].has_key(room_jid):
			return
		del self._gc_contacts[account][room_jid]

	def get_gc_list(self, account):
		if not self._gc_contacts.has_key(account):
			return []
		return self._gc_contacts[account].keys()

	def get_nick_list(self, account, room_jid):
		gc_list = self.get_gc_list(account)
		if not room_jid in gc_list:
			return []
		return self._gc_contacts[account][room_jid].keys()

	def get_gc_contact(self, account, room_jid, nick):
		nick_list = self.get_nick_list(account, room_jid)
		if not nick in nick_list:
			return None
		return self._gc_contacts[account][room_jid][nick]
