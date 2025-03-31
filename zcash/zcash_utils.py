from decimal import Decimal
import requests
from requests.auth import HTTPBasicAuth
from nearai.agents.environment import Environment
import json

rpc_url = "https://bridge.chaindefuser.com/rpc"
zcash_fees = Decimal("0.0002")
zcash_account = None

with open("tokens.json", "r") as file:
    data = json.load(file)

def createAccount(env: Environment):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_getnewaccount",
        "params": []
    }

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()

    if response["result"]["account"]:
        return int(response["result"]["account"])
    
    return -1

def getAddressForAccount(env: Environment, account):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_listaccounts",
        "params": []
    }

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
    if response["result"][int(account)]["addresses"]:
        return response["result"][int(account)]["addresses"][0]["ua"]

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_getaddressforaccount",
        "params": [int(account)]
    }

    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()

    if response["result"]["address"]:
        return response["result"]["address"]
    else:
        env.add_reply(f"Unable to make an address for the account {account} for app usage.")
        return ""

def getAccountForAddress(env: Environment, address):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "listaddresses",
        "params": []
    }

    try:
        data = requests.post(env.env_vars.get("ZCASH_NODE_URL"), json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
        
        if "result" not in data:
            raise ValueError("Invalid response: missing 'result' key")
        
        list_addresses = data["result"]
        
        for wallet in list_addresses:
            if "unified" not in wallet:
                continue
            for account_info in wallet["unified"]:
                if "addresses" not in account_info or not isinstance(account_info["addresses"], list):
                    continue
                for addr in account_info["addresses"]:
                    if "address" in addr and addr["address"] == address:
                        return account_info["account"]
        
        return None  # Address not found
    
    except requests.exceptions.RequestException as e:
        env.add_reply(f"Request error: {e}")
        return None
    except ValueError as e:
        env.add_reply(f"JSON parsing error: {e}")
        return None

def getZcashIntentAccount(env: Environment):
    try:
        # Open the file in read mode first to check existing content
        with open(env.env_vars.get("ZCASH_ACCOUNT_FILE"), "r") as file:
            account = file.read().strip()
    except FileNotFoundError:
        account = -1

    # If account is empty or -1, create a new account
    if account == -1:
        account = createAccount(env)

    # Validate the account 
    try:
        zcash_account = account
    except ValueError:
        return -1

    # Check if account creation failed
    if zcash_account == -1:
        return -1

    # Open file in write mode to update the account
    with open(env.env_vars.get("ZCASH_ACCOUNT_FILE"), "w") as file:
        file.write(str(account))

    # Update environment variables

    return zcash_account

def validate_zcash_address(env: Environment, address):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_validateaddress",
        "params": [
            address
        ]
    }

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
    if not response["result"]["isvalid"]:
        return {"isvalid": response["result"]["isvalid"], "address_type": "invalid"}
    return {"isvalid": response["result"]["isvalid"], "address_type": response["result"]["address_type"]}

def wallet_balance(env: Environment):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "getwalletinfo",
        "params": []
    }

    node_url = env.env_vars.get("ZCASH_NODE_URL")
    response = requests.post(node_url, json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()
    return response["result"]["balance"], response["result"]["shielded_balance"]

def account_balance(env: Environment, account):
    username = env.env_vars.get("ZCASH_USER")
    password = env.env_vars.get("ZCASH_PASS")

    token_data = [obj for obj in data if obj["symbol"] == 'ZEC'][0]

    headers = {"Content-Type": "text/plain"}
    payload = {
        "jsonrpc": "1.0",
        "id": "curltest",
        "method": "z_getbalanceforaccount",
        "params": [int(account)]
    }

    response = requests.post(env.env_vars.get("ZCASH_NODE_URL"), json=payload, headers=headers, auth=HTTPBasicAuth(username, password)).json()

    balance_transparent = 0
    balance_shielded = 0

    if response["result"]:
        pools = response["result"]["pools"]

        if pools and "transparent" in pools and pools["transparent"]["valueZat"]:
            balance_transparent = Decimal(pools["transparent"]["valueZat"]) / (Decimal(10) ** int(token_data["decimals"]))

        if pools and "sapling" in pools and pools["sapling"]["valueZat"]:
            balance_shielded = Decimal(pools["sapling"]["valueZat"]) / (Decimal(10) ** int(token_data["decimals"]))

        if pools and "orchard" in pools and pools["orchard"]["valueZat"]:
            balance_shielded = balance_shielded + Decimal(pools["orchard"]["valueZat"]) / (Decimal(10) ** int(token_data["decimals"]))

    return balance_transparent, balance_shielded
