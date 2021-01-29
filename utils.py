import collections
import logging
import re
import socket
import qrcode
import hashlib
import codecs
import base58

logger = logging.getLogger(__name__)

RE_IP = re.compile(
    '(?P<prefix_host>^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.)'
    '(?P<last_ip>\\d{1,3}$)')


def sorted_dict_by_key(unsorted_dict):
    return collections.OrderedDict(
        sorted(unsorted_dict.items(), key=lambda d: d[0]))


def pprint(chains):
    for i, chain in enumerate(chains):
        print(f'{"="*25} Chain {i} {"="*25}')
        for k, v in chain.items():
            if k == 'transactions':
                print(k)
                for d in v:
                    print(f'{"-"*40}')
                    for kk, vv in d.items():
                        print(f' {kk:30}{vv}')
            else:
                print(f'{k:15}{v}')
    print(f'{"*"*25}')


def is_found_host(target, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((target, port))
            return True
        except Exception as ex:
            logger.error({
                'action': 'is_found_host',
                'target': target,
                'port': port,
                'ex': ex
            })
            return False


def find_neighbours(
        my_host, my_port, start_ip_range, end_ip_range, start_port, end_port):
    # 192.168.0.24 (1,3)
    address = f'{my_host}:{my_port}'
    m = RE_IP.search(my_host)
    if not m:
        return None

    prefix_host = m.group('prefix_host')
    last_ip = m.group('last_ip')

    neighbours = []
    for guess_port in range(start_port, end_port):
        for ip_range in range(start_ip_range, end_ip_range):
            guess_host = f'{prefix_host}{int(last_ip)+int(ip_range)}'
            guess_address = f'{guess_host}:{guess_port}'
            if (is_found_host(guess_host, guess_port) and
                    not guess_address == address):
                neighbours.append(guess_address)
    return neighbours


def get_host():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception as ex:
        logger.debug({'action': 'get_host', 'ex': ex})
    return '127.0.0.1'


def generate_qrcode(private_key, blockchain_address, port):
    if port == 5000:  # 応急処置
        result = qrcode.make('192.168.0.3:8080/?' + 'private_key='  # 固定値注意 (IPと8080)
                         + str(private_key) + '&' + 'blockchain_address=' + str(blockchain_address))
        name = str(port) + "'s_address.png"
        result.save(name)


def generate_blockchain_address(public_key_bytes_string):
    public_key_bytes = public_key_bytes_string
    sha256_bpk = hashlib.sha256(public_key_bytes)
    sha256_bpk_digest = sha256_bpk.digest()

    ripemed160_bpk = hashlib.new('ripemd160')
    ripemed160_bpk.update(sha256_bpk_digest)
    ripemed160_bpk_digest = ripemed160_bpk.digest()
    ripemed160_bpk_hex = codecs.encode(ripemed160_bpk_digest, 'hex')

    network_byte = b'00'
    network_bitcoin_public_key = network_byte + ripemed160_bpk_hex
    network_bitcoin_public_key_bytes = codecs.decode(
        network_bitcoin_public_key, 'hex')

    sha256_bpk = hashlib.sha256(network_bitcoin_public_key_bytes)
    sha256_bpk_digest = sha256_bpk.digest()
    sha256_2_nbpk = hashlib.sha256(sha256_bpk_digest)
    sha256_2_nbpk_digest = sha256_2_nbpk.digest()
    sha256_hex = codecs.encode(sha256_2_nbpk_digest, 'hex')

    checksum = sha256_hex[:8]

    address_hex = (network_bitcoin_public_key + checksum).decode('utf-8')

    blockchain_address = base58.b58encode(address_hex).decode('utf-8')
    return blockchain_address
