
##	common/xmpp/socks5.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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


import socket
import struct
import sha
from dialogs import BindPortError

from errno import EWOULDBLOCK
from errno import ENOBUFS
from errno import EINTR
from errno import EISCONN
from xmpp.idlequeue import IdleObject
MAX_BUFF_LEN = 65536

# after foo seconds without activity label transfer as 'stalled'
STALLED_TIMEOUT = 10

# after foo seconds of waiting to connect, disconnect from
# streamhost and try next one
CONNECT_TIMEOUT = 30

# nothing received for the last foo seconds - stop transfer
# if it is 0, then transfer will wait forever
READ_TIMEOUT = 180

# nothing sent for the last foo seconds - stop transfer
# if it is 0, then transfer will wait forever
SEND_TIMEOUT = 180

class SocksQueue:
	''' queue for all file requests objects '''
	def __init__(self, idlequeue, complete_transfer_cb = None, progress_transfer_cb = None):
		self.connected = 0
		self.readers = {}
		self.files_props = {}
		self.senders = {}
		self.idx = 1
		self.listener = None
		self.sha_handlers = {}
		# handle all io events in the global idle queue, instead of processing
		# each foo seconds
		self.idlequeue = idlequeue
		self.complete_transfer_cb = complete_transfer_cb
		self.progress_transfer_cb = progress_transfer_cb
		self.on_success = None
		self.on_failure = None
	
	def start_listener(self, port, sha_str, sha_handler, sid):
		''' start waiting for incomming connections on (host, port)
		and do a socks5 authentication using sid for generated sha
		'''
		self.sha_handlers[sha_str] = (sha_handler, sid)
		if self.listener == None:
			self.listener = Socks5Listener(self.idlequeue, port)
			self.listener.queue = self
			self.listener.bind()
			if self.listener.started is False:
				self.listener = None
				# We cannot bind port, call error 
				# dialog from dialogs.py and fail
				BindPortError(port)
				return None
			self.connected += 1
		return self.listener
	
	def send_success_reply(self, file_props, streamhost):
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
				if file_props.has_key('proxyhosts'):
					for proxy in file_props['proxyhosts']:
						if proxy == streamhost:
							self.on_success(streamhost)
							return 2
				return 0
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if streamhost['state'] == 1:
					return 0
			streamhost['state'] = 1
			self.on_success(streamhost)
			return 1
		return 0
	
	def connect_to_hosts(self, account, sid, on_success = None, 
		on_failure = None):
		self.on_success = on_success
		self.on_failure = on_failure
		file_props = self.files_props[account][sid]
		file_props['failure_cb'] = on_failure
		
		# add streamhosts to the queue 
		for streamhost in file_props['streamhosts']:
			receiver = Socks5Receiver(self.idlequeue, streamhost, sid, file_props)
			self.add_receiver(account, receiver)
			streamhost['idx'] = receiver.queue_idx
	
	def _socket_connected(self, streamhost, file_props):
		''' called when there is a host connected to one of the 
		senders's streamhosts. Stop othere attempts for connections '''
		for host in file_props['streamhosts']:
			if host != streamhost and host.has_key('idx'):
				if host['state'] == 1:
					# remove current
					self.remove_receiver(streamhost['idx'])
					return
				# set state -2, meaning that this streamhost is stopped,
				# but it may be connectected later
				if host['state'] >=0:
					self.remove_receiver(host['idx'])
					host['idx'] = -1
					host['state'] = -2
	
	def reconnect_receiver(self, receiver, streamhost):
		''' Check the state of all streamhosts and if all has failed, then 
		emit connection failure cb. If there are some which are still 
		not connected try to establish connection to one of them.
		'''
		self.idlequeue.remove_timeout(receiver.fd)
		self.idlequeue.unplug_idle(receiver.fd)
		file_props = receiver.file_props
		streamhost['state'] = -1
		# boolean, indicates that there are hosts, which are not tested yet
		unused_hosts = False
		for host in file_props['streamhosts']:
			if host.has_key('idx'):
				if host['state'] >= 0:
					return
				elif host['state'] == -2:
					unused_hosts = True
		if unused_hosts:
			for host in file_props['streamhosts']:
				if host['state'] == -2:
					host['state'] = 0
					receiver = Socks5Receiver(self.idlequeue, host, host['sid'], file_props)
					self.add_receiver(receiver.account, receiver)
					host['idx'] = receiver.queue_idx
			# we still have chances to connect
			return
		if not file_props.has_key('received-len') or file_props['received-len'] == 0:
			# there are no other streamhosts and transfer hasn't started
			self._connection_refused(streamhost, file_props, receiver.queue_idx)
		else:
			# transfer stopped, it is most likely stopped from sender
			receiver.disconnect()
			file_props['error'] = -1
			self.process_result(-1, receiver)
	
	def _connection_refused(self, streamhost, file_props, idx):
		''' cb, called when we loose connection during transfer'''
		if file_props is None:
			return
		streamhost['state'] = -1
		self.remove_receiver(idx, False)
		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host['state'] != -1:
					return
		# failure_cb exists - this means that it has never been called
		if file_props.has_key('failure_cb') and file_props['failure_cb']:
			file_props['failure_cb'](streamhost['initiator'], streamhost['id'], 
				file_props['sid'], code = 404)
			del(file_props['failure_cb'])
	
	def add_receiver(self, account, sock5_receiver):
		''' add new file request '''
		self.readers[self.idx] = sock5_receiver
		sock5_receiver.queue_idx = self.idx
		sock5_receiver.queue = self
		sock5_receiver.account = account
		self.idx += 1
		result = sock5_receiver.connect()
		self.connected += 1
		if result != None:
			result = sock5_receiver.main()
			self.process_result(result, sock5_receiver)
			return 1
		return None
	
	def get_file_from_sender(self, file_props, account):
		if file_props is None:
			return
		if file_props.has_key('hash') and \
			self.senders.has_key(file_props['hash']):
			
			sender = self.senders[file_props['hash']]
			sender.account = account
			result = self.get_file_contents(0)
			self.process_result(result, sender)
	
	def result_sha(self, sha_str, idx):
		if self.sha_handlers.has_key(sha_str):
			props = self.sha_handlers[sha_str]
			props[0](props[1], idx)
	
	def activate_proxy(self, idx):
		if not self.readers.has_key(idx):
			return
		reader = self.readers[idx]
		if reader.file_props['type'] != 's':
			return
		if reader.state != 5:
			return
		reader.state = 6
		if reader.connected:
			reader.file_props['error'] = 0
			reader.file_props['disconnect_cb'] = reader.disconnect
			reader.file_props['started'] = True
			reader.file_props['completed'] = False
			reader.file_props['paused'] = False
			reader.file_props['stalled'] = False
			reader.file_props['elapsed-time'] = 0
			reader.file_props['last-time'] = self.idlequeue.current_time()
			reader.file_props['received-len'] = 0
			reader.pauses = 0
			# start sending file to proxy
			self.idlequeue.set_read_timeout(reader.fd, STALLED_TIMEOUT)
			self.idlequeue.plug_idle(reader, True, False)
			result = reader.write_next()
			self.process_result(result, reader)
	
	def send_file(self, file_props, account):
		if file_props.has_key('hash') and \
			self.senders.has_key(file_props['hash']):
			sender = self.senders[file_props['hash']]
			file_props['streamhost-used'] = True
			sender.account = account
			if file_props['type'] == 's':
				sender.file_props = file_props 
				result = sender.send_file()
				self.process_result(result, sender)
			else:
				file_props['elapsed-time'] = 0
				file_props['last-time'] = self.idlequeue.current_time()
				file_props['received-len'] = 0
				sender.file_props = file_props
	
	def add_file_props(self, account, file_props):
		''' file_prop to the dict of current file_props.
		It is identified by account name and sid
		'''
		if file_props is None or \
			file_props.has_key('sid') is False:
			return
		_id = file_props['sid']
		if not self.files_props.has_key(account):
			self.files_props[account] = {}
		self.files_props[account][_id] = file_props
	
	def remove_file_props(self, account, sid):
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
			if fl_props.has_key(sid):
				del(fl_props[sid])
		
		if len(self.files_props) == 0:
			self.connected = 0
		
	def get_file_props(self, account, sid):
		''' get fil_prop by account name and session id '''
		if self.files_props.has_key(account):
			fl_props = self.files_props[account]
			if fl_props.has_key(sid):
				return fl_props[sid]
		return None
	
	def on_connection_accepted(self, sock):
		sock_hash =  sock.__hash__()
		if not self.senders.has_key(sock_hash):
			self.senders[sock_hash] = Socks5Sender(self.idlequeue, 
				sock_hash, self, sock[0], sock[1][0], sock[1][1])
			self.connected += 1
	
	def process_result(self, result, actor):
		''' Take appropriate actions upon the result:
		[ 0, - 1 ] complete/end transfer
		[ > 0 ] send progress message
		[ None ] do nothing
		'''
		if result is None:
			return
		if result in (0, -1) and self.complete_transfer_cb is not None:
			account = actor.account
			if account is None and actor.file_props.has_key('tt_account'):
				account = actor.file_props['tt_account']
			self.complete_transfer_cb(account, actor.file_props)
		elif self.progress_transfer_cb is not None:
			self.progress_transfer_cb(actor.account, actor.file_props)
	
	def remove_receiver(self, idx, do_disconnect = True):
		''' Remove reciver from the list and decrease 
		the number of active connections with 1'''
		if idx != -1:
			if self.readers.has_key(idx):
				reader = self.readers[idx]
				self.idlequeue.unplug_idle(reader.fd)
				self.idlequeue.remove_timeout(reader.fd)
				if do_disconnect:
					reader.disconnect()
				else:
					if reader.streamhost is not None:
						reader.streamhost['state'] = -1 
					del(self.readers[idx])
	
	def remove_sender(self, idx, do_disconnect = True):
		''' Remove sender from the list of senders and decrease the 
		number of active connections with 1'''
		if idx != -1:
			if self.senders.has_key(idx):
				if do_disconnect:
					self.senders[idx].disconnect()
					return
				else:
					del(self.senders[idx])
					if self.connected > 0:
						self.connected -= 1
			if len(self.senders) == 0 and self.listener is not None:
				self.listener.disconnect()
				self.listener = None
				self.connected -= 1
	
