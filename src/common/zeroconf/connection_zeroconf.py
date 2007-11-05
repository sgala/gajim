##	common/zeroconf/connection_zeroconf.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
##  - Stefan Bethge <stefan@lanpartei.de>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##                    Stefan Bethge <stefan@lanpartei.de>
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
import random
random.seed()

import signal
if os.name != 'nt':
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import getpass
import gobject

from common import gajim
from common import GnuPG
from common.zeroconf import client_zeroconf
from connection_handlers_zeroconf import *

USE_GPG = GnuPG.USE_GPG

class ConnectionZeroconf(ConnectionHandlersZeroconf):
	'''Connection class'''
	def __init__(self, name):
		ConnectionHandlersZeroconf.__init__(self)
		# system username
		self.username = None
		self.name = name
		self.server_resource = '' # zeroconf has no resource, fake an empty one
		self.connected = 0 # offline
		self.connection = None
		self.gpg = None
		self.is_zeroconf = True
		self.privacy_rules_supported = False
		self.status = ''
		self.old_show = ''
		self.priority = 0
	
		self.call_resolve_timeout = False
		
		self.time_to_reconnect = None
		#self.new_account_info = None
		self.bookmarks = []

		#we don't need a password, but must be non-empty
		self.password = 'zeroconf'

		self.autoconnect = False
		self.sync_with_global_status = True
		self.no_log_for = False

		# Do we continue connection when we get roster (send presence,get vcard...)
		self.continue_connect_info = None
		if USE_GPG:
			self.gpg = GnuPG.GnuPG()
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)
		
		self.get_config_values_or_default()
		
		self.muc_jid = {} # jid of muc server for each transport type
		self.vcard_supported = False
		self.private_storage_supported = False

	def get_config_values_or_default(self):
		''' get name, host, port from config, or 
		create zeroconf account with default values'''
		
		if not gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name'):
			gajim.log.debug('Creating zeroconf account')
			gajim.config.add_per('accounts', gajim.ZEROCONF_ACC_NAME)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'autoconnect', True)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'no_log_for', '')
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'password', 'zeroconf')
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'sync_with_global_status', True)

			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'custom_port', 5298)
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'is_zeroconf', True)
		#XXX make sure host is US-ASCII
		self.host = unicode(socket.gethostname())
		gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'hostname', self.host)
		self.port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'custom_port')
		self.autoconnect = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'autoconnect')
		self.sync_with_global_status = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'sync_with_global_status')
		self.no_log_for = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'no_log_for')
		self.first = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_first_name')
		self.last = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_last_name')
		self.jabber_id = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_jabber_id')
		self.email = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_email')

		if not self.username:
			self.username = unicode(getpass.getuser())
			gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name', self.username)
		else:
			self.username = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name')
	# END __init__

	def dispatch(self, event, data):
		if gajim.handlers.has_key(event):
			gajim.handlers[event](self.name, data)

	def _reconnect(self):
		# Do not try to reco while we are already trying
		self.time_to_reconnect = None
		gajim.log.debug('reconnect')

