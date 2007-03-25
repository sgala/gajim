##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
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
import base64
import sha
import socket
import sys

from time import localtime, strftime, gmtime
from calendar import timegm

import socks5
import common.xmpp

from common import GnuPG
from common import helpers
from common import gajim
from common import atom
from common import pep
from common.commands import ConnectionCommands
from common.pubsub import ConnectionPubSub

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible', 'error']
# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
METACONTACTS_ARRIVED = 'metacontacts_arrived'
PRIVACY_ARRIVED = 'privacy_arrived'
HAS_IDLE = True
try:
	import idle
except:
	gajim.log.debug(_('Unable to load idle module'))
	HAS_IDLE = False

class ConnectionBytestream:
	def __init__(self):
		self.files_props = {}
	
	def is_transfer_stoped(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return True
		if file_props.has_key('completed') and file_props['completed']:
			return True
		if file_props.has_key('connected') and file_props['connected'] == False:
			return True
		if not file_props.has_key('stopped') or not file_props['stopped']:
			return False
		return True
	
	def send_success_connect_reply(self, streamhost):
		''' send reply to the initiator of FT that we
		made a connection
		'''
		if streamhost is None:
			return None
		iq = common.xmpp.Iq(to = streamhost['initiator'], typ = 'result',
			frm = streamhost['target'])
		iq.setAttr('id', streamhost['id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		stream_tag = query.setTag('streamhost-used')
		stream_tag.setAttr('jid', streamhost['jid'])
		self.connection.send(iq)
	
	def remove_transfers_for_contact(self, contact):
		''' stop all active transfer for contact '''
		for file_props in self.files_props.values():
			if self.is_transfer_stoped(file_props):
				continue
			receiver_jid = unicode(file_props['receiver']).split('/')[0]
			if contact.jid == receiver_jid:
				file_props['error'] = -5
				self.remove_transfer(file_props)
				self.dispatch('FILE_REQUEST_ERROR', (contact.jid, file_props, ''))
			sender_jid = unicode(file_props['sender']).split('/')[0]
			if contact.jid == sender_jid:
				file_props['error'] = -3
				self.remove_transfer(file_props)
	
	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list = False)
		del(self.files_props)
		self.files_props = {}
	
	def remove_transfer(self, file_props, remove_from_list = True):
		if file_props is None:
			return
		self.disconnect_transfer(file_props)
		sid = file_props['sid']
		gajim.socks5queue.remove_file_props(self.name, sid)

		if remove_from_list:
			if self.files_props.has_key('sid'):
				del(self.files_props['sid'])
	
	def disconnect_transfer(self, file_props):
		if file_props is None:
			return
		if file_props.has_key('hash'):
			gajim.socks5queue.remove_sender(file_props['hash'])

		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host.has_key('idx') and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])
	
	def send_socks5_info(self, file_props, fast = True, receiver = None,
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if type(self.peerhost) != tuple:
			return
		port = gajim.config.get('file_transfers_port')
		ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
		cfg_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		proxyhosts = []
		if fast and cfg_proxies:
			proxies = map(lambda e:e.strip(), cfg_proxies.split(','))
			default = gajim.proxy65_manager.get_default_for_name(self.name)
			if default:
				# add/move default proxy at top of the others
				if proxies.__contains__(default):
					proxies.remove(default)
				proxies.insert(0, default)
			
			for proxy in proxies:
				(host, _port, jid) = gajim.proxy65_manager.get_proxy(proxy, self.name)
				if host is None:
					continue
				host_dict={
					'state': 0,
					'target': unicode(receiver),
					'id': file_props['sid'],
					'sid': file_props['sid'],
					'initiator': proxy,
					'host': host,
					'port': unicode(_port),
					'jid': jid
				}
				proxyhosts.append(host_dict)
		sha_str = helpers.get_auth_sha(file_props['sid'], sender,
			receiver)
		file_props['sha_str'] = sha_str
		ft_add_hosts = []
		if ft_add_hosts_to_send:
			ft_add_hosts_to_send = map(lambda e:e.strip(),
				ft_add_hosts_to_send.split(','))
			for ft_host in ft_add_hosts_to_send:
				try:
					ft_host = socket.gethostbyname(ft_host)
					ft_add_hosts.append(ft_host)
				except socket.gaierror:
					self.dispatch('ERROR', (_('Wrong host'), _('The host %s you configured as the ft_add_hosts_to_send advanced option is not valid, so ignored.') % ft_host))
		listener = gajim.socks5queue.start_listener(port,
			sha_str, self._result_socks5_sid, file_props['sid'])
		if listener == None:
			file_props['error'] = -5
			self.dispatch('FILE_REQUEST_ERROR', (unicode(receiver), file_props,
				''))
			self._connect_error(unicode(receiver), file_props['sid'],
				file_props['sid'], code = 406)
			return

		iq = common.xmpp.Protocol(name = 'iq', to = unicode(receiver),
			typ = 'set')
		file_props['request-id'] = 'id_' + file_props['sid']
		iq.setID(file_props['request-id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('mode', 'tcp')
		query.setAttr('sid', file_props['sid'])
		for ft_host in ft_add_hosts:
			# The streamhost, if set
			ostreamhost = common.xmpp.Node(tag = 'streamhost')
			query.addChild(node = ostreamhost)
			ostreamhost.setAttr('port', unicode(port))
			ostreamhost.setAttr('host', ft_host)
			ostreamhost.setAttr('jid', sender)
		for thehost in self.peerhost:
			try:
				thehost = self.peerhost[0]
				streamhost = common.xmpp.Node(tag = 'streamhost') # My IP
				query.addChild(node = streamhost)
				streamhost.setAttr('port', unicode(port))
				streamhost.setAttr('host', thehost)
				streamhost.setAttr('jid', sender)
			except socket.gaierror:
				self.dispatch('ERROR', (_('Wrong host'),
					_('Invalid local address? :-O')))

		if fast and proxyhosts != [] and gajim.config.get_per('accounts',
		self.name, 'use_ft_proxies'):
			file_props['proxy_receiver'] = unicode(receiver)
			file_props['proxy_sender'] = unicode(sender)
			file_props['proxyhosts'] = proxyhosts
			for proxyhost in proxyhosts:
				streamhost = common.xmpp.Node(tag = 'streamhost')
				query.addChild(node=streamhost)
				streamhost.setAttr('port', proxyhost['port'])
				streamhost.setAttr('host', proxyhost['host'])
				streamhost.setAttr('jid', proxyhost['jid'])

				# don't add the proxy child tag for streamhosts, which are proxies
				# proxy = streamhost.setTag('proxy')
				# proxy.setNamespace(common.xmpp.NS_STREAM)
		self.connection.send(iq)

	def send_file_rejection(self, file_props):
		''' informs sender that we refuse to download the file '''
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		err = common.xmpp.ErrorNode(code = '403', typ = 'cancel', name =
			'forbidden', text = 'Offer Declined')
		iq.addChild(node=err)
		self.connection.send(iq)

	def send_file_approval(self, file_props):
		''' send iq, confirming that we want to download the file '''
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'result')
		iq.setAttr('id', file_props['request-id'])
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		if file_props.has_key('offset') and file_props['offset']:
			file_tag = si.setTag('file')
			file_tag.setNamespace(common.xmpp.NS_FILE)
			range_tag = file_tag.setTag('range')
			range_tag.setAttr('offset', file_props['offset'])
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='submit')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.delAttr('type')
		field.setValue(common.xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def send_file_request(self, file_props):
		''' send iq for new FT request '''
		if not self.connection or self.connected < 2:
			return
		our_jid = gajim.get_jid_from_account(self.name)
		resource = self.server_resource
		frm = our_jid + '/' + resource
		file_props['sender'] = frm
		fjid = file_props['receiver'].jid + '/' + file_props['receiver'].resource
		iq = common.xmpp.Protocol(name = 'iq', to = fjid,
			typ = 'set')
		iq.setID(file_props['sid'])
		self.files_props[file_props['sid']] = file_props
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		si.setAttr('profile', common.xmpp.NS_FILE)
		si.setAttr('id', file_props['sid'])
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		file_tag.setAttr('name', file_props['name'])
		file_tag.setAttr('size', file_props['size'])
		desc = file_tag.setTag('desc')
		if file_props.has_key('desc'):
			desc.setData(file_props['desc'])
		file_tag.setTag('range')
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='form')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.setAttr('type', 'list-single')
		field.addOption(common.xmpp.NS_BYTESTREAM)
		self.connection.send(iq)
	
	def _result_socks5_sid(self, sid, hash_id):
		''' store the result of sha message from auth. '''
		if not self.files_props.has_key(sid):
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return
	
	def _connect_error(self, to, _id, sid, code = 404):
		''' cb, when there is an error establishing BS connection, or 
		when connection is rejected'''
		msg_dict = {
			404: 'Could not connect to given hosts',
			405: 'Cancel',
			406: 'Not acceptable',
		}
		msg = msg_dict[code]
		iq = None
		iq = common.xmpp.Protocol(name = 'iq', to = to,
			typ = 'error')
		iq.setAttr('id', _id)
		err = iq.setTag('error')
		err.setAttr('code', unicode(code))
		err.setData(msg)
		self.connection.send(iq)
		if code == 404:
			file_props = gajim.socks5queue.get_file_props(self.name, sid)
			if file_props is not None:
				self.disconnect_transfer(file_props)
				file_props['error'] = -3
				self.dispatch('FILE_REQUEST_ERROR', (to, file_props, msg))

	def _proxy_auth_ok(self, proxy):
		'''cb, called after authentication to proxy server '''
		file_props = self.files_props[proxy['sid']]
		iq = common.xmpp.Protocol(name = 'iq', to = proxy['initiator'],
		typ = 'set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid',  proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.connection.send(iq)
	
	# register xmpppy handlers for bytestream and FT stanzas
	def _bytestreamErrorCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamErrorCB')
		id = unicode(iq_obj.getAttr('id'))
		frm = helpers.get_full_jid_from_iq(iq_obj)
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.error_cb(frm, query)
		jid = helpers.get_jid_from_iq(iq_obj)
		id = id[3:]
		if not self.files_props.has_key(id):
			return
		file_props = self.files_props[id]
		file_props['error'] = -4
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed
	
	def _bytestreamSetCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamSetCB')
		target = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = unicode(query.getAttr('sid'))
		file_props = gajim.socks5queue.get_file_props(
			self.name, sid)
		streamhosts=[]
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict={
					'state': 0,
					'target': target,
					'id': id,
					'sid': sid,
					'initiator': helpers.get_full_jid_from_iq(iq_obj)
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if self.files_props.has_key(sid):
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's': # FIXME: remove fast xmlns
					# only psi do this

					if file_props.has_key('streamhosts'):
						file_props['streamhosts'].extend(streamhosts)
					else:
						file_props['streamhosts'] = streamhosts
					if not gajim.socks5queue.get_file_props(self.name, sid):
						gajim.socks5queue.add_file_props(self.name, file_props)
					gajim.socks5queue.connect_to_hosts(self.name, sid,
						self.send_success_connect_reply, None)
				raise common.xmpp.NodeProcessed

		file_props['streamhosts'] = streamhosts
		if file_props['type'] == 'r':
			gajim.socks5queue.connect_to_hosts(self.name, sid,
				self.send_success_connect_reply, self._connect_error)
		raise common.xmpp.NodeProcessed

	def _ResultCB(self, con, iq_obj):
		gajim.log.debug('_ResultCB')
		# if we want to respect jep-0065 we have to check for proxy
		# activation result in any result iq
		real_id = unicode(iq_obj.getAttr('id'))
		if real_id[:3] != 'au_':
			return
		frm = helpers.get_full_jid_from_iq(iq_obj)
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
			if file_props['streamhost-used']:
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and host.has_key('idx'):
						gajim.socks5queue.activate_proxy(host['idx'])
						raise common.xmpp.NodeProcessed
	
	def _bytestreamResultCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamResultCB')
		frm = helpers.get_full_jid_from_iq(iq_obj)
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.resolve_result(frm, query)
		
		try:
			streamhost =  query.getTag('streamhost-used')
		except: # this bytestream result is not what we need
			pass
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
		else:
			raise common.xmpp.NodeProcessed
		if streamhost is None:
			# proxy approves the activate query
			if real_id[:3] == 'au_':
				id = real_id[3:]
				if not file_props.has_key('streamhost-used') or \
					file_props['streamhost-used'] is False:
					raise common.xmpp.NodeProcessed
				if not file_props.has_key('proxyhosts'):
					raise common.xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise common.xmpp.NodeProcessed
		jid = streamhost.getAttr('jid')
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed

		if real_id[:3] == 'au_':
			gajim.socks5queue.send_file(file_props, self.name)
			raise common.xmpp.NodeProcessed

		proxy = None
		if file_props.has_key('proxyhosts'):
			for proxyhost in file_props['proxyhosts']:
				if proxyhost['jid'] == jid:
					proxy = proxyhost

		if proxy != None:
			file_props['streamhost-used'] = True
			if not file_props.has_key('streamhosts'):
				file_props['streamhosts'] = []
			file_props['streamhosts'].append(proxy)
			file_props['is_a_proxy'] = True
			receiver = socks5.Socks5Receiver(gajim.idlequeue, proxy, file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self._proxy_auth_ok
			raise common.xmpp.NodeProcessed

		else:
			gajim.socks5queue.send_file(file_props, self.name)
			if file_props.has_key('fast'):
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(frm, fasts[0]['id'], file_props['sid'],
						code = 406)
		
		raise common.xmpp.NodeProcessed
	
	def _siResultCB(self, con, iq_obj):
		gajim.log.debug('_siResultCB')
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		if file_props.has_key('request-id'):
			# we have already sent streamhosts info
			return
		file_props['receiver'] = helpers.get_full_jid_from_iq(iq_obj)
		si = iq_obj.getTag('si')
		file_tag = si.getTag('file')
		range_tag = None
		if file_tag:
			range_tag = file_tag.getTag('range')
		if range_tag:
			offset = range_tag.getAttr('offset')
			if offset:
				file_props['offset'] = int(offset)
			length = range_tag.getAttr('length')
			if length:
				file_props['length'] = int(length)
		feature = si.setTag('feature')
		if feature.getNamespace() != common.xmpp.NS_FEATURE:
			return
		form_tag = feature.getTag('x')
		form = common.xmpp.DataForm(node=form_tag)
		field = form.getField('stream-method')
		if field.getValue() != common.xmpp.NS_BYTESTREAM:
			return
		self.send_socks5_info(file_props, fast = True)
		raise common.xmpp.NodeProcessed
	
	def _siSetCB(self, con, iq_obj):
		gajim.log.debug('_siSetCB')
		jid = helpers.get_jid_from_iq(iq_obj)
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != common.xmpp.NS_FILE:
			return
		file_tag = si.getTag('file')
		file_props = {'type': 'r'}
		for attribute in file_tag.getAttrs():
			if attribute in ('name', 'size', 'hash', 'date'):
				val = file_tag.getAttr(attribute)
				if val is None:
					continue
				file_props[attribute] = val
		file_desc_tag = file_tag.getTag('desc')
		if file_desc_tag is not None:
			file_props['desc'] = file_desc_tag.getData()

		if mime_type is not None:
			file_props['mime-type'] = mime_type
		our_jid = gajim.get_jid_from_account(self.name)
		resource = self.server_resource
		file_props['receiver'] = our_jid + '/' + resource
		file_props['sender'] = helpers.get_full_jid_from_iq(iq_obj)
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		file_props['sid'] = unicode(si.getAttr('id'))
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def _siErrorCB(self, con, iq_obj):
		gajim.log.debug('_siErrorCB')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != common.xmpp.NS_FILE:
			return
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		jid = helpers.get_jid_from_iq(iq_obj)
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed

class ConnectionDisco:
	''' hold xmpppy handlers and public methods for discover services'''
	def discoverItems(self, jid, node = None, id_prefix = None):
		'''According to JEP-0030: jid is mandatory,
		name, node, action is optional.'''
		self._discover(common.xmpp.NS_DISCO_ITEMS, jid, node, id_prefix)

	def discoverInfo(self, jid, node = None, id_prefix = None):
		'''According to JEP-0030:
			For identity: category, type is mandatory, name is optional.
			For feature: var is mandatory'''
		self._discover(common.xmpp.NS_DISCO_INFO, jid, node, id_prefix)
	
	def request_register_agent_info(self, agent):
		if not self.connection:
			return None
		iq=common.xmpp.Iq('get', common.xmpp.NS_REGISTER, to=agent)
		id = self.connection.getAnID()
		iq.setID(id)
		# Wait the answer during 30 secondes
		self.awaiting_timeouts[gajim.idlequeue.current_time() + 30] = (id,
			_('Registration information for transport %s has not arrived in time') % \
			agent)
		self.connection.SendAndCallForResponse(iq, self._ReceivedRegInfo,
			{'agent': agent})

	def register_agent(self, agent, info, is_form = False):
		if not self.connection:
			return
		if is_form:
			iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
			query = iq.getTag('query')
			info.setAttr('type', 'submit')
			query.addChild(node = info)
			self.connection.send(iq)
		else:
			# fixed: blocking
			common.xmpp.features_nb.register(self.connection, agent, info, None)
	
	
	def _discover(self, ns, jid, node = None, id_prefix = None):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = jid, queryNS = ns)
		if id_prefix:
			id = self.connection.getAnID()
			iq.setID('%s%s' % (id_prefix, id))
		if node:
			iq.setQuerynode(node)
		self.connection.send(iq)
	
	def _ReceivedRegInfo(self, con, resp, agent):
		common.xmpp.features_nb._ReceivedRegInfo(con, resp, agent)
		self._IqCB(con, resp)
	
	def _discoGetCB(self, con, iq_obj):
		''' get disco info '''
		frm = helpers.get_full_jid_from_iq(iq_obj)
		to = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		iq = common.xmpp.Iq(to = frm, typ = 'result', queryNS =\
			common.xmpp.NS_DISCO, frm = to)
		iq.setAttr('id', id)
		query = iq.setTag('query')
		query.setAttr('node','http://gajim.org/caps#' + gajim.version)
		for f in (common.xmpp.NS_BYTESTREAM, common.xmpp.NS_SI, \
						common.xmpp.NS_FILE, common.xmpp.NS_COMMANDS):
			feature = common.xmpp.Node('feature')
			feature.setAttr('var', f)
			query.addChild(node=feature)
		
		self.connection.send(iq)
		raise common.xmpp.NodeProcessed
	
	def _DiscoverItemsErrorCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		self.dispatch('AGENT_ERROR_ITEMS', (jid))

	def _DiscoverItemsCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsCB')
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qp = iq_obj.getQueryPayload()
		items = []
		if not qp:
			qp = []
		for i in qp:
			# CDATA payload is not processed, only nodes
			if not isinstance(i, common.xmpp.simplexml.Node):
				continue
			attr = {}
			for key in i.getAttrs():
				attr[key] = i.getAttrs()[key]
			if 'jid' not in attr:
				continue
			try:
				helpers.parse_jid(attr['jid'])
			except common.helpers.InvalidFormat:
				# jid is not conform
				continue
			items.append(attr)
		jid = helpers.get_full_jid_from_iq(iq_obj)
		hostname = gajim.config.get_per('accounts', self.name, 
													'hostname')
		id = iq_obj.getID()
		if jid == hostname and id[0] == 'p':
			for item in items:
				self.discoverInfo(item['jid'], id_prefix='p')
		else:
			self.dispatch('AGENT_INFO_ITEMS', (jid, node, items))

	def _DiscoverItemsGetCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsGetCB')
		node = iq_obj.getTagAttr('query', 'node')
		if node==common.xmpp.NS_COMMANDS:
			self.commandListQuery(con, iq_obj)
			raise common.xmpp.NodeProcessed

	def _DiscoverInfoGetCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoGetCB')
		q = iq_obj.getTag('query')
		node = q.getAttr('node')

		if self.commandQuery(con, iq_obj):
			raise common.xmpp.NodeProcessed
		
		else:
			iq = iq_obj.buildReply('result')
			q = iq.getTag('query')
			if node:
				q.setAttr('node', node)
			q.addChild('identity', attrs = {'type': 'pc', 'category': 'client',
				'name': 'Gajim'})
			extension = None
			if node and node.find('#') != -1:
				extension = node[node.index('#') + 1:]
			client_version = 'http://gajim.org/caps#' + gajim.version

			if node in (None, client_version):
				q.addChild('feature', attrs = {'var': common.xmpp.NS_BYTESTREAM})
				q.addChild('feature', attrs = {'var': common.xmpp.NS_SI})
				q.addChild('feature', attrs = {'var': common.xmpp.NS_FILE})
				q.addChild('feature', attrs = {'var': common.xmpp.NS_MUC})
				q.addChild('feature', attrs = {'var': common.xmpp.NS_COMMANDS})
				q.addChild('feature', attrs = {'var': common.xmpp.NS_DISCO_INFO})

			if (node is None or extension == 'cstates') and gajim.config.get('outgoing_chat_state_notifactions') != 'disabled':
				q.addChild('feature', attrs = {'var': common.xmpp.NS_CHATSTATES})

			if (node is None or extension == 'xhtml') and not gajim.config.get('ignore_incoming_xhtml'):
				q.addChild('feature', attrs = {'var': common.xmpp.NS_XHTML_IM})

			if q.getChildren():
				self.connection.send(iq)
				raise common.xmpp.NodeProcessed

	def _DiscoverInfoErrorCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		self.dispatch('AGENT_ERROR_INFO', (jid))

	def _DiscoverInfoCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoCB')
		# According to JEP-0030:
		# For identity: category, type is mandatory, name is optional.
		# For feature: var is mandatory
		identities, features, data = [], [], []
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qc = iq_obj.getQueryChildren()
		if not qc:
			qc = []
		is_muc = False
		transport_type = ''
		for i in qc:
			if i.getName() == 'identity':
				attr = {}
				for key in i.getAttrs().keys():
					attr[key] = i.getAttr(key)
				if attr.has_key('category') and attr['category'] in ('gateway', 'headline')\
				and attr.has_key('type'):
					transport_type = attr['type']
				if attr.has_key('category') and attr['category'] == 'conference' \
				and attr.has_key('type') and attr['type'] == 'text':
					is_muc = True
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
			elif i.getName() == 'x' and i.getNamespace() == common.xmpp.NS_DATA:
				data.append(common.xmpp.DataForm(node=i))
		jid = helpers.get_full_jid_from_iq(iq_obj)
		if transport_type and jid not in gajim.transport_type:
			gajim.transport_type[jid] = transport_type
			gajim.logger.save_transport_type(jid, transport_type)
		id = iq_obj.getID()
		if not identities: # ejabberd doesn't send identities when we browse online users
		#FIXME: see http://www.jabber.ru/bugzilla/show_bug.cgi?id=225
			identities = [{'category': 'server', 'type': 'im', 'name': node}]
		if id[0] == 'p':
			if features.__contains__(common.xmpp.NS_BYTESTREAM):
				gajim.proxy65_manager.resolve(jid, self.connection, self.name)
			if features.__contains__(common.xmpp.NS_MUC) and is_muc:
				type_ = transport_type or 'jabber'
				self.muc_jid[type_] = jid
			if transport_type:
				if self.available_transports.has_key(transport_type):
					self.available_transports[transport_type].append(jid)
				else:
					self.available_transports[transport_type] = [jid]
		self.dispatch('AGENT_INFO_INFO', (jid, node, identities,
			features, data))

class ConnectionVcard:
	def __init__(self):
		self.vcard_sha = None
		self.vcard_shas = {} # sha of contacts
		self.room_jids = [] # list of gc jids so that vcard are saved in a folder
		
	def add_sha(self, p, send_caps = True):
		c = p.setTag('x', namespace = common.xmpp.NS_VCARD_UPDATE)
		if self.vcard_sha is not None:
			c.setTagData('photo', self.vcard_sha)
		if send_caps:
			return self.add_caps(p)
		return p
	
	def add_caps(self, p):
		''' advertise our capabilities in presence stanza (jep-0115)'''
		c = p.setTag('c', namespace = common.xmpp.NS_CAPS)
		c.setAttr('node', 'http://gajim.org/caps')
		ext = []
		if not gajim.config.get('ignore_incoming_xhtml'):
			ext.append('xhtml')
		if gajim.config.get('outgoing_chat_state_notifactions') != 'disabled':
			ext.append('cstates')
 
		if len(ext):
			c.setAttr('ext', ' '.join(ext))
		c.setAttr('ver', gajim.version)
		return p
	
	def node_to_dict(self, node):
		dict = {}
		for info in node.getChildren():
			name = info.getName()
			if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
				if not dict.has_key(name):
					dict[name] = []
				entry = {}
				for c in info.getChildren():
					entry[c.getName()] = c.getData()
				dict[name].append(entry)
			elif info.getChildren() == []:
				dict[name] = info.getData()
			else:
				dict[name] = {}
				for c in info.getChildren():
					dict[name][c.getName()] = c.getData()
		return dict

	def save_vcard_to_hd(self, full_jid, card):
		jid, nick = gajim.get_room_and_nick_from_fjid(full_jid)
		puny_jid = helpers.sanitize_filename(jid)
		path = os.path.join(gajim.VCARD_PATH, puny_jid)
		if jid in self.room_jids or os.path.isdir(path):
			if not nick:
				return
			# remove room_jid file if needed
			if os.path.isfile(path):
				os.remove(path)
			# create folder if needed
			if not os.path.isdir(path):
				os.mkdir(path, 0700)
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = path
		fil = open(path_to_file, 'w')
		fil.write(str(card))
		fil.close()
	
	def get_cached_vcard(self, fjid, is_fake_jid = False):
		'''return the vcard as a dict
		return {} if vcard was too old
		return None if we don't have cached vcard'''
		jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
		puny_jid = helpers.sanitize_filename(jid)
		if is_fake_jid:
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid)
		if not os.path.isfile(path_to_file):
			return None
		# We have the vcard cached
		f = open(path_to_file)
		c = f.read()
		f.close()
		try:
			card = common.xmpp.Node(node = c)
		except:
			# We are unable to parse it. Remove it
			os.remove(path_to_file)
			return None
		vcard = self.node_to_dict(card)
		if vcard.has_key('PHOTO'):
			if not isinstance(vcard['PHOTO'], dict):
				del vcard['PHOTO']
		vcard['jid'] = jid
		vcard['resource'] = gajim.get_resource_from_jid(fjid)
		return vcard

	def request_vcard(self, jid = None, is_fake_jid = False):
		'''request the VCARD. If is_fake_jid is True, it means we request a vcard
		to a fake jid, like in private messages in groupchat'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get')
		if jid:
			iq.setTo(jid)
		iq.setTag(common.xmpp.NS_VCARD + ' vCard')

		id = self.connection.getAnID()
		iq.setID(id)
		j = jid
		if not j:
			j = gajim.get_jid_from_account(self.name)
		self.awaiting_answers[id] = (VCARD_ARRIVED, j)
		if is_fake_jid:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			if not room_jid in self.room_jids:
				self.room_jids.append(room_jid)
		self.connection.send(iq)
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})

	def send_vcard(self, vcard):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set')
		iq2 = iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		for i in vcard:
			if i == 'jid':
				continue
			if isinstance(vcard[i], dict):
				iq3 = iq2.addChild(i)
				for j in vcard[i]:
					iq3.addChild(j).setData(vcard[i][j])
			elif type(vcard[i]) == type([]):
				for j in vcard[i]:
					iq3 = iq2.addChild(i)
					for k in j:
						iq3.addChild(k).setData(j[k])
			else:
				iq2.addChild(i).setData(vcard[i])

		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

		our_jid = gajim.get_jid_from_account(self.name)
		# Add the sha of the avatar
		if vcard.has_key('PHOTO') and isinstance(vcard['PHOTO'], dict) and \
		vcard['PHOTO'].has_key('BINVAL'):
			photo = vcard['PHOTO']['BINVAL']
			photo_decoded = base64.decodestring(photo)
			gajim.interface.save_avatar_files(our_jid, photo_decoded)
			avatar_sha = sha.sha(photo_decoded).hexdigest()
			iq2.getTag('PHOTO').setTagData('SHA', avatar_sha)
		else:
			gajim.interface.remove_avatar_files(our_jid)

		self.awaiting_answers[id] = (VCARD_PUBLISHED, iq2)
	
	def _IqCB(self, con, iq_obj):
		id = iq_obj.getID()

		# Check if we were waiting a timeout for this id
		found_tim = None
		for tim in self.awaiting_timeouts:
			if id == self.awaiting_timeouts[tim][0]:
				found_tim = tim
				break
		if found_tim:
			del self.awaiting_timeouts[found_tim]

		if id not in self.awaiting_answers:
			return
		if self.awaiting_answers[id][0] == VCARD_PUBLISHED:
			if iq_obj.getType() == 'result':
				vcard_iq = self.awaiting_answers[id][1]
				# Save vcard to HD
				if vcard_iq.getTag('PHOTO') and vcard_iq.getTag('PHOTO').getTag('SHA'):
					new_sha = vcard_iq.getTag('PHOTO').getTagData('SHA')
				else:
					new_sha = ''

				# Save it to file
				our_jid = gajim.get_jid_from_account(self.name)
				self.save_vcard_to_hd(our_jid, vcard_iq)

				# Send new presence if sha changed and we are not invisible
				if self.vcard_sha != new_sha and STATUS_LIST[self.connected] != \
					'invisible':
					self.vcard_sha = new_sha
					sshow = helpers.get_xmpp_show(STATUS_LIST[self.connected])
					p = common.xmpp.Presence(typ = None, priority = self.priority,
						show = sshow, status = self.status)
					p = self.add_sha(p)
					self.connection.send(p)
				self.dispatch('VCARD_PUBLISHED', ())
			elif iq_obj.getType() == 'error':
				self.dispatch('VCARD_NOT_PUBLISHED', ())
		elif self.awaiting_answers[id][0] == VCARD_ARRIVED:
			# If vcard is empty, we send to the interface an empty vcard so that
			# it knows it arrived
			jid = self.awaiting_answers[id][1]
			our_jid = gajim.get_jid_from_account(self.name)
			if iq_obj.getType() == 'error' and jid == our_jid:
				# our server doesn't support vcard
				self.vcard_supported = False
			if not iq_obj.getTag('vCard') or iq_obj.getType() == 'error':
				if jid and jid != our_jid:
					# Write an empty file
					self.save_vcard_to_hd(jid, '')
					self.dispatch('VCARD', {'jid': jid})
				elif jid == our_jid:
					self.dispatch('MYVCARD', {'jid': jid})
		elif self.awaiting_answers[id][0] == AGENT_REMOVED:
			jid = self.awaiting_answers[id][1]
			self.dispatch('AGENT_REMOVED', jid)
		elif self.awaiting_answers[id][0] == METACONTACTS_ARRIVED:
			if iq_obj.getType() == 'result':
				# Metacontact tags
				# http://www.jabber.org/jeps/jep-XXXX.html
				meta_list = {}
				query = iq_obj.getTag('query')
				storage = query.getTag('storage')
				metas = storage.getTags('meta')
				for meta in metas:
					jid = meta.getAttr('jid')
					tag = meta.getAttr('tag')
					data = {'jid': jid}
					order = meta.getAttr('order')
					if order != None:
						data['order'] = order
					if meta_list.has_key(tag):
						meta_list[tag].append(data)
					else:
						meta_list[tag] = [data]
				self.dispatch('METACONTACTS', meta_list)
			else:
				self.metacontacts_supported = False
			# We can now continue connection by requesting the roster
			self.connection.initRoster()
		elif self.awaiting_answers[id][0] == PRIVACY_ARRIVED:
			if iq_obj.getType() != 'error':
				self.privacy_rules_supported = True
			# Ask metacontacts before roster
			self.get_metacontacts()

		del self.awaiting_answers[id]

	def _vCardCB(self, con, vc):
		'''Called when we receive a vCard
		Parse the vCard and send it to plugins'''
		if not vc.getTag('vCard'):
			return
		if not vc.getTag('vCard').getNamespace() == common.xmpp.NS_VCARD:
			return
		frm_iq = vc.getFrom()
		our_jid = gajim.get_jid_from_account(self.name)
		resource = ''
		if frm_iq:
			who = helpers.get_full_jid_from_iq(vc)
			frm, resource = gajim.get_room_and_nick_from_fjid(who)
		else:
			who = frm = our_jid
		card = vc.getChildren()[0]
		vcard = self.node_to_dict(card)
		photo_decoded = None
		if vcard.has_key('PHOTO') and isinstance(vcard['PHOTO'], dict) and \
		vcard['PHOTO'].has_key('BINVAL'):
			photo = vcard['PHOTO']['BINVAL']
			try:
				photo_decoded = base64.decodestring(photo)
				avatar_sha = sha.sha(photo_decoded).hexdigest()
			except:
				avatar_sha = ''
		else:
			avatar_sha = ''

		if avatar_sha:
			card.getTag('PHOTO').setTagData('SHA', avatar_sha)

		# Save it to file
		self.save_vcard_to_hd(who, card)
		# Save the decoded avatar to a separate file too, and generate files for dbus notifications
		puny_jid = helpers.sanitize_filename(frm)
		puny_nick = None
		begin_path = os.path.join(gajim.AVATAR_PATH, puny_jid)
		frm_jid = frm
		if frm in self.room_jids:
			puny_nick = helpers.sanitize_filename(resource)
			# create folder if needed
			if not os.path.isdir(begin_path):
				os.mkdir(begin_path, 0700)
			begin_path = os.path.join(begin_path, puny_nick)
			frm_jid += '/' + resource
		if photo_decoded:
			avatar_file = begin_path + '_notif_size_colored.png'
			if frm_jid == our_jid and avatar_sha != self.vcard_sha:
				gajim.interface.save_avatar_files(frm, photo_decoded, puny_nick)
			elif frm_jid != our_jid and (not os.path.exists(avatar_file) or \
			not self.vcard_shas.has_key(frm_jid) or \
			avatar_sha != self.vcard_shas[frm_jid]):
				gajim.interface.save_avatar_files(frm, photo_decoded, puny_nick)
				if avatar_sha:
					self.vcard_shas[frm_jid] = avatar_sha
			elif self.vcard_shas.has_key(frm):
				del self.vcard_shas[frm]
		else:
			for ext in ('.jpeg', '.png', '_notif_size_bw.png',
				'_notif_size_colored.png'):
				path = begin_path + ext
				if os.path.isfile(path):
					os.remove(path)

		vcard['jid'] = frm
		vcard['resource'] = resource
		if frm_jid == our_jid:
			self.dispatch('MYVCARD', vcard)
			# we re-send our presence with sha if has changed and if we are
			# not invisible
			if self.vcard_sha == avatar_sha:
				return
			self.vcard_sha = avatar_sha
			if STATUS_LIST[self.connected] == 'invisible':
				return
			sshow = helpers.get_xmpp_show(STATUS_LIST[self.connected])
			p = common.xmpp.Presence(typ = None, priority = self.priority,
				show = sshow, status = self.status)
			p = self.add_sha(p)
			self.connection.send(p)
		else:
			self.dispatch('VCARD', vcard)

class ConnectionHandlers(ConnectionVcard, ConnectionBytestream, ConnectionDisco, ConnectionCommands, ConnectionPubSub):
	def __init__(self):
		ConnectionVcard.__init__(self)
		ConnectionBytestream.__init__(self)
		ConnectionCommands.__init__(self)
		ConnectionPubSub.__init__(self)
		# List of IDs we are waiting answers for {id: (type_of_request, data), }
		self.awaiting_answers = {}
		# List of IDs that will produce a timeout is answer doesn't arrive
		# {time_of_the_timeout: (id, message to send to gui), }
		self.awaiting_timeouts = {}
		# keep the jids we auto added (transports contacts) to not send the
		# SUBSCRIBED event to gui
		self.automatically_added = []
		# keep the latest subscribed event for each jid to prevent loop when we 
		# acknoledge presences
		self.subscribed_events = {}
		try:
			idle.init()
		except:
			HAS_IDLE = False
	
	def build_http_auth_answer(self, iq_obj, answer):
		if answer == 'yes':
			self.connection.send(iq_obj.buildReply('result'))
		elif answer == 'no':
			err = common.xmpp.Error(iq_obj,
				common.xmpp.protocol.ERR_NOT_AUTHORIZED)
			self.connection.send(err)
	
	def _HttpAuthCB(self, con, iq_obj):
		gajim.log.debug('HttpAuthCB')
		opt = gajim.config.get_per('accounts', self.name, 'http_auth')
		if opt in ('yes', 'no'):
			self.build_http_auth_answer(iq_obj, opt)
		else:
			id = iq_obj.getTagAttr('confirm', 'id')
			method = iq_obj.getTagAttr('confirm', 'method')
			url = iq_obj.getTagAttr('confirm', 'url')
			self.dispatch('HTTP_AUTH', (method, url, id, iq_obj));
		raise common.xmpp.NodeProcessed

	def _ErrorCB(self, con, iq_obj):
		gajim.log.debug('ErrorCB')
		if iq_obj.getQueryNS() == common.xmpp.NS_VERSION:
			who = helpers.get_full_jid_from_iq(iq_obj)
			jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
			self.dispatch('OS_INFO', (jid_stripped, resource, '', ''))
			return
		errmsg = iq_obj.getErrorMsg()
		errcode = iq_obj.getErrorCode()
		jid_from = helpers.get_full_jid_from_iq(iq_obj)
		id = unicode(iq_obj.getID())
		self.dispatch('ERROR_ANSWER', (id, jid_from, errmsg, errcode))
	
	def _PrivateCB(self, con, iq_obj):
		'''
		Private Data (JEP 048 and 049)
		'''
		gajim.log.debug('PrivateCB')
		query = iq_obj.getTag('query')
		storage = query.getTag('storage')
		if storage:
			ns = storage.getNamespace()
			if ns == 'storage:bookmarks':
				# Bookmarked URLs and Conferences
				# http://www.jabber.org/jeps/jep-0048.html
				confs = storage.getTags('conference')
				for conf in confs:
					autojoin_val = conf.getAttr('autojoin')
					if autojoin_val is None: # not there (it's optional)
						autojoin_val = False
					print_status = conf.getTagData('print_status')
					if not print_status:
						print_status = conf.getTagData('show_status')
					bm = {'name': conf.getAttr('name'),
							'jid': conf.getAttr('jid'),
							'autojoin': autojoin_val,
							'password': conf.getTagData('password'),
							'nick': conf.getTagData('nick'),
							'print_status': print_status}
					
					self.bookmarks.append(bm)
				self.dispatch('BOOKMARKS', self.bookmarks)

			elif ns == 'gajim:prefs':
				# Preferences data
				# http://www.jabber.org/jeps/jep-0049.html
				#TODO: implement this
				pass
			elif ns == 'storage:rosternotes':
				# Annotations
				# http://www.xmpp.org/extensions/xep-0145.html
				notes = storage.getTags('note')
				for note in notes:
					jid = note.getAttr('jid')
					annotation = note.getData()
					self.annotations[jid] = annotation

	def _PrivateErrorCB(self, con, iq_obj):
		gajim.log.debug('PrivateErrorCB')
		query = iq_obj.getTag('query')
		storage_tag = query.getTag('storage')
		if storage_tag:
			ns = storage_tag.getNamespace()
			if ns == 'storage:metacontacts':
				self.metacontacts_supported = False
				# Private XML Storage (JEP49) is not supported by server
				# Continue connecting
				self.connection.initRoster()

	def _rosterSetCB(self, con, iq_obj):
		gajim.log.debug('rosterSetCB')
		for item in iq_obj.getTag('query').getChildren():
			jid  = helpers.parse_jid(item.getAttr('jid'))
			name = item.getAttr('name')
			sub  = item.getAttr('subscription')
			ask  = item.getAttr('ask')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData())
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))
		raise common.xmpp.NodeProcessed
	
	def _VersionCB(self, con, iq_obj):
		gajim.log.debug('VersionCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('name', 'Gajim')
		qp.setTagData('version', gajim.version)
		send_os = gajim.config.get('send_os_info')
		if send_os:
			qp.setTagData('os', helpers.get_os_info())
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed
	
	def _LastCB(self, con, iq_obj):
		gajim.log.debug('IdleCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		if not HAS_IDLE:
			qp.attrs['seconds'] = '0';
		else:
			qp.attrs['seconds'] = idle.getIdleSec()
		
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed
	
	def _LastResultCB(self, con, iq_obj):
		gajim.log.debug('LastResultCB')
		qp = iq_obj.getTag('query')
		seconds = qp.getAttr('seconds')
		status = qp.getData()
		try:
			seconds = int(seconds)
		except:
			return
		who = helpers.get_full_jid_from_iq(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		self.dispatch('LAST_STATUS_TIME', (jid_stripped, resource, seconds, status))
	
	def _VersionResultCB(self, con, iq_obj):
		gajim.log.debug('VersionResultCB')
		client_info = ''
		os_info = ''
		qp = iq_obj.getTag('query')
		if qp.getTag('name'):
			client_info += qp.getTag('name').getData()
		if qp.getTag('version'):
			client_info += ' ' + qp.getTag('version').getData()
		if qp.getTag('os'):
			os_info += qp.getTag('os').getData()
		who = helpers.get_full_jid_from_iq(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		self.dispatch('OS_INFO', (jid_stripped, resource, client_info, os_info))

	def _TimeCB(self, con, iq_obj):
		gajim.log.debug('TimeCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('utc', strftime("%Y%m%dT%T", gmtime()))
		qp.setTagData('tz', strftime("%Z", gmtime()))
		qp.setTagData('display', strftime("%c", localtime()))
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _TimeRevisedCB(self, con, iq_obj):
		gajim.log.debug('TimeRevisedCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.setTag('time')
		qp.setTagData('utc', strftime("%Y-%m-%dT%TZ", gmtime()))
		qp.setTagData('tzo', "%+03d:00"% (-time.timezone/(60*60)))
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _gMailNewMailCB(self, con, gm):
		'''Called when we get notified of new mail messages in gmail account'''
		if not gm.getTag('new-mail'):
			return
		if gm.getTag('new-mail').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			# we'll now ask the server for the exact number of new messages
			jid = gajim.get_jid_from_account(self.name)
			gajim.log.debug('Got notification of new gmail e-mail on %s. Asking the server for more info.' % jid)
			iq = common.xmpp.Iq(typ = 'get')
			iq.setAttr('id', '13')
			query = iq.setTag('query')
			query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
			self.connection.send(iq)
			raise common.xmpp.NodeProcessed

	def _gMailQueryCB(self, con, gm):
		'''Called when we receive results from Querying the server for mail messages in gmail account'''
		if not gm.getTag('mailbox'):
			return
		if gm.getTag('mailbox').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			newmsgs = gm.getTag('mailbox').getAttr('total-matched')
			if newmsgs != '0':
				# there are new messages
				gmail_messages_list = []
				if gm.getTag('mailbox').getTag('mail-thread-info'):
					gmail_messages = gm.getTag('mailbox').getTags('mail-thread-info')
					for gmessage in gmail_messages:
						sender = gmessage.getTag('senders').getTag('sender')
						if not sender:
							continue
						gmail_from = sender.getAttr('address')
						gmail_subject = gmessage.getTag('subject').getData()
						gmail_snippet = gmessage.getTag('snippet').getData()
						gmail_messages_list.append({ \
							'From': gmail_from, \
							'Subject': gmail_subject, \
							'Snippet': gmail_snippet})
				jid = gajim.get_jid_from_account(self.name)
				gajim.log.debug(('You have %s new gmail e-mails on %s.') % (newmsgs, jid))
				self.dispatch('GMAIL_NOTIFY', (jid, newmsgs, gmail_messages_list))
			raise common.xmpp.NodeProcessed

	def _messageCB(self, con, msg):
		'''Called when we receive a message'''
		# check if the message is pubsub#event
		if msg.getTag('event') is not None:
			self._pubsubEventCB(con, msg)
			return
		msgtxt = msg.getBody()
		msghtml = msg.getXHTML()
		mtype = msg.getType()
		subject = msg.getSubject() # if not there, it's None
		tim = msg.getTimestamp()
		tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
		tim = time.localtime(timegm(tim))
		frm = helpers.get_full_jid_from_iq(msg)
		jid = helpers.get_jid_from_iq(msg)
		no_log_for = gajim.config.get_per('accounts', self.name,
			'no_log_for')
		if not no_log_for:
			no_log_for = ''
		no_log_for = no_log_for.split()
		encrypted = False
		chatstate = None
		encTag = msg.getTag('x', namespace = common.xmpp.NS_ENCRYPTED)
		decmsg = ''
		# invitations
		invite = None
		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None
		delayed = msg.getTag('x', namespace = common.xmpp.NS_DELAY) != None
		msg_id = None
		composing_jep = None
		# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) do NOT RECOMMENDED
		# invitation
		# stanza (MUC JEP) remove in 2007, as we do not do NOT RECOMMENDED
		xtags = msg.getTags('x')
		for xtag in xtags:
			if xtag.getNamespace() == common.xmpp.NS_CONFERENCE and not invite:
				room_jid = xtag.getAttr('jid')
				self.dispatch('GC_INVITATION', (room_jid, frm, '', None))
				return
		# chatstates - look for chatstate tags in a message if not delayed
		if not delayed:
			composing_jep = False
			children = msg.getChildren()
			for child in children:
				if child.getNamespace() == 'http://jabber.org/protocol/chatstates':
					chatstate = child.getName()
					composing_jep = 'JEP-0085'
					break
			# No JEP-0085 support, fallback to JEP-0022
			if not chatstate:
				chatstate_child = msg.getTag('x', namespace = common.xmpp.NS_EVENT)
				if chatstate_child:
					chatstate = 'active'
					composing_jep = 'JEP-0022'
					if not msgtxt and chatstate_child.getTag('composing'):
						chatstate = 'composing'
		# JEP-0172 User Nickname
		user_nick = msg.getTagData('nick')
		if not user_nick:
			user_nick = ''

		if encTag and GnuPG.USE_GPG:
			#decrypt
			encmsg = encTag.getData()
			
			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
			encrypted = True
		if mtype == 'error':
			error_msg = msg.getError()
			if not error_msg:
				error_msg = msgtxt
				msgtxt = None
			if self.name not in no_log_for:
				gajim.logger.write('error', frm, error_msg, tim = tim,
					subject = subject)
			self.dispatch('MSGERROR', (frm, msg.getErrorCode(), error_msg, msgtxt,
				tim))
			return
		elif mtype == 'groupchat':
			has_timestamp = False
			if msg.timestamp:
				has_timestamp = True
			if subject != None:
				self.dispatch('GC_SUBJECT', (frm, subject, msgtxt, has_timestamp))
			else:
				if not msg.getTag('body'): #no <body>
					return
				# Ignore message from room in which we are not
				if not self.last_history_line.has_key(jid):
					return
				self.dispatch('GC_MSG', (frm, msgtxt, tim, has_timestamp, msghtml))
				if self.name not in no_log_for and not int(float(time.mktime(tim)))\
				<= self.last_history_line[jid] and msgtxt:
					gajim.logger.write('gc_msg', frm, msgtxt, tim = tim)
			return
		elif mtype == 'chat': # it's type 'chat'
			if not msg.getTag('body') and chatstate is None: #no <body>
				return
			if msg.getTag('body') and self.name not in no_log_for and jid not in\
				no_log_for and msgtxt:
				msg_id = gajim.logger.write('chat_msg_recv', frm, msgtxt, tim = tim,
					subject = subject)
		else: # it's single message
			if invite is not None:
				item = invite.getTag('invite')
				jid_from = item.getAttr('from')
				reason = item.getTagData('reason')
				item = invite.getTag('password')
				password = invite.getTagData('password')
				self.dispatch('GC_INVITATION',(frm, jid_from, reason, password))
				return
			if self.name not in no_log_for and jid not in no_log_for and msgtxt:
				gajim.logger.write('single_msg_recv', frm, msgtxt, tim = tim,
					subject = subject)
			mtype = 'normal'
		treat_as = gajim.config.get('treat_incoming_messages')
		if treat_as:
			mtype = treat_as
		self.dispatch('MSG', (frm, msgtxt, tim, encrypted, mtype,
			subject, chatstate, msg_id, composing_jep, user_nick, msghtml))
	# END messageCB

	def _pubsubEventCB(self, con, msg):
		''' Called when we receive <message/> with pubsub event. '''
		# TODO: Logging? (actually services where logging would be useful, should
		# TODO: allow to access archives remotely...)
		jid = msg.getAttr('from')
		event = msg.getTag('event')

		# XEP-0107: User Mood
		items = event.getTag('items', {'node': 'http://jabber.org/protocol/mood'})
		if items: pep.user_mood(items, self.name, jid)
		# XEP-0118: User Tune
		items = event.getTag('items', {'node': 'http://jabber.org/protocol/tune'})
		if items: pep.user_tune(items, self.name, jid)
		# XEP-0080: User Geolocation
		items = event.getTag('items', {'node': 'http://jabber.org/protocol/geoloc'})
		if items: pep.user_geoloc(items, self.name, jid)

		items = event.getTag('items')
		if items is None: return

		for item in items.getTags('item'):
			# check for event type (for now only one type supported: pubsub.com events)
			child = item.getTag('pubsub-message')
			if child is not None:
				# we have pubsub.com notification
				child = child.getTag('feed')
				if child is None: continue

				for entry in child.getTags('entry'):
					# for each entry in feed (there shouldn't be more than one,
					# but to be sure...
					self.dispatch('ATOM_ENTRY', (atom.OldEntry(node=entry),))
				continue
			# unknown type... probably user has another client who understands that event
		
		raise common.xmpp.NodeProcessed

	def _presenceCB(self, con, prs):
		'''Called when we receive a presence'''
		ptype = prs.getType()
		if ptype == 'available':
			ptype = None
		gajim.log.debug('PresenceCB: %s' % ptype)
		try:
			who = helpers.get_full_jid_from_iq(prs)
		except:
			if prs.getTag('error').getTag('jid-malformed'):
				# wrong jid, we probably tried to change our nick in a room to a non valid
				# one
				who = str(prs.getFrom())
				jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
				self.dispatch('GC_MSG', (jid_stripped,
					_('Nickname not allowed: %s') % resource, None, False, None))
			return
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		timestamp = None
		is_gc = False # is it a GC presence ?
		sigTag = None
		ns_muc_user_x = None
		avatar_sha = None
		# JEP-0172 User Nickname
		user_nick = prs.getTagData('nick')
		if not user_nick:
			user_nick = ''
		transport_auto_auth = False
		xtags = prs.getTags('x')
		for x in xtags:
			namespace = x.getNamespace()
			if namespace.startswith(common.xmpp.NS_MUC):
				is_gc = True
				if namespace == common.xmpp.NS_MUC_USER and x.getTag('destroy'):
					ns_muc_user_x = x
			elif namespace == common.xmpp.NS_SIGNED:
				sigTag = x
			elif namespace == common.xmpp.NS_VCARD_UPDATE:
				avatar_sha = x.getTagData('photo')
			elif namespace == common.xmpp.NS_DELAY:
				# JEP-0091
				tim = prs.getTimestamp()
				tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
				timestamp = time.localtime(timegm(tim))
			elif namespace == 'http://delx.cjb.net/protocol/roster-subsync':
				# see http://trac.gajim.org/ticket/326
				agent = gajim.get_server_from_jid(jid_stripped)
				if self.connection.getRoster().getItem(agent): # to be sure it's a transport contact
					transport_auto_auth = True

		no_log_for = gajim.config.get_per('accounts', self.name,
			'no_log_for').split()
		status = prs.getStatus() or ''
		show = prs.getShow()
		if not show in STATUS_LIST:
			show = '' # We ignore unknown show
		if not ptype and not show:
			show = 'online'
		elif ptype == 'unavailable':
			show = 'offline'

		prio = prs.getPriority()
		try:
			prio = int(prio)
		except:
			prio = 0
		keyID = ''
		if sigTag and GnuPG.USE_GPG:
			#verify
			sigmsg = sigTag.getData()
			keyID = self.gpg.verify(status, sigmsg)

		if is_gc:
			if ptype == 'error':
				errmsg = prs.getError()
				errcode = prs.getErrorCode()
				if errcode == '502': # Internal Timeout:
					self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
						prio, keyID, timestamp))
				elif errcode == '401': # password required to join
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('A password is required to join this group chat.')))
				elif errcode == '403': # we are banned
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('You are banned from this group chat.')))
				elif errcode == '404': # group chat does not exist
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Such group chat does not exist.')))
				elif errcode == '405':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Group chat creation is restricted.')))
				elif errcode == '406':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Your registered nickname must be used.')))
				elif errcode == '407':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('You are not in the members list.')))
				elif errcode == '409': # nick conflict
					# the jid_from in this case is FAKE JID: room_jid/nick
					# resource holds the bad nick so propose a new one
					proposed_nickname = resource + \
						gajim.config.get('gc_proposed_nick_char')
					room_jid = gajim.get_room_from_fjid(who)
					self.dispatch('ASK_NEW_NICK', (room_jid, _('Unable to join group chat'),
		_('Your desired nickname is in use or registered by another occupant.\nPlease specify another nickname below:'), proposed_nickname))
				else:	# print in the window the error
					self.dispatch('ERROR_ANSWER', ('', jid_stripped,
						errmsg, errcode))
			if not ptype or ptype == 'unavailable':
				if gajim.config.get('log_contact_status_changes') and self.name\
				not in no_log_for and jid_stripped not in no_log_for:
					gc_c = gajim.contacts.get_gc_contact(self.name, jid_stripped, resource)
					st = status or ''
					if gc_c:
						jid = gc_c.jid
					else:
						jid = prs.getJid()
					if jid:
						# we know real jid, save it in db
						st += ' (%s)' % jid
					gajim.logger.write('gcstatus', who, st, show)
				if avatar_sha or avatar_sha == '':
					if avatar_sha == '':
						# contact has no avatar
						puny_nick = helpers.sanitize_filename(resource)
						gajim.interface.remove_avatar_files(jid_stripped, puny_nick)
					if self.vcard_shas.has_key(who): # Verify sha cached in mem
						if avatar_sha != self.vcard_shas[who]:
							# avatar has been updated
							self.request_vcard(who, True)
					else: # Verify sha cached in hdd
						cached_vcard = self.get_cached_vcard(who, True)
						if cached_vcard and cached_vcard.has_key('PHOTO') and \
						cached_vcard['PHOTO'].has_key('SHA'):
							cached_sha = cached_vcard['PHOTO']['SHA']
						else:
							cached_sha = ''
						if cached_sha != avatar_sha:
							# avatar has been updated
							# sha in mem will be updated later
							self.request_vcard(who, True)
						else:
							# save sha in mem NOW
							self.vcard_shas[who] = avatar_sha
				if ns_muc_user_x:
					# Room has been destroyed. see
					# http://www.xmpp.org/extensions/xep-0045.html#destroyroom
					reason = _('Room has been destroyed')
					destroy = ns_muc_user_x.getTag('destroy')
					r = destroy.getTagData('reason')
					if r:
						reason += ' (%s)' % r
					jid = destroy.getAttr('jid')
					if jid:
						reason += '\n' + _('You can join this room instead: %s') % jid
					statusCode = 'destroyed'
				else:
					reason = prs.getReason()
					statusCode = prs.getStatusCode()
				self.dispatch('GC_NOTIFY', (jid_stripped, show, status, resource,
					prs.getRole(), prs.getAffiliation(), prs.getJid(),
					reason, prs.getActor(), statusCode, prs.getNewNick()))
			return

		if ptype == 'subscribe':
			gajim.log.debug('subscribe request from %s' % who)
			if gajim.config.get('alwaysauth') or who.find("@") <= 0 or \
			jid_stripped in self.jids_for_auto_auth or transport_auto_auth:
				if self.connection:
					p = common.xmpp.Presence(who, 'subscribed')
					p = self.add_sha(p)
					self.connection.send(p)
				if who.find("@") <= 0 or transport_auto_auth:
					self.dispatch('NOTIFY', (jid_stripped, 'offline', 'offline',
						resource, prio, keyID, timestamp))
				if transport_auto_auth:
					self.automatically_added.append(jid_stripped)
					self.request_subscription(jid_stripped, name = user_nick)
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (who, status, user_nick))
		elif ptype == 'subscribed':
			if jid_stripped in self.automatically_added:
				self.automatically_added.remove(jid_stripped)
			else:
				# detect a subscription loop
				if not self.subscribed_events.has_key(jid_stripped):
					self.subscribed_events[jid_stripped] = []
				self.subscribed_events[jid_stripped].append(time.time())
				block = False
				if len(self.subscribed_events[jid_stripped]) > 5:
					if time.time() - self.subscribed_events[jid_stripped][0] < 5:
						block = True
					self.subscribed_events[jid_stripped] = self.subscribed_events[jid_stripped][1:]
				if block:
					gajim.config.set_per('account', self.name,
						'dont_ack_subscription', True)
				else:
					self.dispatch('SUBSCRIBED', (jid_stripped, resource))
			# BE CAREFUL: no con.updateRosterItem() in a callback
			gajim.log.debug(_('we are now subscribed to %s') % who)
		elif ptype == 'unsubscribe':
			gajim.log.debug(_('unsubscribe request from %s') % who)
		elif ptype == 'unsubscribed':
			gajim.log.debug(_('we are now unsubscribed from %s') % who)
			# detect a unsubscription loop
			if not self.subscribed_events.has_key(jid_stripped):
				self.subscribed_events[jid_stripped] = []
			self.subscribed_events[jid_stripped].append(time.time())
			block = False
			if len(self.subscribed_events[jid_stripped]) > 5:
				if time.time() - self.subscribed_events[jid_stripped][0] < 5:
					block = True
				self.subscribed_events[jid_stripped] = self.subscribed_events[jid_stripped][1:]
			if block:
				gajim.config.set_per('account', self.name, 'dont_ack_subscription',
					True)
			else:
				self.dispatch('UNSUBSCRIBED', jid_stripped)
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '502': # Internal Timeout:
				self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
					prio, keyID, timestamp))
			else:	# print in the window the error
				self.dispatch('ERROR_ANSWER', ('', jid_stripped,
					errmsg, errcode))

		if avatar_sha and ptype != 'error':
			if not self.vcard_shas.has_key(jid_stripped):
				cached_vcard = self.get_cached_vcard(jid_stripped)
				if cached_vcard and cached_vcard.has_key('PHOTO') and \
				cached_vcard['PHOTO'].has_key('SHA'):
					self.vcard_shas[jid_stripped] = cached_vcard['PHOTO']['SHA']
				else:
					self.vcard_shas[jid_stripped] = ''
			if avatar_sha != self.vcard_shas[jid_stripped]:
				# avatar has been updated
				self.request_vcard(jid_stripped)
		if not ptype or ptype == 'unavailable':
			if gajim.config.get('log_contact_status_changes') and self.name\
				not in no_log_for and jid_stripped not in no_log_for:
				gajim.logger.write('status', jid_stripped, status, show)
			self.dispatch('NOTIFY', (jid_stripped, show, status, resource, prio,
				keyID, timestamp))
	# END presenceCB

	def _StanzaArrivedCB(self, con, obj):
		self.last_io = gajim.idlequeue.current_time()

	def _MucOwnerCB(self, con, iq_obj):
		gajim.log.debug('MucOwnerCB')
		qp = iq_obj.getQueryPayload()
		node = None
		for q in qp:
			if q.getNamespace() == common.xmpp.NS_DATA:
				node = q
		if not node:
			return
		self.dispatch('GC_CONFIG', (helpers.get_full_jid_from_iq(iq_obj), node))

	def _MucAdminCB(self, con, iq_obj):
		gajim.log.debug('MucAdminCB')
		items = iq_obj.getTag('query', namespace = common.xmpp.NS_MUC_ADMIN).getTags('item')
		list = {}
		affiliation = ''
		for item in items:
			if item.has_attr('jid') and item.has_attr('affiliation'):
				jid = item.getAttr('jid')
				affiliation = item.getAttr('affiliation')
				list[jid] = {'affiliation': affiliation}
				if item.has_attr('nick'):
					list[jid]['nick'] = item.getAttr('nick')
				if item.has_attr('role'):
					list[jid]['role'] = item.getAttr('role')
				reason = item.getTagData('reason')
				if reason:
					list[jid]['reason'] = reason

		self.dispatch('GC_AFFILIATION', (helpers.get_full_jid_from_iq(iq_obj), 
															affiliation, list))

	def _MucErrorCB(self, con, iq_obj):
		gajim.log.debug('MucErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		self.dispatch('MSGERROR', (jid, errcode, errmsg))

	def _IqPingCB(self, con, iq_obj):
		gajim.log.debug('IqPingCB')
		iq_obj = iq_obj.buildReply('result')
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _getRosterCB(self, con, iq_obj):
		if not self.connection:
			return
		self.connection.getRoster(self._on_roster_set)
		if gajim.config.get_per('accounts', self.name, 'use_ft_proxies'):
			self.discover_ft_proxies()
	
	def discover_ft_proxies(self):
		cfg_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		if cfg_proxies:
			proxies = map(lambda e:e.strip(), cfg_proxies.split(','))
			for proxy in proxies:
				gajim.proxy65_manager.resolve(proxy, self.connection)
			self.discoverItems(gajim.config.get_per('accounts', self.name, 
				'hostname'), id_prefix='p')
	
	def _on_roster_set(self, roster):
		raw_roster = roster.getRaw()
		roster = {}
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name))
		for jid in raw_roster:
			try:
				j = helpers.parse_jid(jid)
			except:
				print >> sys.stderr, _('JID %s is not RFC compliant. It will not be added to your roster. Use roster management tools such as http://jru.jabberstudio.org/ to remove it') % jid
			else:
				infos = raw_roster[jid]
				if jid != our_jid and (not infos['subscription'] or \
				infos['subscription'] == 'none') and (not infos['ask'] or \
				infos['ask'] == 'none') and not infos['name'] and \
				not infos['groups']:
					# remove this useless item, it won't be shown in roster anyway
					self.connection.getRoster().delItem(jid)
				elif jid != our_jid: # don't add our jid
					roster[j] = raw_roster[jid]
					if gajim.jid_is_transport(jid) and \
					not gajim.get_transport_name_from_jid(jid):
						# we can't determine which iconset to use
						self.discoverInfo(jid)

		self.dispatch('ROSTER', roster)

		# continue connection
		if self.connected > 1 and self.continue_connect_info:
			show = self.continue_connect_info[0]
			msg = self.continue_connect_info[1]
			signed = self.continue_connect_info[2]
			self.connected = STATUS_LIST.index(show)
			sshow = helpers.get_xmpp_show(show)
			# send our presence
			if show == 'invisible':
				self.send_invisible_presence(msg, signed, True)
				return
			priority = gajim.get_priority(self.name, sshow)
			vcard = self.get_cached_vcard(jid)
			if vcard and vcard.has_key('PHOTO') and vcard['PHOTO'].has_key('SHA'):
				self.vcard_sha = vcard['PHOTO']['SHA']
			p = common.xmpp.Presence(typ = None, priority = priority, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)

			if self.connection:
				self.connection.send(p)
				self.priority = priority
			self.dispatch('STATUS', show)
			# ask our VCard
			self.request_vcard(None)

			# Get bookmarks from private namespace
			self.get_bookmarks()

			# Get annotations from private namespace
			self.get_annotations()

			# If it's a gmail account,
			# inform the server that we want e-mail notifications
			if gajim.get_server_from_jid(our_jid) in gajim.gmail_domains:
				gajim.log.debug(('%s is a gmail account. Setting option '
					'to get e-mail notifications on the server.') % (our_jid))
				iq = common.xmpp.Iq(typ = 'set', to = our_jid)
				iq.setAttr('id', 'MailNotify')
				query = iq.setTag('usersetting')
				query.setNamespace(common.xmpp.NS_GTALKSETTING)
				query = query.setTag('mailnotifications')
				query.setAttr('value', 'true')
				self.connection.send(iq)
				# Ask how many messages there are now
				iq = common.xmpp.Iq(typ = 'get')
				iq.setAttr('id', '13')
				query = iq.setTag('query')
				query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
				self.connection.send(iq)

			#Inform GUI we just signed in
			self.dispatch('SIGNED_IN', ())
		self.continue_connect_info = None
	
	def _register_handlers(self, con, con_type):
		# try to find another way to register handlers in each class 
		# that defines handlers
		con.RegisterHandler('message', self._messageCB)
		con.RegisterHandler('presence', self._presenceCB)
		con.RegisterHandler('iq', self._vCardCB, 'result',
			common.xmpp.NS_VCARD)
		con.RegisterHandler('iq', self._rosterSetCB, 'set',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._siSetCB, 'set',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siErrorCB, 'error',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siResultCB, 'result',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._discoGetCB, 'get',
			common.xmpp.NS_DISCO)
		con.RegisterHandler('iq', self._bytestreamSetCB, 'set',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamResultCB, 'result',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverItemsErrorCB, 'error',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverInfoErrorCB, 'error',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._VersionCB, 'get',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._TimeCB, 'get',
			common.xmpp.NS_TIME)
		con.RegisterHandler('iq', self._TimeRevisedCB, 'get',
			common.xmpp.NS_TIME_REVISED)
		con.RegisterHandler('iq', self._LastCB, 'get',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._LastResultCB, 'result',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._VersionResultCB, 'result',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._MucOwnerCB, 'result',
			common.xmpp.NS_MUC_OWNER)
		con.RegisterHandler('iq', self._MucAdminCB, 'result',
			common.xmpp.NS_MUC_ADMIN)
		con.RegisterHandler('iq', self._getRosterCB, 'result',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._PrivateCB, 'result',
			common.xmpp.NS_PRIVATE)
		con.RegisterHandler('iq', self._HttpAuthCB, 'get',
			common.xmpp.NS_HTTP_AUTH)
		con.RegisterHandler('iq', self._CommandExecuteCB, 'set',
			common.xmpp.NS_COMMANDS)
		con.RegisterHandler('iq', self._gMailNewMailCB, 'set',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._gMailQueryCB, 'result',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._DiscoverInfoGetCB, 'get',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverItemsGetCB, 'get',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._IqPingCB, 'get',
			common.xmpp.NS_PING)
		con.RegisterHandler('iq', self._PubSubCB, 'result')
		con.RegisterHandler('iq', self._ErrorCB, 'error')
		con.RegisterHandler('iq', self._IqCB)
		con.RegisterHandler('iq', self._StanzaArrivedCB)
		con.RegisterHandler('iq', self._ResultCB, 'result')
		con.RegisterHandler('presence', self._StanzaArrivedCB)
		con.RegisterHandler('message', self._StanzaArrivedCB)
