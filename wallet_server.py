import urllib.parse

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
import requests

import wallet

app = Flask(__name__, template_folder='./templates')


@app.route('/wallet')
def index():
    return render_template('./wallet/index.html')


@app.route('/wallet/create', methods=['POST'])
def create_wallet():
    my_wallet = wallet.Wallet()
    response = {
        'private_key': my_wallet.private_key,
        'blockchain_address': my_wallet.blockchain_address,
    }
    return jsonify(response), 200


@app.route('/transaction', methods=['POST'])
def create_transaction():  #TODO
    request_json = request.json
    required = (
        'sender_private_key',
        'recipient_blockchain_address',
        'value',
        'transaction_message'
    )   # 必須事項を示す 1
    if not all(k in request_json for k in required):
        return 'missing values', 400
    sender_private_key = request_json['sender_private_key']
    sender_public_key = wallet.Wallet.generate_public_key(sender_private_key)
    sender_blockchain_address = wallet.Wallet.generate_blockchain_address(sender_public_key)
    recipient_blockchain_address = request_json['recipient_blockchain_address']
    value = float(request_json['value'])
    transaction_message = request_json['transaction_message']

    transaction = wallet.Transaction(
        sender_private_key,
        sender_public_key,
        sender_blockchain_address,
        recipient_blockchain_address,
        value,
        transaction_message
    )

    json_data = {
        'sender_blockchain_address': sender_blockchain_address,
        'recipient_blockchain_address': recipient_blockchain_address,
        'sender_public_key': sender_public_key,
        'value': value,
        'transaction_message': transaction_message,
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


@app.route('/wallet/reload_blockchain_address', methods=['GET'])  #TODO
def create_new_blockchain_address():
    required = ['private_key']
    if not all(k in request.args for k in required):
        return 'Missing values', 400
    my_private_key = request.args.get('private_key')
    my_public_key = wallet.Wallet.generate_public_key(my_private_key)
    new_blockchain_address = wallet.Wallet.generate_blockchain_address(my_public_key)
    return jsonify({'message': 'success', 'new_blockchain_address': new_blockchain_address}), 200


###############database_server#################

@app.route('/explorer', methods=['GET'])
def explorer():
    return render_template('./explorer/explorer_top.html')


@app.route('/explorer/blockchain_address', methods=['GET'])
def explorer_blockchain_address_amount():
    blockchain_address = request.args['search_value']
    response = requests.get(urllib.parse.urljoin(app.config['gw'], 'transaction_aggregation'), timeout=3)  # TODO 本来はすでにデータ保持済
    if response.status_code == 200:
        transaction_aggregation = response.json()['transaction_aggregation']
        total_amount = 0.0
        transaction_history = []
        for block_number, transaction_data in enumerate(transaction_aggregation):
            for transaction in transaction_data:
                value = float(transaction['value'])
                if blockchain_address == transaction['recipient_blockchain_address']:
                    transaction_history.append({'block_number': block_number, 'transaction': transaction})
                    total_amount += value
                if blockchain_address == transaction['sender_blockchain_address']:
                    transaction_history.append({'block_number': block_number, 'transaction': transaction})
                    total_amount -= value
        return render_template('./explorer/blockchain_address.html', blockchain_address=blockchain_address,
                               total_amount=total_amount, transaction_history=list(reversed(transaction_history)))
    return jsonify({'message': 'fail', 'error': response.content}), 400


@app.route('/explorer/block', methods=['GET'])
def explorer_block():
    block_number = int(request.args['search_value'])
    response = requests.get(urllib.parse.urljoin(app.config['gw'], 'chain'), timeout=3)
    if response.status_code == 200:
        chain = response.json()['chain']
        return jsonify({'message': 'success', 'block_number': block_number, 'block': chain[block_number]}), 200
    return jsonify({'message': 'fail', 'error': response.content}), 400


@app.route('/explorer/hashrate', methods=['GET'])
def get_rate():
    response = requests.get(urllib.parse.urljoin(app.config['gw'], 'chain'), timeout=3)
    if response.status_code == 200:
        chain = response.json()['chain']
        difficulty = response.json()['difficulty']
        time_average = (chain[-1]['timestamp'] - chain[-11]['timestamp']) / 10
        rate = 2 ** (difficulty * 4) / time_average
        response = {
            'rate': rate
        }
        return jsonify(response), 200
    return jsonify({'message': 'fail', 'error': response.content}), 400


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
