## common/sleepy.py
##
## Contributors for this file:
##      - Yann Le Boulanger <asterix@lagaule.org>
##      - Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
##                    Nikos Kouremenos <kourem@gmail.com>
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

from common import gajim
import os


STATE_UNKNOWN  = 'OS probably not supported'
STATE_XA   = 'extended away'
STATE_AWAY   = 'away'
STATE_AWAKE    = 'awake'

SUPPORTED = True
try:
        if os.name == 'nt':
                import ctypes

                GetTickCount = ctypes.windll.kernel32.GetTickCount
                GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo

                class LASTINPUTINFO(ctypes.Structure):
                        _fields_ = [('cbSize', ctypes.c_uint),
                            ('dwTime', ctypes.c_uint)]

                lastInputInfo = LASTINPUTINFO()
                lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)

        else: # unix
        	import idle
except:
	gajim.log.debug('Unable to load idle module')
	SUPPORTED = False

class SleepyWindows:
        def __init__(self, away_interval = 60, xa_interval = 120):
		self.away_interval = away_interval
		self.xa_interval = xa_interval
		self.state = STATE_AWAKE # assume we are awake

        def getIdleSec(self):
                GetLastInputInfo(ctypes.byref(lastInputInfo))
                idleDelta = float(GetTickCount() - lastInputInfo.dwTime) / 1000
                return idleDelta

	def poll(self):
		'''checks to see if we should change state'''
		idleTime = self.getIdleSec()
		
		# xa is stronger than away so check for xa first
		if idleTime > self.xa_interval:
			self.state = STATE_XA
		elif idleTime > self.away_interval:
			self.state = STATE_AWAY
		else:
			self.state = STATE_AWAKE
		return True

	def getState(self):
		return self.state

	def setState(self, val):
		self.state = val

class SleepyUnix:

	def __init__(self, away_interval = 60, xa_interval = 120):
		self.away_interval = away_interval
		self.xa_interval = xa_interval
		self.state = STATE_AWAKE # assume we are awake
		try:
			idle.init()
		except:
			SUPPORTED = False
			self.state = STATE_UNKNOWN

        def getIdleSec(self):
                return idle.getIdleSec()

	def poll(self):
		'''checks to see if we should change state'''
		if not SUPPORTED:
			return False

		idleTime = self.getIdleSec()
		
		# xa is stronger than away so check for xa first
		if idleTime > self.xa_interval:
			self.state = STATE_XA
		elif idleTime > self.away_interval:
			self.state = STATE_AWAY
		else:
			self.state = STATE_AWAKE
		return True

	def getState(self):
		return self.state

	def setState(self, val):
		self.state = val

if os.name == 'nt':
        Sleepy = SleepyWindows
else:
        Sleepy = SleepyUnix
