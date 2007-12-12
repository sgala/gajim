from common import gajim

from common import xmpp
from common import helpers
from common import exceptions

import random
import string

import time

import xmpp.c14n

import base64

XmlDsig = 'http://www.w3.org/2000/09/xmldsig#'

class StanzaSession(object):
	def __init__(self, conn, jid, thread_id, type):
		self.conn = conn

		self.jid = jid

		self.type = type

		if thread_id:
			self.received_thread_id = True
			self.thread_id = thread_id
		else:
			self.received_thread_id = False
			if type == 'normal':
				self.thread_id = None
			else:
				self.thread_id = self.generate_thread_id()

		self.last_send = 0
		self.status = None
		self.negotiated = {}

	def generate_thread_id(self):
		return "".join([random.choice(string.ascii_letters) for x in xrange(0,32)])

	def send(self, msg):
		if self.thread_id:
			msg.NT.thread = self.thread_id

		msg.setAttr('to', self.jid)
		self.conn.send_stanza(msg)

		if isinstance(msg, xmpp.Message):
			self.last_send = time.time()

	def reject_negotiation(self, body = None):
		msg = xmpp.Message()
		feature = msg.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')
		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='accept', value='0'))

		feature.addChild(node=x)

		if body:
			msg.setBody(body)

		self.send(msg)

		self.cancelled_negotiation()

	def cancelled_negotiation(self):
		'''A negotiation has been cancelled, so reset this session to its default state.'''

		if hasattr(self, 'control'):
			self.control.on_cancel_session_negotiation()

		self.status = None
		self.negotiated = {}

	def terminate(self):
		msg = xmpp.Message()
		feature = msg.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')
		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='terminate', value='1'))

		feature.addChild(node=x)

		self.send(msg)

		self.status = None

	def acknowledge_termination(self):
		# we could send an acknowledgement message to the remote client here
		self.status = None

if gajim.HAVE_PYCRYPTO:
	from Crypto.Cipher import AES
	from Crypto.Hash import HMAC, SHA256
	from Crypto.PublicKey import RSA
	from common import crypto

	from common import dh
	import secrets

# an encrypted stanza negotiation has several states. i've represented them
# as the following values in the 'status'
# attribute of the session object:

# 1. None:
#				default state
# 2. 'requested-e2e':
#				this client has initiated an esession negotiation and is waiting
#				for a response
# 3. 'responded-e2e':
#				this client has responded to an esession negotiation request and
#				is waiting for the initiator to identify itself and complete the
#				negotiation
# 4. 'identified-alice':
#				this client identified itself and is waiting for the responder to
#				identify itself and complete the negotiation
# 5. 'active':
#				an encrypted session has been successfully negotiated. messages
#				of any of the types listed in 'encryptable_stanzas' should be
#				encrypted before they're sent.

# the transition between these states is handled in gajim.py's
#	handle_session_negotiation method.

