import base58
# import codecs
import hashlib

from ecdsa import SECP256k1
from ecdsa import SigningKey
# import qrcode

import utils


class Wallet(object):

    def __init__(self):
        self._private_key = SigningKey.generate(curve=SECP256k1)
        self._04public_key_string = bytes.fromhex("04") + self._private_key.get_verifying_key().to_string()
        self._blockchain_address = self.generate_blockchain_address(self._04public_key_string)
        # self.private_key_qrcode = qrcode.make(self.private_key)
        # self.private_key_qrcode.save('private_key_qrcode.png')

    @property
    def private_key(self):
        return self._private_key.to_string().hex()

    @property
    def public_key(self):
        return self._04public_key_string.hex()

    @property
    def blockchain_address(self):
        return self._blockchain_address

    @classmethod
    def generate_blockchain_address(cls, public_key_bytes_string):
        public_key_bytes = public_key_bytes_string
        sha256_bpk = hashlib.sha256(public_key_bytes)
        sha256_bpk_digest = sha256_bpk.digest()

        ripemed160_bpk = hashlib.new('ripemd160')
        ripemed160_bpk.update(sha256_bpk_digest)
        ripemed160_bpk_digest = ripemed160_bpk.digest()

        network_byte = bytes.fromhex('00')
        network_bitcoin_public_key_bytes = network_byte + ripemed160_bpk_digest
        checksum = cls.create_checksum(network_bitcoin_public_key_bytes)

        blockchain_address = base58.b58encode(network_bitcoin_public_key_bytes + checksum).decode('utf-8')
        return blockchain_address

    @classmethod
    def create_checksum(cls, network_bitcoin_public_key_bytes):
        sha256_bpk = hashlib.sha256(network_bitcoin_public_key_bytes)
        sha256_bpk_digest = sha256_bpk.digest()
        sha256_2_nbpk = hashlib.sha256(sha256_bpk_digest)
        sha256_2_nbpk_digest = sha256_2_nbpk.digest()
        checksum = sha256_2_nbpk_digest[:4]
        return checksum


class Transaction(object):

    def __init__(self, sender_private_key, sender_public_key,
                 sender_blockchain_address, recipient_blockchain_address,
                 value, transaction_message):
        self.sender_private_key = sender_private_key
        self.sender_public_key = sender_public_key
        self.sender_blockchain_address = sender_blockchain_address
        self.recipient_blockchain_address = recipient_blockchain_address
        self.value = value
        self.transaction_message = transaction_message

    def generate_signature(self):  # TODO
        sha256 = hashlib.sha256()
        transaction = utils.sorted_dict_by_key({
            'sender_blockchain_address': self.sender_blockchain_address,
            'recipient_blockchain_address': self.recipient_blockchain_address,
            'value': float(self.value),
            'transaction_message': self.transaction_message
        })
        sha256.update(str(transaction).encode('utf-8'))
        message = sha256.digest()
        private_key = SigningKey.from_string(
            bytes().fromhex(self.sender_private_key), curve=SECP256k1)
        private_key_sign = private_key.sign(message)
        signature = private_key_sign.hex()
        return signature
