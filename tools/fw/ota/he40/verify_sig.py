import base64, hashlib
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
pub = serialization.load_pem_public_key(open('pubkey.pem','rb').read())
sig = "YnrZ7B54jG+VeTATPEEWZtyLjzU066a3G3eexL1okdd7cLE/K+uyR/yvaqcaICuRNl6pfMyAhrXVguGuBDKP0A=="
raw = base64.b64decode(sig)
print("sig len:", len(raw))
try:
    m = pub.decrypt(raw, padding.PKCS1v15())
    print("decrypted:", m.hex(), "len", len(m))
    # is it MD5 of something?
except Exception as e:
    print("decrypt failed:", e)
# try public_decrypt semantics: RSA_public_decrypt uses public key to decrypt (verify signature)