class EncryptedStanzaSession(StanzaSession):
	def __init__(self, conn, jid, thread_id, type = 'chat'):
		StanzaSession.__init__(self, conn, jid, thread_id, type = 'chat')

		self.loggable = True

		self.xes = {}
		self.es = {}

		self.n = 128

		self.enable_encryption = False

		# _s denotes 'self' (ie. this client)
		self._kc_s = None

		# _o denotes 'other' (ie. the client at the other end of the session)
		self._kc_o = None

	# keep the encrypter updated with my latest cipher key
	def set_kc_s(self, value):
		self._kc_s = value
		self.encrypter = self.cipher.new(self._kc_s, self.cipher.MODE_CTR,
			counter=self.encryptcounter)

	def get_kc_s(self):
		return self._kc_s

	# keep the decrypter updated with the other party's latest cipher key
	def set_kc_o(self, value):
		self._kc_o = value
		self.decrypter = self.cipher.new(self._kc_o, self.cipher.MODE_CTR,
			counter=self.decryptcounter)

	def get_kc_o(self):
		return self._kc_o

	kc_s = property(get_kc_s, set_kc_s)
	kc_o = property(get_kc_o, set_kc_o)

	def encryptcounter(self):
		self.c_s = (self.c_s + 1) % (2 ** self.n)
		return crypto.encode_mpi_with_padding(self.c_s)

	def decryptcounter(self):
		self.c_o = (self.c_o + 1) % (2 ** self.n)
		return crypto.encode_mpi_with_padding(self.c_o)

	def sign(self, string):
		if self.negotiated['sign_algs'] == (XmlDsig + 'rsa-sha256'):
			hash = crypto.sha256(string)
			return crypto.encode_mpi(gajim.pubkey.sign(hash, '')[0])

	def encrypt_stanza(self, stanza):
		encryptable = filter(lambda x: x.getName() not in ('error', 'amp',
			'thread'), stanza.getChildren())

		# XXX can also encrypt contents of <error/> elements in stanzas @type =
		# 'error'
		# (except for <defined-condition
		# xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/> child elements)

		old_en_counter = self.c_s

		for element in encryptable:
			stanza.delChild(element)

		plaintext = ''.join(map(str, encryptable))

		m_compressed = self.compress(plaintext)
		m_final = self.encrypt(m_compressed)

		c = stanza.NT.c
		c.setNamespace('http://www.xmpp.org/extensions/xep-0200.html#ns')
		c.NT.data = base64.b64encode(m_final)

		# XXX check for rekey request, handle <key/> elements

		m_content = ''.join(map(str, c.getChildren()))
		c.NT.mac = base64.b64encode(self.hmac(self.km_s, m_content + \
			crypto.encode_mpi(old_en_counter)))

		return stanza

	def hmac(self, key, content):
		return HMAC.new(key, content, self.hash_alg).digest()

	def generate_initiator_keys(self, k):
		return (self.hmac(k, 'Initiator Cipher Key'),
						self.hmac(k, 'Initiator MAC Key'),
						self.hmac(k, 'Initiator SIGMA Key')		 )

	def generate_responder_keys(self, k):
		return (self.hmac(k, 'Responder Cipher Key'),
						self.hmac(k, 'Responder MAC Key'),
						self.hmac(k, 'Responder SIGMA Key')		)

	def compress(self, plaintext):
		if self.compression == None:
			return plaintext

	def decompress(self, compressed):
		if self.compression == None:
			return compressed

	def encrypt(self, encryptable):
		padded = crypto.pad_to_multiple(encryptable, 16, ' ', False)

		return self.encrypter.encrypt(padded)

	def decrypt_stanza(self, stanza):
		c = stanza.getTag(name='c',
			namespace='http://www.xmpp.org/extensions/xep-0200.html#ns')

		stanza.delChild(c)

		# contents of <c>, minus <mac>, minus whitespace
		macable = ''.join(map(str, filter(lambda x: x.getName() != 'mac',
			c.getChildren())))

		received_mac = base64.b64decode(c.getTagData('mac'))
		calculated_mac = self.hmac(self.km_o, macable + \
			crypto.encode_mpi_with_padding(self.c_o))

		if not calculated_mac == received_mac:
			raise exceptions.DecryptionError, 'bad signature'

		m_final = base64.b64decode(c.getTagData('data'))
		m_compressed = self.decrypt(m_final)
		plaintext = self.decompress(m_compressed)

		try:
			parsed = xmpp.Node(node='<node>' + plaintext + '</node>')
		except:
			raise exceptions.DecryptionError, 'decrypted <data/> not parseable as XML'

		for child in parsed.getChildren():
			stanza.addChild(node=child)

		return stanza

	def decrypt(self, ciphertext):
		return self.decrypter.decrypt(ciphertext)

	def logging_preference(self):
		if gajim.config.get('log_encrypted_sessions'):
			return ["may", "mustnot"]
		else:
			return ["mustnot", "may"]

	def get_shared_secret(self, e, y, p):
		if (not 1 < e < (p - 1)):
			raise exceptions.NegotiationError, "invalid DH value"

		return crypto.sha256(crypto.encode_mpi(crypto.powmod(e, y, p)))

	def c7lize_mac_id(self, form):
		kids = form.getChildren()
		macable = filter(lambda x: x.getVar() not in ('mac', 'identity'), kids)
		return ''.join(map(lambda el: xmpp.c14n.c14n(el), macable))

	def verify_identity(self, form, dh_i, sigmai, i_o):
		m_o = base64.b64decode(form['mac'])
		id_o = base64.b64decode(form['identity'])

		m_o_calculated = self.hmac(self.km_o, crypto.encode_mpi(self.c_o) + id_o)

		if m_o_calculated != m_o:
			raise exceptions.NegotiationError, 'calculated m_%s differs from received m_%s' % (i_o, i_o)

		if i_o == 'a' and self.sas_algs == 'sas28x5':
			# XXX not necessary if there's a verified retained secret
			self.sas = crypto.sas_28x5(m_o, self.form_s)

		if self.negotiated['recv_pubkey']:
			plaintext = self.decrypt(id_o)
			parsed = xmpp.Node(node='<node>' + plaintext + '</node>')

			if self.negotiated['recv_pubkey'] == 'hash':
				fingerprint = parsed.getTagData('fingerprint')

				# XXX find stored pubkey or terminate session
				raise 'unimplemented'
			else:
				if self.negotiated['sign_algs'] == (XmlDsig + 'rsa-sha256'):
					keyvalue = parsed.getTag(name='RSAKeyValue', namespace=XmlDsig)

					n, e = map(lambda x: crypto.decode_mpi(base64.b64decode(
						keyvalue.getTagData(x))), ('Modulus', 'Exponent'))
					eir_pubkey = RSA.construct((n,long(e)))

					pubkey_o = xmpp.c14n.c14n(keyvalue)
				else:
					# XXX DSA, etc.
					raise 'unimplemented'

			enc_sig = parsed.getTag(name='SignatureValue',
				namespace=XmlDsig).getData()
			signature = (crypto.decode_mpi(base64.b64decode(enc_sig)),)
		else:
			mac_o = self.decrypt(id_o)
			pubkey_o = ''

		c7l_form = self.c7lize_mac_id(form)

		content = self.n_s + self.n_o + crypto.encode_mpi(dh_i) + pubkey_o

		if sigmai:
			self.form_o = c7l_form
			content += self.form_o
		else:
			form_o2 = c7l_form
			content += self.form_o + form_o2

		mac_o_calculated = self.hmac(self.ks_o, content)

		if self.negotiated['recv_pubkey']:
			hash = crypto.sha256(mac_o_calculated)

			if not eir_pubkey.verify(hash, signature):
				raise exceptions.NegotiationError, 'public key signature verification failed!'

		elif mac_o_calculated != mac_o:
			raise exceptions.NegotiationError, 'calculated mac_%s differs from received mac_%s' % (i_o, i_o)

	def make_identity(self, form, dh_i):
		if self.negotiated['send_pubkey']:
			if self.negotiated['sign_algs'] == (XmlDsig + 'rsa-sha256'):
				pubkey = secrets.secrets().my_pubkey(self.conn.name)
				fields = (pubkey.n, pubkey.e)

				cb_fields = map(lambda f: base64.b64encode(crypto.encode_mpi(f)), fields)

				pubkey_s = '<RSAKeyValue xmlns="http://www.w3.org/2000/09/xmldsig#"><Modulus>%s</Modulus><Exponent>%s</Exponent></RSAKeyValue>' % tuple(cb_fields)
		else:
			pubkey_s = ''

		form_s2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))

		old_c_s = self.c_s
		content = self.n_o + self.n_s + crypto.encode_mpi(dh_i) + pubkey_s + self.form_s + form_s2

		mac_s = self.hmac(self.ks_s, content)

		if self.negotiated['send_pubkey']:
			signature = self.sign(mac_s)

			sign_s = '<SignatureValue xmlns="http://www.w3.org/2000/09/xmldsig#">%s</SignatureValue>' % base64.b64encode(signature)

			if self.negotiated['send_pubkey'] == 'hash':
				b64ed = base64.b64encode(self.hash(pubkey_s))
				pubkey_s = '<fingerprint>%s</fingerprint>' % b64ed

			id_s = self.encrypt(pubkey_s + sign_s)
		else:
			id_s = self.encrypt(mac_s)

		m_s = self.hmac(self.km_s, crypto.encode_mpi(old_c_s) + id_s)

		if self.status == 'requested-e2e' and self.sas_algs == 'sas28x5':
			# we're alice; check for a retained secret
			# if none exists, prompt the user with the SAS
			self.sas = crypto.sas_28x5(m_s, self.form_o)

			if self.sigmai:
				# XXX save retained secret?
				self.check_identity(lambda : ())

		return (xmpp.DataField(name='identity', value=base64.b64encode(id_s)), \
						xmpp.DataField(name='mac', value=base64.b64encode(m_s)))

	def negotiate_e2e(self, sigmai):
		self.negotiated = {}

		request = xmpp.Message()
		feature = request.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='form')

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='accept', value='1', typ='boolean', required=True))

		# this field is incorrectly called 'otr' in XEPs 0116 and 0217
		x.addChild(node=xmpp.DataField(name='logging', typ='list-single', options=self.logging_preference(), required=True))

		# unsupported options: 'disabled', 'enabled'
		x.addChild(node=xmpp.DataField(name='disclosure', typ='list-single', options=['never'], required=True))
		x.addChild(node=xmpp.DataField(name='security', typ='list-single', options=['e2e'], required=True))
		x.addChild(node=xmpp.DataField(name='crypt_algs', value='aes128-ctr', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='hash_algs', value='sha256', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='compress', value='none', typ='hidden'))

		# unsupported options: 'iq', 'presence'
		x.addChild(node=xmpp.DataField(name='stanzas', typ='list-multi', options=['message']))

		x.addChild(node=xmpp.DataField(name='init_pubkey', options=['none', 'key', 'hash'], typ='list-single'))

		# XXX store key, use hash
		x.addChild(node=xmpp.DataField(name='resp_pubkey', options=['none', 'key'], typ='list-single'))

		x.addChild(node=xmpp.DataField(name='ver', value='1.0', typ='hidden'))

		x.addChild(node=xmpp.DataField(name='rekey_freq', value='4294967295', typ='hidden'))

		x.addChild(node=xmpp.DataField(name='sas_algs', value='sas28x5', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='sign_algs', value='http://www.w3.org/2000/09/xmldsig#rsa-sha256', typ='hidden'))

		self.n_s = crypto.generate_nonce()

		x.addChild(node=xmpp.DataField(name='my_nonce', value=base64.b64encode(self.n_s), typ='hidden'))

		modp_options = [ 5, 14, 2, 1 ]

		x.addChild(node=xmpp.DataField(name='modp', typ='list-single', options=map(lambda x: [ None, x ], modp_options)))

		x.addChild(node=self.make_dhfield(modp_options, sigmai))
		self.sigmai = sigmai

		self.form_s = ''.join(map(lambda el: xmpp.c14n.c14n(el), x.getChildren()))

		feature.addChild(node=x)

		self.status = 'requested-e2e'

		self.send(request)

	# 4.3 esession response (bob)
	def verify_options_bob(self, form):
		negotiated = {'recv_pubkey': None, 'send_pubkey': None}
		not_acceptable = []
		ask_user = {}

		fixed = { 'disclosure': 'never',
								'security': 'e2e',
							'crypt_algs': 'aes128-ctr',
							'hash_algs': 'sha256',
								'compress': 'none',
								'stanzas': 'message',
						'init_pubkey': 'none',
						'resp_pubkey': 'none',
										'ver': '1.0',
								'sas_algs': 'sas28x5' }

		self.encryptable_stanzas = ['message']

		self.sas_algs = 'sas28x5'
		self.cipher = AES
		self.hash_alg = SHA256
		self.compression = None

		for name, field in map(lambda name: (name, form.getField(name)), form.asDict().keys()):
			options = map(lambda x: x[1], field.getOptions())
			values = field.getValues()

			if not field.getType() in ('list-single', 'list-multi'):
				options = values

			if name in fixed:
				if fixed[name] in options:
					negotiated[name] = fixed[name]
				else:
					not_acceptable.append(name)
			elif name == 'rekey_freq':
				preferred = int(options[0])
				negotiated['rekey_freq'] = preferred
				self.rekey_freq = preferred
			elif name == 'logging':
				my_prefs = self.logging_preference()

				if my_prefs[0] in options: # our first choice is offered, select it
					pref = my_prefs[0]
					negotiated['logging'] = pref
				else:	# see if other acceptable choices are offered
					for pref in my_prefs:
						if pref in options:
							ask_user['logging'] = pref
							break

					if not 'logging' in ask_user:
						not_acceptable.append(name)
			elif name == 'init_pubkey':
				for x in ('key'):
					if x in options:
						negotiated['recv_pubkey'] = x
						break
			elif name == 'resp_pubkey':
				for x in ('hash', 'key'):
					if x in options:
						negotiated['send_pubkey'] = x
						break
			elif name == 'sign_algs':
				if (XmlDsig + 'rsa-sha256') in options:
					negotiated['sign_algs'] = XmlDsig + 'rsa-sha256'
			else:
				# XXX some things are handled elsewhere, some things are not-implemented
				pass

		return (negotiated, not_acceptable, ask_user)

	# 4.3 esession response (bob)
	def respond_e2e_bob(self, form, negotiated, not_acceptable):
		response = xmpp.Message()
		feature = response.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='accept', value='true'))

		for name in negotiated:
			# some fields are internal and should not be sent
			if not name in ('send_pubkey', 'recv_pubkey'):
				x.addChild(node=xmpp.DataField(name=name, value=negotiated[name]))

		self.negotiated = negotiated

		# the offset of the group we chose (need it to match up with the dhhash)
		group_order = 0
		self.modp = int(form.getField('modp').getOptions()[group_order][1])
		x.addChild(node=xmpp.DataField(name='modp', value=self.modp))

		g = dh.generators[self.modp]
		p = dh.primes[self.modp]

		self.n_o = base64.b64decode(form['my_nonce'])

		dhhashes = form.getField('dhhashes').getValues()
		self.negotiated['He'] = base64.b64decode(dhhashes[group_order].encode("utf8"))

		bytes = int(self.n / 8)

		self.n_s = crypto.generate_nonce()

		self.c_o = crypto.decode_mpi(crypto.random_bytes(bytes)) # n-bit random number
		self.c_s = self.c_o ^ (2 ** (self.n - 1))

		self.y = crypto.srand(2 ** (2 * self.n - 1), p - 1)
		self.d = crypto.powmod(g, self.y, p)

		to_add = { 'my_nonce': self.n_s,
							 'dhkeys': crypto.encode_mpi(self.d),
							 'counter': crypto.encode_mpi(self.c_o),
							 'nonce': self.n_o }

		for name in to_add:
			b64ed = base64.b64encode(to_add[name])
			x.addChild(node=xmpp.DataField(name=name, value=b64ed))

		self.form_o = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))
		self.form_s = ''.join(map(lambda el: xmpp.c14n.c14n(el), x.getChildren()))

		self.status = 'responded-e2e'

		feature.addChild(node=x)

		if not_acceptable:
			response = xmpp.Error(response, xmpp.ERR_NOT_ACCEPTABLE)

			feature = xmpp.Node(xmpp.NS_FEATURE + ' feature')

			for f in not_acceptable:
				n = xmpp.Node('field')
				n['var'] = f
				feature.addChild(node=n)

			response.T.error.addChild(node=feature)

		self.send(response)

	# 'Alice Accepts'
	def verify_options_alice(self, form):
		negotiated = {}
		ask_user = {}
		not_acceptable = []

		if not form['logging'] in self.logging_preference():
			not_acceptable.append(form['logging'])
		elif form['logging'] != self.logging_preference()[0]:
			ask_user['logging'] = form['logging']
		else:
			negotiated['logging'] = self.logging_preference()[0]

		for r,a in (('recv_pubkey', 'resp_pubkey'), ('send_pubkey', 'init_pubkey')):
			negotiated[r] = None

			if a in form.asDict() and form[a] in ('key', 'hash'):
				negotiated[r] = form[a]

		if 'sign_algs' in form.asDict():
			if form['sign_algs'] in (XmlDsig + 'rsa-sha256',):
				negotiated['sign_algs'] = form['sign_algs']
			else:
				not_acceptable.append(form['sign_algs'])

		return (negotiated, not_acceptable, ask_user)

	# 'Alice Accepts', continued
	def accept_e2e_alice(self, form, negotiated):
		self.encryptable_stanzas = ['message']
		self.sas_algs = 'sas28x5'
		self.cipher = AES
		self.hash_alg = SHA256
		self.compression = None

		self.negotiated = negotiated

		accept = xmpp.Message()
		feature = accept.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		result = xmpp.DataForm(typ='result')

		self.c_s = crypto.decode_mpi(base64.b64decode(form['counter']))
		self.c_o = self.c_s ^ (2 ** (self.n - 1))

		self.n_o = base64.b64decode(form['my_nonce'])

		mod_p = int(form['modp'])
		p = dh.primes[mod_p]
		x = self.xes[mod_p]
		e = self.es[mod_p]

		self.d = crypto.decode_mpi(base64.b64decode(form['dhkeys']))

		self.k = self.get_shared_secret(self.d, x, p)

		result.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		result.addChild(node=xmpp.DataField(name='accept', value='1'))
		result.addChild(node=xmpp.DataField(name='nonce', value=base64.b64encode(self.n_o)))

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(self.k)

		if self.sigmai:
			self.kc_o, self.km_o, self.ks_o = self.generate_responder_keys(self.k)
			self.verify_identity(form, self.d, True, 'b')
		else:
			srses = secrets.secrets().retained_secrets(self.conn.name, self.jid.getStripped())
			rshashes = [self.hmac(self.n_s, rs) for (rs,v) in srses]

			if not rshashes:
				# we've never spoken before, but we'll pretend we have
				rshash_size = self.hash_alg.digest_size
				rshashes.append(crypto.random_bytes(rshash_size))

			rshashes = [base64.b64encode(rshash) for rshash in rshashes]
			result.addChild(node=xmpp.DataField(name='rshashes', value=rshashes))
			result.addChild(node=xmpp.DataField(name='dhkeys', value=base64.b64encode(crypto.encode_mpi(e))))

			self.form_o = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))

		# MUST securely destroy K unless it will be used later to generate the final shared secret

		for datafield in self.make_identity(result, e):
			result.addChild(node=datafield)

		feature.addChild(node=result)
		self.send(accept)

		if self.sigmai:
			self.status = 'active'
			self.enable_encryption = True
		else:
			self.status = 'identified-alice'

	# 4.5 esession accept (bob)
	def accept_e2e_bob(self, form):
		response = xmpp.Message()

		init = response.NT.init
		init.setNamespace(xmpp.NS_ESESSION_INIT)

		x = xmpp.DataForm(typ='result')

		for field in ('nonce', 'dhkeys', 'rshashes', 'identity', 'mac'):
			assert field in form.asDict(), "alice's form didn't have a %s field" % field

		# 4.5.1 generating provisory session keys
		e = crypto.decode_mpi(base64.b64decode(form['dhkeys']))
		p = dh.primes[self.modp]

		if crypto.sha256(crypto.encode_mpi(e)) != self.negotiated['He']:
			raise exceptions.NegotiationError, 'SHA256(e) != He'

		k = self.get_shared_secret(e, self.y, p)

		self.kc_o, self.km_o, self.ks_o = self.generate_initiator_keys(k)

		# 4.5.2 verifying alice's identity

		self.verify_identity(form, e, False, 'a')

		# 4.5.4 generating bob's final session keys

		srs = ''

		srses = secrets.secrets().retained_secrets(self.conn.name, self.jid.getStripped())
		rshashes = [base64.b64decode(rshash) for rshash in form.getField('rshashes').getValues()]

		for (secret, verified) in srses:
			if self.hmac(self.n_o, secret) in rshashes:
				srs = secret
				break

		# other shared secret
		# (we're not using one)
		oss = ''

		k = crypto.sha256(k + srs + oss)

		self.kc_s, self.km_s, self.ks_s = self.generate_responder_keys(k)
		self.kc_o, self.km_o, self.ks_o = self.generate_initiator_keys(k)

		# 4.5.5
		if srs:
			srshash = self.hmac(srs, 'Shared Retained Secret')
		else:
			srshash = crypto.random_bytes(32)

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='nonce', value=base64.b64encode(self.n_o)))
		x.addChild(node=xmpp.DataField(name='srshash', value=base64.b64encode(srshash)))

		for datafield in self.make_identity(x, self.d):
			x.addChild(node=datafield)

		init.addChild(node=x)

		self.send(response)

		self.do_retained_secret(k, srs)

		if self.negotiated['logging'] == 'mustnot':
			self.loggable = False

		self.status = 'active'
		self.enable_encryption = True

		if hasattr(self, 'control'):
			self.control.print_esession_details()

	def final_steps_alice(self, form):
		srs = ''
		srses = secrets.secrets().retained_secrets(self.conn.name, self.jid.getStripped())

		srshash = base64.b64decode(form['srshash'])

		for (secret, verified) in srses:
			if self.hmac(secret, 'Shared Retained Secret') == srshash:
				srs = secret
				break

		oss = ''
		k = crypto.sha256(self.k + srs + oss)
		del self.k

		self.do_retained_secret(k, srs)

		# don't need to calculate ks_s here

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(k)
		self.kc_o, self.km_o, self.ks_o = self.generate_responder_keys(k)

		# 4.6.2 Verifying Bob's Identity

		self.verify_identity(form, self.d, False, 'b')
