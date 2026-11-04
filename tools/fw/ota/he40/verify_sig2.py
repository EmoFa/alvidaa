import base64, hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
pub = serialization.load_pem_public_key(open('pubkey.pem','rb').read())
nums = pub.public_numbers()
n, e = nums.n, nums.e
sig = "YnrZ7B54jG+VeTATPEEWZtyLjzU066a3G3eexL1okdd7cLE/K+uyR/yvaqcaICuRNl6pfMyAhrXVguGuBDKP0A=="
c = int.from_bytes(base64.b64decode(sig), 'big')
m = pow(c, e, n)
mb = m.to_bytes(64, 'big')
print("raw decrypt hex:", mb.hex())
print("pkcs1 type2? prefix:", mb[:2].hex())
# extract the message after 00 02 PS 00
# find the 00 separator
idx = mb.find(b'\x00', 2)
msg = mb[idx+1:] if idx != -1 else b''
print("extracted msg (md5?):", msg.hex(), "len", len(msg))
