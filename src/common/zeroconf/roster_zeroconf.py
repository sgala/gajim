##      common/zeroconf/roster_zeroconf.py
##
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


from common.zeroconf import zeroconf

class Roster:
	def __init__(self, zeroconf):
		self._data = None
		self.zeroconf = zeroconf 	  	 # our zeroconf instance

	def update_roster(self):
		for val in self.zeroconf.contacts.values():
			self.setItem(val[zeroconf.C_NAME])

	def getRoster(self):
		#print 'roster_zeroconf.py: getRoster'
		if self._data is None:
			self._data = {}
			self.update_roster()
		return self

	def getDiffs(self):
		'''	update the roster with new data and return dict with
		jid -> new status pairs to do notifications and stuff '''

		diffs = {}
		old_data = self._data.copy()
		self.update_roster()
		for key in old_data.keys():
			if self._data.has_key(key):
				if old_data[key] != self._data[key]:
					diffs[key] = self._data[key]['status']
		#print 'roster_zeroconf.py: diffs:' + str(diffs)
		return diffs
		
	def setItem(self, jid, name = '', groups = ''):
		#print 'roster_zeroconf.py: setItem %s' % jid
		contact = self.zeroconf.get_contact(jid)
		if not contact:
			return

		(service_jid, domain, interface, protocol, host, address, port, bare_jid, txt)  \
			= contact

		self._data[jid]={}
		self._data[jid]['ask'] = 'no'  #?
		self._data[jid]['subscription'] = 'both'
		self._data[jid]['groups'] = []
		self._data[jid]['resources'] = {}
		self._data[jid]['address'] = address
		self._data[jid]['host'] = host
		self._data[jid]['port'] = port
		txt_dict = self.zeroconf.txt_array_to_dict(txt)
		if txt_dict.has_key('status'):
			status = txt_dict['status']
		else:
			status = ''
		if not status:
			status = 'avail'
		nm = ''
		if txt_dict.has_key('1st'):
			nm = txt_dict['1st']
		if txt_dict.has_key('last'):
			if nm != '':
				nm += ' '
			nm += txt_dict['last']
		if nm:
			self._data[jid]['name'] = nm
		else:
			self._data[jid]['name'] = jid
		if status == 'avail': 
			status = 'online'
		self._data[jid]['txt_dict'] = txt_dict
		if not self._data[jid]['txt_dict'].has_key('msg'):
			self._data[jid]['txt_dict']['msg'] = ''
		self._data[jid]['status'] = status
		self._data[jid]['show'] = status

	def delItem(self, jid):
		#print 'roster_zeroconf.py: delItem %s' % jid
		if self._data.has_key(jid):
			del self._data[jid]
		
	def getItem(self, jid):
		#print 'roster_zeroconf.py: getItem: %s' % jid
		if self._data.has_key(jid):
			return self._data[jid]

	def __getitem__(self,jid):
		#print 'roster_zeroconf.py: __getitem__'
		return self._data[jid]
	
	def getItems(self):
		#print 'roster_zeroconf.py: getItems'
		# Return list of all [bare] JIDs that the roster currently tracks.
		return self._data.keys()
	
	def keys(self):
		#print 'roster_zeroconf.py: keys'
		return self._data.keys()
	
	def getRaw(self):
		#print 'roster_zeroconf.py: getRaw'
		return self._data

	def getResources(self, jid):
		#print 'roster_zeroconf.py: getResources(%s)' % jid
		return {}
		
	def getGroups(self, jid):
		return self._data[jid]['groups']

	def getName(self, jid):
		if self._data.has_key(jid):
			return self._data[jid]['name']

	def getStatus(self, jid):
		if self._data.has_key(jid):
			return self._data[jid]['status']

	def getMessage(self, jid):
		if self._data.has_key(jid):
			return self._data[jid]['txt_dict']['msg']

	def getShow(self, jid):
		#print 'roster_zeroconf.py: getShow'
		return self.getStatus(jid)

	def getPriority(jid):
		return 5

	def getSubscription(self,jid):
		#print 'roster_zeroconf.py: getSubscription'
		return 'both'

	def Subscribe(self,jid):
		pass
		
	def Unsubscribe(self,jid):
		pass
	
	def Authorize(self,jid):
		pass

	def Unauthorize(self,jid):
		pass
