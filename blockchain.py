import contextlib
import hashlib
import json
import logging
import sys
import time
import threading

# from ecdsa import NIST256p
from ecdsa import SECP256k1
from ecdsa import VerifyingKey
import requests

import utils

MINING_DIFFICULTY = 3
MINING_SENDER = 'THE BLOCKCHAIN'
MINING_REWARD = 10
MINING_TIMER_SEC = 20

BLOCKCHAIN_PORT_RANGE = (5000, 5003)
NEIGHBOURS_IP_RANGE_NUM = (0, 1)
BLOCKCHAIN_NEIGHBOURS_SYNC_TIME_SEC = 20

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class BlockChain(object):

    def __init__(self, blockchain_address=None, port=None):
        self.transaction_pool = []
        self.chain = []
        self.transaction_aggregation = []
        self.neighbours = []
        self.root_hash = '0'
        self.create_block(0, self.hash({}))
        self.blockchain_address = blockchain_address
        self.port = port
        self.mining_semaphore = threading.Semaphore(1)
        self.sync_neighbours_semaphore = threading.Semaphore(1)

    def run(self):
        self.sync_neighbours()
        self.resolve_conflicts()
        self.start_mining()

    def set_neighbours(self):
        self.neighbours = utils.find_neighbours(
            utils.get_host(), self.port,
            NEIGHBOURS_IP_RANGE_NUM[0], NEIGHBOURS_IP_RANGE_NUM[1],
            BLOCKCHAIN_PORT_RANGE[0], BLOCKCHAIN_PORT_RANGE[1])
        logger.info({
            'action': 'set_neighbours', 'neighbours': self.neighbours
        })

    def sync_neighbours(self):
        is_acquire = self.sync_neighbours_semaphore.acquire(blocking=False)
        if is_acquire:
            with contextlib.ExitStack() as stack:
                stack.callback(self.sync_neighbours_semaphore.release)
                self.set_neighbours()
                loop = threading.Timer(
                    BLOCKCHAIN_NEIGHBOURS_SYNC_TIME_SEC, self.sync_neighbours)
                loop.start()

    def create_block(self, nonce, previous_hash):
        block = utils.sorted_dict_by_key({
            'timestamp': time.time(),
            'root_hash': self.root_hash,
            'nonce': nonce,
            'previous_hash': previous_hash
        })
        self.chain.append(block)
        self.transaction_aggregation.append(self.transaction_pool.copy())
        self.transaction_pool = []

        for node in self.neighbours:
            requests.delete(f'http://{node}/transactions')

        return block

    def hash(self, block):
        sorted_block = json.dumps(block, sort_keys=True)
        return hashlib.sha256(sorted_block.encode()).hexdigest()

    def add_transaction(self, sender_blockchain_address,
                        recipient_blockchain_address, value,
                        sender_public_key, transaction_message, signature):

        transaction = utils.sorted_dict_by_key({
            'sender_blockchain_address': sender_blockchain_address,
            'recipient_blockchain_address': recipient_blockchain_address,
            'value': float(value),
            'transaction_message': transaction_message
        })

        if sender_blockchain_address == MINING_SENDER:
            self.buildin_transaction(transaction)
            return True

        if self.verify_transaction_signature(
                sender_public_key, signature, transaction):

            if (self.calculate_total_amount(sender_blockchain_address)
                    < float(value)):
                logger.error(
                    {'action': 'add_transaction', 'error': 'no_value'})
                return False

            self.buildin_transaction(transaction)
            return True
        return False

    def create_transaction(self, sender_blockchain_address,
                           recipient_blockchain_address, value,
                           sender_public_key, transaction_message, signature):

        is_transacted = self.add_transaction(
            sender_blockchain_address, recipient_blockchain_address,
            value, sender_public_key, transaction_message, signature)

        if is_transacted:
            for node in self.neighbours:
                requests.put(
                    f'http://{node}/transactions',
                    json={
                        'sender_blockchain_address': sender_blockchain_address,
                        'recipient_blockchain_address':
                            recipient_blockchain_address,
                        'value': value,
                        'sender_public_key': sender_public_key,
                        'transaction_message': transaction_message,
                        'signature': signature
                    }
                )  # 他ノードにtxの追加をputで要求
        return is_transacted

    def verify_transaction_signature(
            self, sender_public_key, signature, transaction):   # txの検証
        sha256 = hashlib.sha256()
        sha256.update(str(transaction).encode('utf-8'))
        message = sha256.digest()
        signature_bytes = bytes().fromhex(signature)
        verifying_key = VerifyingKey.from_string(
            bytes().fromhex(sender_public_key[2:]), curve=SECP256k1)  # sender_public_keyの先頭'04'を消す
        verified_key = verifying_key.verify(signature_bytes, message)
        return verified_key

    def valid_proof(self, root_hash, previous_hash, nonce,
                    difficulty=MINING_DIFFICULTY):
        guess_block = utils.sorted_dict_by_key({
            'root_hash': root_hash,
            'nonce': nonce,
            'previous_hash': previous_hash
        })
        guess_hash = self.hash(guess_block)
        return guess_hash[:difficulty] == '0' * difficulty

    def proof_of_work(self):
        root_hash = self.root_hash
        previous_hash = self.hash(self.chain[-1])
        nonce = 0
        while self.valid_proof(root_hash, previous_hash, nonce) is False:
            nonce += 1
        return nonce

    def mining(self):
        # if not self.transaction_pool:
        #     return False

        self.add_transaction(
            sender_blockchain_address=MINING_SENDER,
            recipient_blockchain_address=self.blockchain_address,
            value=MINING_REWARD,
            transaction_message='',
            signature=None,
            sender_public_key=None
        )
        nonce = self.proof_of_work()
        previous_hash = self.hash(self.chain[-1])
        self.create_block(nonce, previous_hash)
        logger.info({'action': 'mining', 'status': 'success'})

        for node in self.neighbours:
            requests.put(f'http://{node}/consensus')

        return True

    def start_mining(self):
        is_acquire = self.mining_semaphore.acquire(blocking=False)
        if is_acquire:
            with contextlib.ExitStack() as stack:
                stack.callback(self.mining_semaphore.release)
                self.mining()
                loop = threading.Timer(MINING_TIMER_SEC, self.start_mining)
                loop.start()

    def calculate_total_amount(self, blockchain_address):
        total_amount = 0.0
        for transaction_data in self.transaction_aggregation:
            for transaction in transaction_data:
                value = float(transaction['value'])
                if blockchain_address == transaction['recipient_blockchain_address']:
                    total_amount += value
                if blockchain_address == transaction['sender_blockchain_address']:
                    total_amount -= value
        return total_amount

    def valid_chain(self, chain):
        pre_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(pre_block):
                return False

            if not self.valid_proof(
                    block['root_hash'], block['previous_hash'],
                    block['nonce'], MINING_DIFFICULTY):
                return False

            pre_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        longest_chain = None
        longest_chain_port = None
        max_length = len(self.chain)
        for node in self.neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                response_json = response.json()
                chain = response_json['chain']
                chain_length = len(chain)
                if chain_length > max_length and self.valid_chain(chain):
                    max_length = chain_length
                    longest_chain = chain
                    longest_chain_port = node

        if longest_chain:
            self.chain = longest_chain
            response = requests.get(f'http://{longest_chain_port}/transaction_aggregation')
            if response.status_code == 200:
                response_json = response.json()
                transaction_aggregation = response_json['transaction_aggregation']  # TODO スライスで要求
                self.transaction_aggregation = transaction_aggregation  # TODO スレッドで実行
            else:
                logger.info({'action': 'resolve_conflicts', 'status': 'replace_error'})  # TODO loggerinfoじゃない
            logger.info({'action': 'resolve_conflicts', 'status': 'replaced'})
            return True

        logger.info({'action': 'resolve_conflicts', 'status': 'not_replaced'})
        return False

    def update_root_hash(self):
        transactions = self.transaction_pool.copy()  # 参照渡し防止
        if len(transactions) % 2 == 1:
            transactions.append(transactions[-1])
        leaves = [self.hash(d) for d in transactions]  # 必ず leaves >= 2 になる
        while len(leaves) > 1:
            leaves = self.merge_leaves(leaves)  # 全体の要素を1/2に圧縮
        self.root_hash = leaves[0]


    def merge_leaves(self, leaves):
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        return [(hashlib.sha256(leaves[i].encode() + leaves[i + 1].encode())).hexdigest()
                for i in range(0, len(leaves), 2)]

    def buildin_transaction(self, transaction):
        self.transaction_pool.append(transaction)
        self.update_root_hash()

