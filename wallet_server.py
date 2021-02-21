import urllib.parse

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
import requests
# from ecdsa import NIST256p
from ecdsa import SECP256k1
from ecdsa import SigningKey

import wallet

app = Flask(__name__, template_folder='./templates')


@app.route('/')
def index():
    return render_template('./index.html')


@app.route('/wallet', methods=['POST'])
def create_wallet():
    my_wallet = wallet.Wallet()
    response = {
        'private_key': my_wallet.private_key,
        # 'private_key_qrcode': my_wallet.private_key_qrcode,
        # 'public_key': my_wallet.public_key,
        'blockchain_address': my_wallet.blockchain_address,
    }
    return jsonify(response), 200


@app.route('/transaction', methods=['POST'])
def create_transaction():  #TODO
    request_json = request.json
    required = (
        'sender_private_key',
        # 'sender_blockchain_address',
        'recipient_blockchain_address',
        # 'sender_public_key',
        'value')
    if not all(k in request_json for k in required):
        return 'missing values', 400

    sender_private_key = request_json['sender_private_key']
    private_key_bytes = SigningKey.from_string(
        bytes().fromhex(sender_private_key), curve=SECP256k1)
    sender_public_key_string_bytes = bytes.fromhex("04") + private_key_bytes.get_verifying_key().to_string()
    sender_public_key = sender_public_key_string_bytes.hex()
    sender_blockchain_address = wallet.Wallet.generate_blockchain_address(sender_public_key_string_bytes)
    recipient_blockchain_address = request_json['recipient_blockchain_address']
    value = float(request_json['value'])

    transaction = wallet.Transaction(
        sender_private_key,
        sender_public_key,
        sender_blockchain_address,
        recipient_blockchain_address,
        value)

    json_data = {
        'sender_blockchain_address': sender_blockchain_address,
        'recipient_blockchain_address': recipient_blockchain_address,
        'sender_public_key': sender_public_key,
        'value': value,
        'signature': transaction.generate_signature(),
    }

    response = requests.post(
        urllib.parse.urljoin(app.config['gw'], 'transactions'),
        json=json_data, timeout=3)

    if response.status_code == 201:
        return jsonify({'message': 'success'}), 201
    return jsonify({'message': 'fail', 'response': response}), 400


@app.route('/wallet/amount', methods=['GET'])
def calculate_amount():
    required = ['blockchain_address']
    if not all(k in request.args for k in required):
        return 'Missing values', 400

    my_blockchain_address = request.args.get('blockchain_address')
    response = requests.get(
        urllib.parse.urljoin(app.config['gw'], 'amount'),
        {'blockchain_address': my_blockchain_address},
        timeout=3)
    if response.status_code == 200:
        total = response.json()['amount']
        return jsonify({'message': 'success', 'amount': total}), 200
    return jsonify({'message': 'fail', 'error': response.content}), 400


@app.route('/wallet/amount/create_new_blockchain_address', methods=['GET'])  #TODO
def create_new_blockchain_address():
    required = ['private_key']
    if not all(k in request.args for k in required):
        return 'Missing values', 400
    my_private_key = request.args.get('private_key')
    my_private_key_bytes = SigningKey.from_string(bytes().fromhex(my_private_key), curve=SECP256k1)
    my_public_key_bytes = bytes.fromhex("04") + my_private_key_bytes.get_verifying_key().to_string()
    new_blockchain_address = wallet.Wallet.generate_blockchain_address(my_public_key_bytes)
    return jsonify({'message': 'success', 'new_blockchain_address': new_blockchain_address}), 200


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=8080,
                        type=int, help='port to listen on')
    parser.add_argument('-g', '--gw', default='http://127.0.0.1:5000',
                        type=str, help='blockchain gateway')
    args = parser.parse_args()
    port = args.port
    app.config['gw'] = args.gw

    app.run(host='0.0.0.0', port=port, threaded=True, debug=True)