#		signed = self.get_signed_msg(self.status)
		self.connect(self.old_show, self.status)

	def quit(self, kill_core):
		if kill_core and self.connected > 1:
			self.disconnect()
	
	def disable_account(self):
		self.disconnect()

	def test_gpg_passphrase(self, password):
		self.gpg.passphrase = password
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		signed = self.gpg.sign('test', keyID)
		self.gpg.password = None
		return signed != 'BAD_PASSPHRASE'

	def get_signed_msg(self, msg):
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if self.connected < 2 and self.gpg.passphrase is None and \
				not use_gpg_agent:
				# We didn't set a passphrase
				self.dispatch('ERROR', (_('OpenPGP passphrase was not given'),
					#%s is the account name here
					_('You will be connected to %s without OpenPGP.') % self.name))
			elif self.gpg.passphrase is not None or use_gpg_agent:
				signed = self.gpg.sign(msg, keyID)
				if signed == 'BAD_PASSPHRASE':
					signed = ''
					if self.connected < 2:
						self.dispatch('BAD_PASSPHRASE', ())
		return signed

	def _on_resolve_timeout(self):
		if self.connected:
			self.connection.resolve_all()
			diffs = self.roster.getDiffs()
			for key in diffs:
				self.roster.setItem(key)
				self.dispatch('ROSTER_INFO', (key, self.roster.getName(key),
							'both', 'no', self.roster.getGroups(key)))
				self.dispatch('NOTIFY', (key, self.roster.getStatus(key),
							self.roster.getMessage(key), 'local', 0, None, 0, None))
				#XXX open chat windows don't get refreshed (full name), add that
		return self.call_resolve_timeout

	# callbacks called from zeroconf	
	def _on_new_service(self,jid):
		self.roster.setItem(jid)
		self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both', 'no', self.roster.getGroups(jid)))
		self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0, None))
	
	def _on_remove_service(self, jid):
		self.roster.delItem(jid)
		# 'NOTIFY' (account, (jid, status, status message, resource, priority,
		# keyID, timestamp, contact_nickname))
		self.dispatch('NOTIFY', (jid, 'offline', '', 'local', 0, None, 0, None))

	def _on_disconnected(self):
		self.disconnect()
		self.dispatch('STATUS', 'offline')
		self.dispatch('CONNECTION_LOST',
			(_('Connection with account "%s" has been lost') % self.name,
			_('To continue sending and receiving messages, you will need to reconnect.')))
		self.status = 'offline'
		self.disconnect()

	def _disconnectedReconnCB(self):
		'''Called when we are disconnected. Comes from network manager for example
		we don't try to reconnect, network manager will tell us when we can'''
		if gajim.account_is_connected(self.name):
			# we cannot change our status to offline or connecting
			# after we auth to server
			self.old_show = STATUS_LIST[self.connected]
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		# random number to show we wait network manager to send us a reconenct
		self.time_to_reconnect = 5
		self.on_purpose = False

	def _on_name_conflictCB(self, alt_name):
		self.disconnect()
		self.dispatch('STATUS', 'offline')
		self.dispatch('ZC_NAME_CONFLICT', alt_name)

	def _on_error(self, message):
		self.dispatch('ERROR', (_('Avahi error'), _("%s\nLink-local messaging might not work properly.") % message))

	def connect(self, show = 'online', msg = ''):
		self.get_config_values_or_default()
		if not self.connection:
			self.connection = client_zeroconf.ClientZeroconf(self)
			if not self.connection.test_avahi():
				self.dispatch('STATUS', 'offline')
				self.status = 'offline'
				self.dispatch('CONNECTION_LOST',
					(_('Could not connect to "%s"') % self.name,
					_('Please check if Avahi is installed.')))
				self.disconnect()
				return
			result = self.connection.connect(show, msg)
			if not result:
				self.dispatch('STATUS', 'offline')
				self.status = 'offline'
				if result is False:
					self.dispatch('CONNECTION_LOST',
						(_('Could not start local service'),
						_('Unable to bind to port %d.' % self.port)))
				else: # result is None
					self.dispatch('CONNECTION_LOST',
					(_('Could not start local service'),
					_('Please check if avahi-daemon is running.')))
				self.disconnect()
				return
		else:
			self.connection.announce()
		self.roster = self.connection.getRoster()
		self.dispatch('ROSTER', self.roster)

		#display contacts already detected and resolved
		for jid in self.roster.keys():
			self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both', 'no', self.roster.getGroups(jid)))
			self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0, None))

		self.connected = STATUS_LIST.index(show)

		# refresh all contacts data every five seconds
		self.call_resolve_timeout = True
		gobject.timeout_add(5000, self._on_resolve_timeout)
		return True

	def disconnect(self, on_purpose = False):
		self.connected = 0
		self.time_to_reconnect = None
		if self.connection:
			self.connection.disconnect()
			self.connection = None
			# stop calling the timeout
			self.call_resolve_timeout = False

	def reannounce(self):
		if self.connected:
			txt = {}
			txt['1st'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_first_name')
			txt['last'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_last_name')
			txt['jid'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_jabber_id')
			txt['email'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'zeroconf_email')
			self.connection.reannounce(txt)

	def update_details(self):
		if self.connection:
			port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'custom_port')
			if port != self.port:
				self.port = port
				last_msg = self.connection.last_msg
				self.disconnect()
				if not self.connect(self.status, last_msg):
					return
				if self.status != 'invisible':
					self.connection.announce()
			else:
				self.reannounce()

	def change_status(self, show, msg, sync = False, auto = False):
		if not show in STATUS_LIST:
			return -1
		self.status = show

		check = True		#to check for errors from zeroconf
		# 'connect'
		if show != 'offline' and not self.connected:
			if not self.connect(show, msg):
				return
			if show != 'invisible':
				check = self.connection.announce()
			else:
				self.connected = STATUS_LIST.index(show)

		# 'disconnect'
		elif show == 'offline' and self.connected:
			self.disconnect()
			self.time_to_reconnect = None
			
		# update status
		elif show != 'offline' and self.connected:
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			if show == 'invisible':
				check = check and self.connection.remove_announce()
			elif was_invisible:
				if not self.connected:
					check = check and self.connect(show, msg)
				check = check and self.connection.announce()
			if self.connection and not show == 'invisible':
				check = check and self.connection.set_show_msg(show, msg)

		#stay offline when zeroconf does something wrong
		if check:
			self.dispatch('STATUS', show)
		else:
			# show notification that avahi or system bus is down	
			self.dispatch('STATUS', 'offline')
			self.status = 'offline'
			self.dispatch('CONNECTION_LOST',
				(_('Could not change status of account "%s"') % self.name,
				_('Please check if avahi-daemon is running.')))
			
	def get_status(self):
		return STATUS_LIST[self.connected]

	def send_message(self, jid, msg, keyID, type = 'chat', subject='',
	chatstate = None, msg_id = None, composing_xep = None, resource = None, 
	user_nick = None):
		fjid = jid

		if not self.connection:
			return
		if not msg and chatstate is None:
			return

		if self.status in ('invisible', 'offline'):
			self.dispatch('MSGERROR', [unicode(jid), '-1', _('You are not connected or not visible to others. Your message could not be sent.'), None, None])
			return

		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			# encrypt
			msgenc, error = self.gpg.encrypt(msg, [keyID])
			if msgenc and not error:
				msgtxt = '[This message is encrypted]'
				lang = os.getenv('LANG')
				if lang is not None or lang != 'en': # we're not english
					msgtxt = _('[This message is encrypted]') +\
						' ([This message is encrypted])' # one  in locale and one en
			else:
				# Encryption failed, do not send message
				tim = time.localtime()
				self.dispatch('MSGNOTSENT', (jid, error, msgtxt, tim))
				return 3

		if type == 'chat':
			msg_iq = common.xmpp.Message(to = fjid, body = msgtxt, typ = type)

		else:
			if subject:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal', subject = subject)
			else:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal')

		if msgenc:
			msg_iq.setTag(common.xmpp.NS_ENCRYPTED + ' x').setData(msgenc)

		# chatstates - if peer supports jep85 or jep22, send chatstates
		# please note that the only valid tag inside a message containing a <body>
		# tag is the active event
		if chatstate is not None:
			if composing_xep == 'XEP-0085' or not composing_xep:
				# JEP-0085
				msg_iq.setTag(chatstate, namespace = common.xmpp.NS_CHATSTATES)
			if composing_xep == 'XEP-0022' or not composing_xep:
				# JEP-0022
				chatstate_node = msg_iq.setTag('x', namespace = common.xmpp.NS_EVENT)
				if not msgtxt: # when no <body>, add <id>
					if not msg_id: # avoid putting 'None' in <id> tag
						msg_id = ''
					chatstate_node.setTagData('id', msg_id)
				# when msgtxt, requests JEP-0022 composing notification
				if chatstate is 'composing' or msgtxt: 
					chatstate_node.addChild(name = 'composing') 

		if not self.connection.send(msg_iq, msg != None):
			return

		no_log_for = gajim.config.get_per('accounts', self.name, 'no_log_for')
		ji = gajim.get_jid_without_resource(jid)
		if self.name not in no_log_for and ji not in no_log_for:
			log_msg = msg
			if subject:
				log_msg = _('Subject: %s\n%s') % (subject, msg)
			if log_msg:
				if type == 'chat':
					kind = 'chat_msg_sent'
				else:
					kind = 'single_msg_sent'
				gajim.logger.write(kind, jid, log_msg)
		
		self.dispatch('MSGSENT', (jid, msg, keyID))
		
	def send_stanza(self, stanza):
		# send a stanza untouched
		if not self.connection:
			return
		self.connection.send(stanza)
	
	def ack_subscribed(self, jid):
		gajim.log.debug('This should not happen (ack_subscribed)')

	def ack_unsubscribed(self, jid):
		gajim.log.debug('This should not happen (ack_unsubscribed)')

	def request_subscription(self, jid, msg = '', name = '', groups = [],
	auto_auth = False):
		gajim.log.debug('This should not happen (request_subscription)')

	def send_authorization(self, jid):
		gajim.log.debug('This should not happen (send_authorization)')

	def refuse_authorization(self, jid):
		gajim.log.debug('This should not happen (refuse_authorization)')

	def unsubscribe(self, jid, remove_auth = True):
		gajim.log.debug('This should not happen (unsubscribe)')

	def unsubscribe_agent(self, agent):
		gajim.log.debug('This should not happen (unsubscribe_agent)')

	def update_contact(self, jid, name, groups):	
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)
	
	def new_account(self, name, config, sync = False):
		gajim.log.debug('This should not happen (new_account)')

	def _on_new_account(self, con = None, con_type = None):
		gajim.log.debug('This should not happen (_on_new_account)')

	def account_changed(self, new_name):
		self.name = new_name

	def request_last_status_time(self, jid, resource):
		gajim.log.debug('This should not happen (request_last_status_time)')

	def request_os_info(self, jid, resource):
		gajim.log.debug('This should not happen (request_os_info)')

	def get_settings(self):
		gajim.log.debug('This should not happen (get_settings)')

	def get_bookmarks(self):
		gajim.log.debug('This should not happen (get_bookmarks)')
		
	def store_bookmarks(self):
		gajim.log.debug('This should not happen (store_bookmarks)')
		
	def get_metacontacts(self):
		gajim.log.debug('This should not happen (get_metacontacts)')
		
	def send_agent_status(self, agent, ptype):
		gajim.log.debug('This should not happen (send_agent_status)')

	def gpg_passphrase(self, passphrase):
		if USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if use_gpg_agent:
				self.gpg.passphrase = None
			else:
				self.gpg.passphrase = passphrase

	def ask_gpg_keys(self):
		if USE_GPG:
			keys = self.gpg.get_keys()
			return keys
		return None

	def ask_gpg_secrete_keys(self):
		if USE_GPG:
			keys = self.gpg.get_secret_keys()
			return keys
		return None

	def _event_dispatcher(self, realm, event, data):
		if realm == '':
			if event == common.xmpp.transports.DATA_RECEIVED:
				self.dispatch('STANZA_ARRIVED', unicode(data, errors = 'ignore'))
			elif event == common.xmpp.transports.DATA_SENT:
				self.dispatch('STANZA_SENT', unicode(data))

# END ConnectionZeroconf