# Note: If Alice discovers an error then she SHOULD ignore any encrypted content she received in the stanza.

		if self.negotiated['logging'] == 'mustnot':
			self.loggable = False

		self.status = 'active'
		self.enable_encryption = True

		if hasattr(self, 'control'):
			self.control.print_esession_details()

	# calculate and store the new retained secret
	# prompt the user to check the remote party's identity (if necessary)
	def do_retained_secret(self, k, srs):
		new_srs = self.hmac(k, 'New Retained Secret')
		account = self.conn.name
		bjid = self.jid.getStripped()

		if srs:
			if secrets.secrets().srs_verified(account, bjid, srs):
				secrets.secrets().replace_srs(account, bjid, srs, new_srs, True)
			else:
				def _cb(verified):
					secrets.secrets().replace_srs(account, bjid, srs, new_srs, verified)

				self.check_identity(_cb)
		else:
			def _cb(verified):
				secrets.secrets().save_new_srs(account, bjid, new_srs, verified)

			self.check_identity(_cb)

	def make_dhfield(self, modp_options, sigmai):
		dhs = []

		for modp in modp_options:
			p = dh.primes[modp]
			g = dh.generators[modp]

			x = crypto.srand(2 ** (2 * self.n - 1), p - 1)

			# XXX this may be a source of performance issues
			e = crypto.powmod(g, x, p)

			self.xes[modp] = x
			self.es[modp] = e

			if sigmai:
				dhs.append(base64.b64encode(crypto.encode_mpi(e)))
				name = 'dhkeys'
			else:
				He = crypto.sha256(crypto.encode_mpi(e))
				dhs.append(base64.b64encode(He))
				name = 'dhhashes'

		return xmpp.DataField(name=name, typ='hidden', value=dhs)

	def terminate_e2e(self):
		self.terminate()

		self.enable_encryption = False

	def acknowledge_termination(self):
		StanzaSession.acknowledge_termination(self)

		self.enable_encryption = False

	def fail_bad_negotiation(self, reason, fields = None):
		'''sends an error and cancels everything.

if fields == None, the remote party has given us a bad cryptographic value of some kind

otherwise, list the fields we haven't implemented'''

		err = xmpp.Error(xmpp.Message(), xmpp.ERR_FEATURE_NOT_IMPLEMENTED)
		err.T.error.T.text.setData(reason)

		if fields:
			feature = xmpp.Node(xmpp.NS_FEATURE + ' feature')

			for field in fields:
				fn = xmpp.Node('field')
				fn['var'] = field
				feature.addChild(node=feature)

			err.addChild(node=feature)

		self.send(err)

		self.status = None
		self.enable_encryption = False

		# this prevents the MAC check on decryption from succeeding,
		# preventing falsified messages from going through.
		self.km_o = ''

	def is_loggable(self):
		account = self.conn.name
		no_log_for = gajim.config.get_per('accounts', account, 'no_log_for')

		if not no_log_for:
			no_log_for = ''

		no_log_for = no_log_for.split()

		return self.loggable and account not in no_log_for and self.jid not in no_log_for

	def cancelled_negotiation(self):
		StanzaSession.cancelled_negotiation(self)
		self.enable_encryption = False

		self.km_o = ''
