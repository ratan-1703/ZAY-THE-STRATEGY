import base64
import hashlib
import json
import secrets
import time
from typing import Any, List, Optional, Union
from decimal import Decimal

import base58
import nacl.signing
import requests
from nearai.agents.environment import Environment

# from py_near.account import Account
from borsh_construct import U32
from serializer import BinarySerializer
from zcash.zcash import withdraw
from py_near.constants import DEFAULT_ATTACHED_GAS

from intents.deposit import _deposit_to_intents
from intents.swap import intent_swap
from intents.withdraw import withdraw_from_intents

default_mainnet_rpc = "https://rpc.mainnet.near.org"

import re

with open("tokens.json", "r") as file:
    data = json.load(file)

INTENTS_CONTRACT = "intents.near"
url = "https://solver-relay-v2.chaindefuser.com/rpc"

headers = {
    "Content-Type": "application/json"
}

ED_PREFIX = "ed25519:"  

FT_DEPOSIT_GAS = 30000000000000
FT_TRANSFER_GAS = 50000000000000
FT_MINIMUM_STORAGE_BALANCE_LARGE = 1250000000000000000000

async def swap(env, token_in, amount_in, token_out, receiverId):
    receiverId = receiverId if receiverId else  env.env_vars.get("ACCOUNT_ID", None)
    if token_in.upper() == "ZEC":
        if (receiverId == env.env_vars.get("ACCOUNT_ID", None)):
            receiverId = env.env_vars.get("ZCASH_ADDRESS", None)
        
        receiverId = receiverId if receiverId else  env.env_vars.get("ZCASH_ADDRESS", None)
    
    await _deposit_to_intents(env, data, amount_in, receiverId, token_in)
    amount = await intent_swap(env, token_in, token_out, amount_in, data)

    if token_out.upper() == "ZEC":
        if (receiverId == env.env_vars.get("ACCOUNT_ID", None)):
            receiverId = env.env_vars.get("ZCASH_ADDRESS", None)
        
        receiverId = receiverId if receiverId else  env.env_vars.get("ZCASH_ADDRESS", None)
        await withdraw(env, token_out, amount, receiverId, data)
        return
        
    receiverId = receiverId if receiverId else  env.env_vars.get("ACCOUNT_ID", None)
    await withdraw_from_intents(env, token_out, amount, receiverId, data)