class Socks5:
	def __init__(self, idlequeue, host, port, initiator, target, sid):
		if host is not None:
			try:
				self.host = socket.gethostbyname(host)
			except socket.gaierror:
				self.host = None
		self.idlequeue = idlequeue
		self.fd = -1
		self.port = port
		self.initiator = initiator
		self.target = target
		self.sid = sid
		self._sock = None
		self.account = None
		self.state = 0 # not connected
		self.pauses = 0
		self.size = 0
		self.remaining_buff = ''
		self.file = None
	
	def open_file_for_reading(self):
		if self.file == None:
			try:
				self.file = open(self.file_props['file-name'],'rb')
				if self.file_props.has_key('offset') and self.file_props['offset']:
					self.size = self.file_props['offset']
					self.file.seek(self.size)
					self.file_props['received-len'] = self.size
			except IOError, e:
				self.close_file()
				raise IOError, e
	
	def close_file(self):
		if self.file:
			if not self.file.closed:
				try:
					self.file.close()
				except:
					pass
			self.file = None
	
	def get_fd(self):
		''' Test if file is already open and return its fd,
		or just open the file and return the fd.
		'''
		if self.file_props.has_key('fd'):
			fd = self.file_props['fd']
		else:
			offset = 0
			opt = 'wb'
			if self.file_props.has_key('offset') and self.file_props['offset']:
				offset = self.file_props['offset']
				opt = 'ab'
			fd = open(self.file_props['file-name'], opt)
			self.file_props['fd'] = fd
			self.file_props['elapsed-time'] = 0
			self.file_props['last-time'] = self.idlequeue.current_time()
			self.file_props['received-len'] = offset
		return fd
	
	def rem_fd(self, fd):
		if self.file_props.has_key('fd'):
			del(self.file_props['fd'])
		try:
			fd.close()
		except:
			pass
			
	
	def receive(self):
		''' Reads small chunks of data. 
			Calls owner's disconnected() method if appropriate.'''
		received = ''
		try: 
			add = self._recv(64)
		except Exception, e: 
			add=''
		received +=add
		if len(add) == 0:
			self.disconnect()
		return add
	
	def send_raw(self,raw_data):
		''' Writes raw outgoing data. '''
		try:
			lenn = self._send(raw_data)
		except Exception, e:
			self.disconnect()
		return len(raw_data)
	
	def write_next(self):
		if self.remaining_buff != '':
			buff = self.remaining_buff
			self.remaining_buff = ''
		else:
			try:
				self.open_file_for_reading()
			except IOError, e:
				self.state = 8 # end connection
				self.disconnect()
				self.file_props['error'] = -7 # unable to read from file
				return -1
			buff = self.file.read(MAX_BUFF_LEN)
		if len(buff) > 0:
			lenn = 0
			try:
				lenn = self._send(buff)
			except Exception, e:
				if e.args[0] not in (EINTR, ENOBUFS, EWOULDBLOCK):
					# peer stopped reading
					self.state = 8 # end connection
					self.disconnect()
					self.file_props['error'] = -1
					return -1
			self.size += lenn
			current_time = self.idlequeue.current_time()
			self.file_props['elapsed-time'] += current_time - \
				self.file_props['last-time']
			self.file_props['last-time'] = current_time
			self.file_props['received-len'] = self.size
			if self.size >= int(self.file_props['size']):
				self.state = 8 # end connection
				self.file_props['error'] = 0
				self.disconnect()
				return -1
			if lenn != len(buff):
				self.remaining_buff = buff[lenn:]
			else:
				self.remaining_buff = ''
			self.state = 7 # continue to write in the socket
			if lenn == 0:
				return None
			self.file_props['stalled'] = False
			return lenn
		else:
			self.state = 8 # end connection
			self.disconnect()
			return -1
	
	def get_file_contents(self, timeout):
		''' read file contents from socket and write them to file ''', \
			self.file_props['type'], self.file_props['sid']
		if self.file_props is None or \
			self.file_props.has_key('file-name') is False:
			self.file_props['error'] = -2
			return None
		fd = None
		if self.remaining_buff != '':
			fd = self.get_fd()
			fd.write(self.remaining_buff)
			lenn = len(self.remaining_buff)
			current_time = self.idlequeue.current_time()
			self.file_props['elapsed-time'] += current_time - \
				self.file_props['last-time']
			self.file_props['last-time'] = current_time
			self.file_props['received-len'] += lenn
			self.remaining_buff = ''
			if self.file_props['received-len'] == int(self.file_props['size']):
				self.rem_fd(fd)
				self.disconnect()
				self.file_props['error'] = 0
				self.file_props['completed'] = True
				return 0
		else:
			fd = self.get_fd()
			try: 
				buff = self._recv(MAX_BUFF_LEN)
			except Exception, e:
				buff = ''
			current_time = self.idlequeue.current_time()
			self.file_props['elapsed-time'] += current_time - \
				self.file_props['last-time']
			self.file_props['last-time'] = current_time
			self.file_props['received-len'] += len(buff)
			if len(buff) == 0:
				# Transfer stopped  somehow:
				# reset, paused or network error
				self.rem_fd(fd)
				self.disconnect(False)
				self.file_props['error'] = -1
				return 0
			try:
				fd.write(buff)
			except IOError, e:
				self.rem_fd(fd)
				self.disconnect(False)
				self.file_props['error'] = -6 # file system error
				return 0
			if self.file_props['received-len'] >= int(self.file_props['size']):
				# transfer completed
				self.rem_fd(fd)
				self.disconnect()
				self.file_props['error'] = 0
				self.file_props['completed'] = True
				return 0
			# return number of read bytes. It can be used in progressbar
		if fd != None:
			self.file_props['stalled'] = False
		if fd == None and self.file_props['stalled'] is False:
			return None
		if self.file_props.has_key('received-len'):
			if self.file_props['received-len'] != 0:
				return self.file_props['received-len']
		return None
	
	def disconnect(self):
		''' Closes open descriptors and remover socket descr. from idleque '''
		# be sure that we don't leave open file
		self.close_file()
		self.idlequeue.remove_timeout(self.fd)
		self.idlequeue.unplug_idle(self.fd)
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except:
			# socket is already closed
			pass
		self.connected = False
		self.fd = -1
		self.state = -1
	
	def _get_auth_buff(self):
		''' Message, that we support 1 one auth mechanism: 
		the 'no auth' mechanism. '''
		return struct.pack('!BBB', 0x05, 0x01, 0x00)
	
	def _parse_auth_buff(self, buff):
		''' Parse the initial message and create a list of auth
		mechanisms '''
		auth_mechanisms = []
		try:
			ver, num_auth = struct.unpack('!BB', buff[:2])
			for i in xrange(num_auth):
				mechanism, = struct.unpack('!B', buff[1 + i])
				auth_mechanisms.append(mechanism)
		except:
			return None
		return auth_mechanisms
	def _get_auth_response(self):
		''' socks version(5), number of extra auth methods (we send
		0x00 - no auth
		) '''
		return struct.pack('!BB', 0x05, 0x00)
	
	def _get_connect_buff(self):
		''' Connect request by domain name '''
		buff = struct.pack('!BBBBB%dsBB' % len(self.host), 
			0x05, 0x01, 0x00, 0x03, len(self.host), self.host, 
			self.port >> 8, self.port & 0xff)
		return buff
	
	def _get_request_buff(self, msg, command = 0x01):
		''' Connect request by domain name, 
		sid sha, instead of domain name (jep 0096) '''
		buff = struct.pack('!BBBBB%dsBB' % len(msg), 
			0x05, command, 0x00, 0x03, len(msg), msg, 0, 0)
		return buff
	
	def _parse_request_buff(self, buff):
		try: # don't trust on what comes from the outside
			version, req_type, reserved, host_type,  = \
				struct.unpack('!BBBB', buff[:4])
			if host_type == 0x01:
				host_arr = struct.unpack('!iiii', buff[4:8])
				host, = reduce(lambda e1, e2: str(e1) + "." + str(e2), host_arr)
				host_len = len(host)
			elif host_type == 0x03:
				host_len,  = struct.unpack('!B' , buff[4])
				host, = struct.unpack('!%ds' % host_len, buff[5:5 + host_len])
			portlen = len(buff[host_len + 5:])
			if portlen == 1: 
				port, = struct.unpack('!B', buff[host_len + 5])
			elif portlen == 2: 
				port, = struct.unpack('!H', buff[host_len + 5:])
			# file data, comes with auth message (Gaim bug)
			else: 
				port, = struct.unpack('!H', buff[host_len + 5: host_len + 7])
				self.remaining_buff = buff[host_len + 7:]
		except:
			return (None, None, None)
		return (req_type, host, port)
	
	def read_connect(self):
		''' connect responce: version, auth method '''
		buff = self._recv()
		try:
			version, method = struct.unpack('!BB', buff)
		except:
			version, method = None, None
		if version != 0x05 or method == 0xff:
			self.disconnect()
	
	def continue_paused_transfer(self):
		if self.state < 5:
			return
		if self.file_props['type'] == 'r':
			self.idlequeue.plug_idle(self, False, True)
		else:
			self.idlequeue.plug_idle(self, True, False)
	
	def _get_sha1_auth(self):
		''' get sha of sid + Initiator jid + Target jid '''
		if self.file_props.has_key('is_a_proxy'):
			del(self.file_props['is_a_proxy'])
			return sha.new('%s%s%s' % (self.sid, self.file_props['proxy_sender'], 
				self.file_props['proxy_receiver'])).hexdigest()
		return sha.new('%s%s%s' % (self.sid, self.initiator, self.target)).hexdigest()
	
