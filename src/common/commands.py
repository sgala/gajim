##
## Copyright (C) 2006 Gajim Team
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

import xmpp
import helpers
import dataforms
import gajim

class AdHocCommand:
	commandnode = 'command'
	commandname = 'The Command'
	commandfeatures = (xmpp.NS_DATA,)

	@staticmethod
	def isVisibleFor(samejid):
		''' This returns True if that command should be visible and invokable
		for others.
		samejid - True when command is invoked by an entity with the same bare jid.
		'''
		return True

	def __init__(self, conn, jid, sessionid):
		self.connection = conn
		self.jid = jid
		self.sessionid = sessionid

	def buildResponse(self, request, status='executing', defaultaction=None, actions=None):
		assert status in ('executing', 'completed', 'canceled')

		response = request.buildReply('result')
		cmd = response.addChild('command', {
			'xmlns': xmpp.NS_COMMANDS,
			'sessionid': self.sessionid,
			'node': self.commandnode,
			'status': status})
		if defaultaction is not None or actions is not None:
			if defaultaction is not None:
				assert defaultaction in ('cancel', 'execute', 'prev', 'next', 'complete')
				attrs = {'action': defaultaction}
			else:
				attrs = {}

			cmd.addChild('actions', attrs, actions)
		return response, cmd

	def badRequest(self, stanza):
		self.connection.connection.send(xmpp.Error(stanza, xmpp.NS_STANZAS+' bad-request'))

	def cancel(self, request):
		response, cmd = self.buildResponse(request, status='canceled')
		self.connection.connection.send(response)
		return False	# finish the session

class ChangeStatusCommand(AdHocCommand):
	commandnode = 'change-status'
	commandname = 'Change status information'

	@staticmethod
	def isVisibleFor(samejid):
		''' Change status is visible only if the entity has the same bare jid. '''
		return samejid

	def execute(self, request):
		# first query...
		response, cmd = self.buildResponse(request, defaultaction='execute', actions=['execute'])
		
		cmd.addChild(node=dataforms.SimpleDataForm(
			title='Change status',
			instructions='Set the presence type and description',
			fields=[
				dataforms.Field('list-single',
					var='presence-type',
					label='Type of presence:',
					options=[
						(u'free-for-chat', u'Free for chat'),
						(u'online', u'Online'),
						(u'away', u'Away'),
						(u'xa', u'Extended away'),
						(u'dnd', u'Do not disturb'),
						(u'offline', u'Offline - disconnect')],
					value='online',
					required=True),
				dataforms.Field('text-multi',
					var='presence-desc',
					label='Presence description:')]))

		self.connection.connection.send(response)

		# for next invocation
		self.execute = self.changestatus
		
		return True	# keep the session

	def changestatus(self, request):
		# check if the data is correct
		try:
			form=dataforms.SimpleDataForm(extend=request.getTag('command').getTag('x'))
		except:
			self.badRequest(request)
			return False
		
		try:
			presencetype = form['presence-type'].value
			if not presencetype in \
			    ('free-for-chat', 'online', 'away', 'xa', 'dnd', 'offline'):
				self.badRequest(request)
				return False
		except:	# KeyError if there's no presence-type field in form or
			# AttributeError if that field is of wrong type
			self.badRequest(request)
			return False

		try:
			presencedesc = form['presence-desc'].value
		except:	# same exceptions as in last comment
			presencedesc = u''

		response, cmd = self.buildResponse(request, status='completed')
		cmd.addChild('note', {}, 'The status has been changed.')

		self.connection.connection.send(response)

		# send new status
		gajim.interface.roster.send_status(self.connection.name, presencetype, presencedesc)

		return False	# finish the session

class ConnectionCommands:
	''' This class depends on that it is a part of Connection() class. '''
	def __init__(self):
		# a list of all commands exposed: node -> command class
		self.__commands = {}
		for cmdobj in (ChangeStatusCommand,):
			self.__commands[cmdobj.commandnode] = cmdobj

		# a list of sessions; keys are tuples (jid, sessionid, node)
		self.__sessions = {}

	def getOurBareJID(self):
		return gajim.get_jid_from_account(self.name)

	def isSameJID(self, jid):
		''' Tests if the bare jid given is the same as our bare jid. '''
		return xmpp.JID(jid).getStripped() == self.getOurBareJID()

	def commandListQuery(self, con, iq_obj):
		iq = iq_obj.buildReply('result')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		q = iq.getTag('query')

		for node, cmd in self.__commands.iteritems():
			if cmd.isVisibleFor(self.isSameJID(jid)):
				q.addChild('item', {
					# TODO: find the jid
					'jid': self.getOurBareJID()+u'/'+self.server_resource,
					'node': node,
					'name': cmd.commandname})

		self.connection.send(iq)

	def commandQuery(self, con, iq_obj):
		''' Send disco result for query for command (JEP-0050, example 6.).
		Return True if the result was sent, False if not. '''
		jid = helpers.get_full_jid_from_iq(iq_obj)
		node = iq_obj.getTagAttr('query', 'node')

		if node not in self.__commands: return False

		cmd = self.__commands[node]
		if cmd.isVisibleFor(self.isSameJID(jid)):
			iq = iq_obj.buildReply('result')
			q = iq.getTag('query')
			q.addChild('identity', attrs = {'type': 'command-node',
			                                'category': 'automation',
			                                'name': cmd.commandname})
			q.addChild('feature', attrs = {'var': xmpp.NS_COMMANDS})
			for feature in cmd.commandfeatures:
				q.addChild('feature', attrs = {'var': feature})

			self.connection.send(iq)
			return True

		return False

	def _CommandExecuteCB(self, con, iq_obj):
		jid = helpers.get_full_jid_from_iq(iq_obj)

		cmd = iq_obj.getTag('command')
		if cmd is None: return

		node = cmd.getAttr('node')
		if node is None: return

		sessionid = cmd.getAttr('sessionid')
		if sessionid is None:
			# we start a new command session... only if we are visible for the jid
			# and command exist
			if node not in self.__commands.keys():
				self.connection.send(
					xmpp.Error(iq_obj, xmpp.NS_STANZAS+' item-not-found'))
				raise xmpp.NodeProcessed

			newcmd = self.__commands[node]
			if not newcmd.isVisibleFor(self.isSameJID(jid)):
				return

			# generate new sessionid
			sessionid = self.connection.getAnID()

			# create new instance and run it
			obj = newcmd(conn=self, jid=jid, sessionid=sessionid)
			rc = obj.execute(iq_obj)
			if rc:
				self.__sessions[(jid, sessionid, node)] = obj
			raise xmpp.NodeProcessed
		else:
			# the command is already running, check for it
			magictuple = (jid, sessionid, node)
			if magictuple not in self.__sessions:
				# we don't have this session... ha!
				return

			action = cmd.getAttr('action')
			obj = self.__sessions[magictuple]

			try:
				if action == 'cancel':		rc = obj.cancel(iq_obj)
				elif action == 'prev':		rc = obj.prev(iq_obj)
				elif action == 'next':		rc = obj.next(iq_obj)
				elif action == 'execute' or action is None:
								rc = obj.execute(iq_obj)
				elif action == 'complete':	rc = obj.complete(iq_obj)
				else:
					# action is wrong. stop the session, send error
					raise AttributeError
			except AttributeError:
				# the command probably doesn't handle invoked action...
				# stop the session, return error
				del self.__sessions[magictuple]
				return

			# delete the session if rc is False
			if not rc:
				del self.__sessions[magictuple]

			raise xmpp.NodeProcessed
