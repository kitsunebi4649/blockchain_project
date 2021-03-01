import base58
import hashlib

from ecdsa import SECP256k1
from ecdsa import SigningKey

import utils


class Wallet(object):

    def __init__(self):
        self.private_key = SigningKey.generate(curve=SECP256k1).to_string().hex()
        self.public_key = self.generate_public_key(self.private_key)
        self.blockchain_address = self.generate_blockchain_address(self.public_key)

    @classmethod
    def generate_public_key(cls, private_key):
        private_key_bytes = SigningKey.from_string(bytes().fromhex(private_key), curve=SECP256k1)
        public_key_bytes = bytes.fromhex('04') + private_key_bytes.get_verifying_key().to_string()
        public_key = public_key_bytes.hex()
        return public_key

    @classmethod
    def generate_blockchain_address(cls, public_key):
        public_key_bytes = bytes().fromhex(public_key)
        sha256_bpk = hashlib.sha256(public_key_bytes)
        sha256_bpk_digest = sha256_bpk.digest()

        ripemed160_bpk = hashlib.new('ripemd160')
        ripemed160_bpk.update(sha256_bpk_digest)
        ripemed160_bpk_digest = ripemed160_bpk.digest()

        network_byte = bytes.fromhex('00')
        network_bitcoin_public_key_bytes = network_byte + ripemed160_bpk_digest
        checksum = cls.generate_checksum(network_bitcoin_public_key_bytes)

        blockchain_address = base58.b58encode(network_bitcoin_public_key_bytes + checksum).decode('utf-8')
        return blockchain_address

    @classmethod
    def generate_checksum(cls, network_bitcoin_public_key_bytes):
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
