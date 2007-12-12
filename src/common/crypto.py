# common crypto functions (mostly specific to XEP-0116, but useful elsewhere)

import os
import math

from Crypto.Hash import SHA256

# convert a large integer to a big-endian bitstring
def encode_mpi(n):
	if n >= 256:
		return encode_mpi(n / 256) + chr(n % 256)
	else:
		return chr(n)

# convert a large integer to a big-endian bitstring, padded with \x00s to
# a multiple of 16 bytes
def encode_mpi_with_padding(n):
	return pad_to_multiple(encode_mpi(n), 16, '\x00', True)

# pad 'string' to a multiple of 'multiple_of' with 'char'.
# pad on the left if 'left', otherwise pad on the right.
def pad_to_multiple(string, multiple_of, char, left):
	mod = len(string) % multiple_of
	if mod == 0:
		return string
	else:
		padding = (multiple_of - mod) * char

	if left:
		return padding + string
	else:
		return string + padding

# convert a big-endian bitstring to an integer
def decode_mpi(s):
	if len(s) == 0:
		return 0
	else:
		return 256 * decode_mpi(s[:-1]) + ord(s[-1])

def sha256(string):
	sh = SHA256.new()
	sh.update(string)
	return sh.digest()

base28_chr = "acdefghikmopqruvwxy123456789"

def sas_28x5(m_a, form_b):
	sha = sha256(m_a + form_b + 'Short Authentication String')
	lsb24 = decode_mpi(sha[-3:])
	return base28(lsb24)

def base28(n):
	if n >= 28:
		return base28(n / 28) + base28_chr[n % 28]
	else:
		return base28_chr[n]

def random_bytes(bytes):
	return os.urandom(bytes)

def generate_nonce():
	return random_bytes(8)

# generate a random number between 'bottom' and 'top'
def srand(bottom, top):
	# minimum number of bytes needed to represent that range
	bytes = int(math.ceil(math.log(top - bottom, 256)))

	# in retrospect, this is horribly inadequate.
	return (decode_mpi(random_bytes(bytes)) % (top - bottom)) + bottom

# a faster version of (base ** exp) % mod
#		taken from <http://lists.danga.com/pipermail/yadis/2005-September/001445.html> 
def powmod(base, exp, mod):
	square = base % mod
	result = 1

	while exp > 0:
		if exp & 1: # exponent is odd
			result = (result * square) % mod

		square = (square * square) % mod
		exp /= 2

	return result
