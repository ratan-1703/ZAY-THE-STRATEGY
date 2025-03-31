from decimal import Decimal
import time
import requests
from requests.auth import HTTPBasicAuth
from nearai.agents.environment import Environment
from intents.withdraw import withdraw_from_intents
import json
from zcash.zcash_utils import getAccountForAddress, account_balance, validate_zcash_address, getZcashIntentAccount, getAddressForAccount

rpc_url = "https://bridge.chaindefuser.com/rpc"
zcash_fees = Decimal("0.0002")
zcash_account = None

with open("tokens.json", "r") as file:
    data = json.load(file)


def transfer(env: Environment, sender, amount, recipient, args = [1, str(zcash_fees), 'NoPrivacy']):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_sendmany",
        "params": [
            sender,
            [
                {
                    "address": recipient,
                    "amount": str(Decimal(amount) - zcash_fees)
                }
            ],
        ]
    }

    payload["params"].extend(args)

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
    if not response["result"]:
        return False
    opid = response["result"]

    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_listoperationids",
        "params": []
    }

    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
    
    if opid not in response["result"]:
        return opid

    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_getoperationstatus",
        "params": [
            [opid]
        ]
    }

    start_time = time.time()
    timeout = 300
    
    while True:
        response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
        if response["result"] and response["result"][0]:  # Check if result is available
            result = response["result"][0]

            if result["status"] == "success":
                txid = result["result"]["txid"]
                return txid
            elif result["status"] == "failed":
                env.add_reply(result)
                return None
        
        if time.time() - start_time > timeout:  # Check if 2 minutes have passed
            env.add_reply("Timeout: Operation did not complete within 2 minutes")
            return None  # Or handle timeout case accordingly
        
        time.sleep(2)




async def deposit(env: Environment, sender, amount):
    
    user_account_id = env.env_vars.get("ACCOUNT_ID")
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}

    account = getAccountForAddress(env, sender)
    balance_transparent, balance_shielded = account_balance(env, account)

    match = [obj for obj in data if obj["symbol"] == "ZEC"]
    token_data = match[0]

    amount = Decimal(amount) + Decimal(zcash_fees)
    if Decimal(amount) > Decimal(balance_shielded) + Decimal(balance_transparent):
        env.add_reply(f"You have insufficiant balance of {Decimal(balance_shielded) + Decimal(balance_transparent)}. Cannot deposit {amount}")
        return False

    if Decimal(amount) > Decimal(balance_shielded) and Decimal(amount) < Decimal(balance_shielded) + Decimal(balance_transparent):
        args = [
            1,
            str(zcash_fees),
            "AllowRevealedSenders"
        ]

        amount = Decimal(amount) + Decimal(zcash_fees)
        txid = transfer(env, sender, amount, sender, args)
        if not txid:
            return False
        
        env.add_reply(f"Transaction Id: {txid}")
        
        start_time = time.time()
        timeout = 300
        while True:
            _, shielded = account_balance(account)
            if Decimal(shielded) > Decimal(amount):
                break
            
            if time.time() - start_time > timeout:  # Check if 5 minutes have passed
                env.add_reply("Timeout: Operation did not complete within 5 minutes")
                return None

            time.sleep(2)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "deposit_address",
        "params": [{
            "account_id": user_account_id,
            "chain": "zec:mainnet"
        }]
    }
    
    # wait unitl the amount gets confirmed on intents
    
    response = requests.post(rpc_url, json=payload).json()
    deposit_address = response["result"]["address"]

    args = [
        1,
        str(zcash_fees),
        "NoPrivacy"
    ]

    txid = transfer(env, sender, amount, deposit_address, args)
    env.add_reply(f"Transaction Id: {txid}")
    
    start_time = time.time()
    timeout = 600
    
    user_account_id = env.env_vars.get("ACCOUNT_ID", None)
    user_private_key = env.env_vars.get("PRIVATE_KEY", None)
    near = env.set_near(user_account_id, user_private_key)
    
    args = {
        "account_id": user_account_id,
        "token_ids": ["nep141:zec.omft.near"],
    }
    
    while True:
        tr = await near.view("intents.near", "mt_batch_balance_of", args)
        zec_balance = Decimal(tr.result[0]) / Decimal(Decimal(10) ** int(token_data["decimals"]))
        
        if Decimal(zec_balance) >= Decimal(amount) - Decimal(zcash_fees):
            break
        
        if time.time() - start_time > timeout:  # Check if 5 minutes have passed
            return txid
        
        time.sleep(10)
        
    return txid

async def withdraw(env: Environment, token, amount, recipient, data):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")
    headers = {"Content-Type": "text/plain"}
    
    obj = validate_zcash_address(env, recipient)
    is_valid, address_type = obj["isvalid"], obj["address_type"]
    if not is_valid:
        env.add_reply(f"Address {recipient} is not valid for zcash chain.")
        return False

    match = [obj for obj in data if obj["symbol"] == token.upper()]

    if not match:
      env.add_reply(f"Token {token} may not be supported for this app.")
      return False

    token_data = match[0]

    if address_type in ("p2pkh", "p2sh"):
        return await withdraw_from_intents(env, token, amount, recipient, data, token_data)
    
    account = getZcashIntentAccount(env)
    if account == -1:
        return False
    
    
    unified_address = getAddressForAccount(env, account)

    if not unified_address:
        return False

    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_listunifiedreceivers",
        "params": [unified_address]
    }

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()

    transparent_address = response["result"]["p2pkh"] or response["result"]["p2sh"]
    shielded_address = response["result"]["sapling"] or response["result"]["orchard"]

    result = await withdraw_from_intents(env, token, amount, transparent_address, data, token_data)
    if not result:
        return False
    
    payload = {
        "jsonrpc": "2.0",
        "id": "dontcare",
        "method": "withdrawal_status",
        "params": [{
            "withdrawal_hash": result 
        }]
    }
    
    start_time = time.time()
    timeout = 600
    hash = None
    to_print = True
    to_break = 3
    
    while True:
        response = requests.post(rpc_url, json=payload).json()
        
        if "result" in response:
            res = response["result"]
            
            if "withdrawals" in res:
                
                withdrawals = res["withdrawals"][0]
                hash = withdrawals["data"]["transfer_tx_hash"]
                status = withdrawals["status"]

                if status != "PENDING":
                    break
                
                if to_print:
                    env.add_reply(f"Transaction Hash: {hash}")
                    to_print = False
                    
        else:
            if to_break < 0:
                break
            to_break = to_break - 1
            time.sleep(5)

        if time.time() - start_time > timeout:  # Check if 5 minutes have passed
            env.add_reply("Timeout: Operation did not complete within 5 minutes")
            return None
    
        time.sleep(2)


    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_getbalanceforaccount",
        "params": [int(account)]
    }

    start_time = time.time()
    timeout = 600

    while True:
        response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
        if response["result"]:
            pools = response["result"]["pools"]

            if pools and pools["transparent"] and pools["transparent"]["valueZat"]:
                balance = Decimal(pools["transparent"]["valueZat"]) / (Decimal(10) ** int(token_data["decimals"]))
                if Decimal(amount) - zcash_fees <= balance:
                    break

        if time.time() - start_time > timeout:  # Check if 5 minutes have passed
            env.add_reply("Timeout: Operation did not complete within 5 minutes")
            return None

        time.sleep(2)

    args = [
        1,
        str(zcash_fees),
        "AllowRevealedSenders"
    ]

    txid = transfer(env, unified_address, amount, recipient, args)
    env.add_reply(f"Transaction Hash: {txid}")
    return txid