class Socks5Sender(Socks5, IdleObject):
	''' class for sending file to socket over socks5 '''
	def __init__(self, idlequeue, sock_hash, parent, _sock, host = None, port = None):
		self.queue_idx = sock_hash
		self.queue = parent
		Socks5.__init__(self, idlequeue, host, port, None, None, None)
		self._sock = _sock
		self._sock.setblocking(False)
		self.fd = _sock.fileno()
		self._recv = _sock.recv
		self._send = _sock.send
		self.connected = True
		self.state = 1 # waiting for first bytes
		self.file_props = None
		# start waiting for data
		self.idlequeue.plug_idle(self, False, True)
	
	def read_timeout(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state > 5:
			# no activity for foo seconds
			if self.file_props['stalled'] == False:
				self.file_props['stalled'] = True
				self.queue.process_result(-1, self)
				if SEND_TIMEOUT > 0:
					self.idlequeue.set_read_timeout(self.fd, SEND_TIMEOUT)
			else:
				# stop transfer, there is no error code for this 
				self.pollend()
	
	def pollout(self):
		if not self.connected:
			self.disconnect()
			return
		self.idlequeue.remove_timeout(self.fd)
		if self.state == 2: # send reply with desired auth type
			self.send_raw(self._get_auth_response())
		elif self.state == 4: # send positive response to the 'connect'
			self.send_raw(self._get_request_buff(self.sha_msg, 0x00))
		elif self.state == 7:
			if self.file_props['paused']:
				self.file_props['continue_cb'] = self.continue_paused_transfer
				self.idlequeue.plug_idle(self, False, False)
				return 
			result = self.write_next()
			self.queue.process_result(result, self)
			if result is None or result <= 0:
				self.disconnect()
				return
			self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
		elif self.state == 8:
			self.disconnect()
			return
		else:
			self.disconnect()
		if self.state < 5:
			self.state += 1
			# unplug and plug this time for reading
			self.idlequeue.plug_idle(self, False, True)
	
	def pollend(self):
		self.state = 8 # end connection
		self.disconnect()
		self.file_props['error'] = -1
		self.queue.process_result(-1, self)
	
	def pollin(self):
		if self.connected:
			if self.state < 5:
				result = self.main()
				if self.state == 4:
					self.queue.result_sha(self.sha_msg, self.queue_idx)
				if result == -1:
					self.disconnect()
			
			elif self.state == 5:
				if self.file_props is not None and \
				self.file_props['type'] == 'r':
					result = self.get_file_contents(0)
					self.queue.process_result(result, self)
		else:
			self.disconnect()
	
	def send_file(self):
		''' start sending the file over verified connection ''' 
		if self.file_props['started']:
			return
		self.file_props['error'] = 0
		self.file_props['disconnect_cb'] = self.disconnect
		self.file_props['started'] = True
		self.file_props['completed'] = False
		self.file_props['paused'] = False
		self.file_props['continue_cb'] = self.continue_paused_transfer
		self.file_props['stalled'] = False
		self.file_props['connected'] = True
		self.file_props['elapsed-time'] = 0
		self.file_props['last-time'] = self.idlequeue.current_time()
		self.file_props['received-len'] = 0
		self.pauses = 0
		self.state = 7
		# plug for writing
		self.idlequeue.plug_idle(self, True, False)
		return self.write_next() # initial for nl byte
		
	def main(self):
		''' initial requests for verifying the connection '''
		if self.state == 1: # initial read
			buff = self.receive()
			if not self.connected:
				return -1
			mechs = self._parse_auth_buff(buff)
			if mechs is None:
				return -1 # invalid auth methods received
		elif self.state == 3: # get next request
			buff = self.receive()
			(req_type, self.sha_msg, port) = self._parse_request_buff(buff)
			if req_type != 0x01:
				return -1 # request is not of type 'connect'
		self.state += 1 # go to the next step
		# unplug & plug for writing
		self.idlequeue.plug_idle(self, True, False)
		return None
			
	def disconnect(self, cb = True):
		''' Closes the socket. '''
		# close connection and remove us from the queue
		Socks5.disconnect(self)
		if self.file_props is not None:
			self.file_props['connected'] = False
			self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_sender(self.queue_idx, False)

class Socks5Listener(IdleObject):
	def __init__(self, idlequeue, port):
		''' handle all incomming connections on (0.0.0.0, port) 
		This class implements IdleObject, but we will expect
		only pollin events though
		'''
		self.port = port
		self.queue_idx = -1	
		self.idlequeue = idlequeue
		self.queue = None
		self.started = False
		self._sock = None
		self.fd = -1
		
	def bind(self):
		self._serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		# will fail when port as busy, or we don't have rights to bind
		try:
			self._serv.bind(('0.0.0.0', self.port))
		except Exception, e:
			# unable to bind, show error dialog
			return None
		self._serv.listen(socket.SOMAXCONN)
		self._serv.setblocking(False)
		self.fd = self._serv.fileno()
		self.idlequeue.plug_idle(self, False, True)
		self.started = True
	
	def pollend(self):
		''' called when we stop listening on (host, port) '''
		self.disconnect()
	
	def pollin(self):
		''' accept a new incomming connection and notify queue'''
		sock = self.accept_conn()
		self.queue.on_connection_accepted(sock)
	
	def disconnect(self):
		''' free all resources, we are not listening anymore '''
		self.idlequeue.remove_timeout(self.fd)
		self.idlequeue.unplug_idle(self.fd)
		self.fd = -1
		self.state = -1
		self.started = False
		try:
			self._serv.close()
		except:
			pass
	
	def accept_conn(self):
		''' accepts a new incomming connection '''
		_sock  = self._serv.accept()
		_sock[0].setblocking(False)
		return _sock
	
class Socks5Receiver(Socks5, IdleObject):
	def __init__(self, idlequeue, streamhost, sid, file_props = None):
		self.queue_idx = -1
		self.streamhost = streamhost
		self.queue = None
		self.file_props = file_props
		self.connect_timeout = 0
		self.connected = False
		self.pauses = 0
		if not self.file_props:
			self.file_props = {}
		self.file_props['disconnect_cb'] = self.disconnect
		self.file_props['error'] = 0
		self.file_props['started'] = True
		self.file_props['completed'] = False
		self.file_props['paused'] = False
		self.file_props['continue_cb'] = self.continue_paused_transfer
		self.file_props['stalled'] = False
		Socks5.__init__(self, idlequeue, streamhost['host'], int(streamhost['port']), 
			streamhost['initiator'], streamhost['target'], sid)
	
	def read_timeout(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state > 5:
			# no activity for foo seconds
			if self.file_props['stalled'] == False:
				self.file_props['stalled'] = True
				if not self.file_props.has_key('received-len'):
					self.file_props['received-len'] = 0
				self.queue.process_result(-1, self)
				if READ_TIMEOUT > 0:
					self.idlequeue.set_read_timeout(self.fd, READ_TIMEOUT)
			else:
				# stop transfer, there is no error code for this 
				self.pollend()
		else:
			self.queue.reconnect_receiver(self, self.streamhost)
	
	def connect(self):
		''' create the socket and plug it to the idlequeue '''
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# this will not block the GUI
		self._sock.setblocking(False)
		self.fd = self._sock.fileno()
		self.state = 0 # about to be connected
		self.idlequeue.plug_idle(self, True, False)
		self.do_connect()
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
		return None
	
	def _is_connected(self):
		if self.state < 5:
			return False
		return True
	def pollout(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state == 0:
			self.do_connect()
			return
		elif self.state == 1: # send initially: version and auth types
			self.send_raw(self._get_auth_buff())
		elif self.state == 3: # send 'connect' request
			self.send_raw(self._get_request_buff(self._get_sha1_auth()))
		elif self.file_props['type'] != 'r':
			if self.file_props['paused'] == True:
				self.idlequeue.plug_idle(self, False, False)
				return
			result = self.write_next()
			self.queue.process_result(result, self)
			return
		self.state += 1
		# unplug and plug for reading
		self.idlequeue.plug_idle(self, False, True)
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
	
	def pollend(self):
		if self.state >= 5:
			# error during transfer
			self.disconnect()
			self.file_props['error'] = -1
			self.queue.process_result(-1, self)
		else:
			self.queue.reconnect_receiver(self, self.streamhost)
	
	def pollin(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.connected:
			if self.file_props['paused']:
				self.idlequeue.plug_idle(self, False, False)
				return
			if self.state < 5:
				self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
				result = self.main(0)
				self.queue.process_result(result, self)
			elif self.state == 5: # wait for proxy reply
				pass
			elif self.file_props['type'] == 'r':
				self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
				result = self.get_file_contents(0)
				self.queue.process_result(result, self)
				
		else:
			self.disconnect()
	
	def do_connect(self):
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		except Exception, ee:
			(errnum, errstr) = ee
			self.connect_timeout += 1
			if errnum == 111 or self.connect_timeout > 1000:
				self.queue._connection_refused(self.streamhost, 
					self.file_props, self.queue_idx)
				return None
			# win32 needs this
			elif errnum not in  (10056, EISCONN) or self.state != 0:
				return None
			else: # socket is already connected
				self._sock.setblocking(False)
				self._send=self._sock.send
				self._recv=self._sock.recv
		self.buff = ''
		self.connected = True
		self.file_props['connected'] = True
		self.file_props['disconnect_cb'] = self.disconnect
		self.state = 1 # connected
		
		# stop all others connections to sender's streamhosts
		self.queue._socket_connected(self.streamhost, self.file_props)
		self.idlequeue.plug_idle(self, True, False)
		return 1 # we are connected
		
	def main(self, timeout = 0):
		''' begin negotiation. on success 'address' != 0 '''
		result = 1
		buff = self.receive()
		if buff == '':
			# end connection
			self.pollend()
			return
		
		if self.state == 2: # read auth response
			if buff is None or len(buff) != 2:
				return None
			version, method = struct.unpack('!BB', buff[:2])
			if version != 0x05 or method == 0xff:
				self.disconnect()
		elif self.state == 4: # get approve of our request
			if buff == None:
				return None
			sub_buff = buff[:4]
			if len(sub_buff) < 4:
				return None
			version, command, rsvd, address_type = struct.unpack('!BBBB', buff[:4])
			addrlen, address, port = 0, 0, 0
			if address_type == 0x03:
				addrlen = ord(buff[4])
				address = struct.unpack('!%ds' % addrlen, buff[5:addrlen + 5])
				portlen = len(buff[addrlen + 5:])
				if portlen == 1: 
					port, = struct.unpack('!B', buff[addrlen + 5])
				elif portlen == 2:
					port, = struct.unpack('!H', buff[addrlen + 5:])
				else: # Gaim bug :)
					port, = struct.unpack('!H', buff[addrlen + 5:addrlen + 7])
					self.remaining_buff = buff[addrlen + 7:]
			self.state = 5 # for senders: init file_props and send '\n'
			if self.queue.on_success:
				result = self.queue.send_success_reply(self.file_props, 
					self.streamhost)
				if result == 0:
					self.state = 8
					self.disconnect()
		
		# for senders: init file_props 
		if result == 1 and self.state == 5: 
			if self.file_props['type'] == 's':
				self.file_props['error'] = 0
				self.file_props['disconnect_cb'] = self.disconnect
				self.file_props['started'] = True
				self.file_props['completed'] = False
				self.file_props['paused'] = False
				self.file_props['stalled'] = False
				self.file_props['elapsed-time'] = 0
				self.file_props['last-time'] = self.idlequeue.current_time()
				self.file_props['received-len'] = 0
				self.pauses = 0
				# start sending file contents to socket
				self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
				self.idlequeue.plug_idle(self, True, False)
			else:
				# receiving file contents from socket
				self.idlequeue.plug_idle(self, False, True)
			self.file_props['continue_cb'] = self.continue_paused_transfer
			# we have set up the connection, next - retrieve file
			self.state = 6 
		if self.state < 5:
			self.idlequeue.plug_idle(self, True, False)
			self.state += 1
			return None
	
	def disconnect(self, cb = True):
		''' Closes the socket. Remove self from queue if cb is True'''
		# close connection 
		Socks5.disconnect(self)
		if cb is True:
			self.file_props['disconnect_cb'] = None
		if self.queue is not None:
			self.queue.remove_receiver(self.queue_idx, False)
