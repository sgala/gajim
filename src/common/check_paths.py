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

import os
import sys
import stat

from common import gajim
import logger

# DO NOT MOVE ABOVE OF import gajim
try:
	import sqlite3 as sqlite # python 2.5
except ImportError:
	try:
		from pysqlite2 import dbapi2 as sqlite
	except ImportError:
		raise exceptions.PysqliteNotAvailable

def create_log_db():
	print _('creating logs database')
	con = sqlite.connect(logger.LOG_DB_PATH) 
	os.chmod(logger.LOG_DB_PATH, 0600) # rw only for us
	cur = con.cursor()
	# create the tables
	# kind can be
	# status, gcstatus, gc_msg, (we only recv for those 3),
	# single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
	# to meet all our needs
	# logs.jid_id --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
	# jids.jid text column will be JID if TC-related, room_jid if GC-related,
	# ROOM_JID/nick if pm-related.
	# also check optparser.py, which updates databases on gajim updates
	cur.executescript(
		'''
		CREATE TABLE jids(
			jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
			jid TEXT UNIQUE,
			type INTEGER
		);
		
		CREATE TABLE unread_messages(
			message_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
			jid_id INTEGER
		);
		
		CREATE INDEX idx_unread_messages_jid_id ON unread_messages (jid_id);
		
		CREATE TABLE transports_cache (
			transport TEXT UNIQUE,
			type INTEGER
		);
		
		CREATE TABLE logs(
			log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
			jid_id INTEGER,
			contact_name TEXT,
			time INTEGER,
			kind INTEGER,
			show INTEGER,
			message TEXT,
			subject TEXT
		);
		
		CREATE INDEX idx_logs_jid_id_kind ON logs (jid_id, kind);

		CREATE TABLE caps_cache (
			node TEXT,
			ver TEXT,
			ext TEXT,
			data BLOB);
		'''
		)

	con.commit()
	con.close()

def check_and_possibly_create_paths():
	LOG_DB_PATH = logger.LOG_DB_PATH
	VCARD_PATH = gajim.VCARD_PATH
	AVATAR_PATH = gajim.AVATAR_PATH
	dot_gajim = os.path.dirname(VCARD_PATH)
	if os.path.isfile(dot_gajim):
		print _('%s is a file but it should be a directory') % dot_gajim
		print _('Gajim will now exit')
		sys.exit()
	elif os.path.isdir(dot_gajim):
		s = os.stat(dot_gajim)
		if s.st_mode & stat.S_IROTH: # others have read permission!
			os.chmod(dot_gajim, 0700) # rwx------

		if not os.path.exists(VCARD_PATH):
			create_path(VCARD_PATH)
		elif os.path.isfile(VCARD_PATH):
			print _('%s is a file but it should be a directory') % VCARD_PATH
			print _('Gajim will now exit')
			sys.exit()

		if not os.path.exists(AVATAR_PATH):
			create_path(AVATAR_PATH)
		elif os.path.isfile(AVATAR_PATH):
			print _('%s is a file but it should be a directory') % AVATAR_PATH
			print _('Gajim will now exit')
			sys.exit()

		if not os.path.exists(LOG_DB_PATH):
			create_log_db()
			gajim.logger.init_vars()
		elif os.path.isdir(LOG_DB_PATH):
			print _('%s is a directory but should be a file') % LOG_DB_PATH
			print _('Gajim will now exit')
			sys.exit()

	else: # dot_gajim doesn't exist
		if dot_gajim: # is '' on win9x so avoid that
			create_path(dot_gajim)
		if not os.path.isdir(VCARD_PATH):
			create_path(VCARD_PATH)
		if not os.path.exists(AVATAR_PATH):
			create_path(AVATAR_PATH)
		if not os.path.isfile(LOG_DB_PATH):
			create_log_db()
			gajim.logger.init_vars()

def create_path(directory):
	print _('creating %s directory') % directory
	os.mkdir(directory, 0700)
