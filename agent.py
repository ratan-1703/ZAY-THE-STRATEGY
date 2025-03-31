import asyncio
import base64
from datetime import datetime, timedelta
from urllib.parse import quote

import json
import time
import requests

import utils
import zcash

from nearai.agents.agent import Agent
from nearai.agents.environment import Environment

from rich.console import Console
from rich.markdown import Markdown
import strategy
import sys

from intents.deposit import _deposit_to_intents
from intents.swap import intent_swap
from intents.withdraw import withdraw_from_intents
from io import StringIO

# env:Environment = Environment()

console = Console()

with open("tokens.json", "r") as file:
    data = json.load(file)

with open("env.json", "r") as file:
    env_vars = json.load(file)
    if not env_vars["ACCOUNT_ID"] or not env_vars["PRIVATE_KEY"] or not env_vars["ZCASH_NODE_URL"] or not env_vars["CODE_DIR"]:
        print("Please set ACCOUNT_ID, PRIVATE_KEY, ZCASH_NODE_URL, CODE_DIR in env file")
        sys.exit(1)
    
    if not env_vars["ZCASH_USER"] or not env_vars["ZCASH_PASS"] or not env_vars["ZCASH_ACCOUNT_FILE"] or not env_vars["CODE_DIR"]:
        print("Please set ZCASH_USER, ZCASH_PASS, ZCASH_ACCOUNT_FILE in env file")
        sys.exit(1)
    
    if not env_vars["ZCASH_ADDRESS"] :
        print("Please set ZCASH_ADDRESS in env file")
        sys.exit(1)
    
    env.env_vars.update(env_vars)

def get_all_tokens():
    """Gets all the tokens supported with relevant metadata. Use this tool to get the tokens supported. This tool is not intended for direct calls by users."""
    data = utils.load_url("https://api-mng-console.chaindefuser.com/api/tokens")
    return data["items"]

def wallet_balance(accountId = env.env_vars.get("ACCOUNT_ID", "")):
   
    """ Request Handling for Wallet Balance
        Specific Wallet Balance Request: If the user explicitly requests a wallet balance and does not intend to check the balance from the Defuse/Intents contract, call this tool.
        Account ID Handling: If the user provides an account ID (words like 'my' etc are not account id), set the accountId parameter to the provided ID. 
        Ambiguous Request: If the user simply types "balance" or you are unsure about their intent, ask them if they want to check their wallet balance. If they confirm, proceed with calling this tool.
    """
    accountId = accountId if ((accountId != "") or (accountId != None)) else  env.env_vars.get("ACCOUNT_ID", "")
    with console.status(f"[bold green]Getting Wallet Balance...[/bold green]"):
        token_balances = asyncio.run(utils._wallet_balance(env, accountId))
    utils.reply_with_markdown(env, token_balances, f"wallet balance of {accountId}")
    
    
def Intents_balance(accountId = env.env_vars.get("ACCOUNT_ID", "")):
    
    """Request Handling for Intents Balance
        Specific Intents Balance Request: If the user explicitly requests a Intents/Defuse balance and does not intend to check the balance from the wallet, call this tool.
        Account ID Handling: If the user provides an account ID (words like 'my' etc are not account id), set the accountId parameter to the provided ID. 
        Ambiguous Request: If the user simply types "balance" or you are unsure about their intent, ask them if they want to check their Intents balance. If they confirm, proceed with calling this tool.
    """
    
    accountId = accountId if ((accountId != "") or (accountId != None)) else  env.env_vars.get("ACCOUNT_ID", "")
    with console.status(f"[bold green]Getting Intents Balance...[/bold green]"):
        token_balances = asyncio.run(utils._Intents_balance(env, accountId))
        
    utils.reply_with_markdown(env, token_balances, f"Intents balance of {accountId}")

def deposit_to_intents(amount, token_symbol="", sender = env.env_vars.get("ACCOUNT_ID", None)):
    
    """Always re-ask for user confirmation regarding the amount and the token before calling the tool each time. This tool deposits a token to the intents contract. You can call this tool if user asks to deposit into defuse/intents contract, after user confirmation regarding the amount and the token. Take the amount and token symbol from the user, and call this tool."""

    
    if token_symbol.upper() == "ZEC":
        if (sender == env.env_vars.get("ACCOUNT_ID", None)):
            sender = env.env_vars.get("ZCASH_ADDRESS", None)
        sender = sender if sender != "" else  env.env_vars.get("ZCASH_ADDRESS", None)
    else:    
        sender = sender if sender != "" else  env.env_vars.get("ACCOUNT_ID", None)
        
    with console.status(f"[bold green]Depositing {amount} {token_symbol}... This may take up to 15 minutes.[/bold green]"):
        asyncio.run(_deposit_to_intents(env, data, amount, sender, token_symbol))

    

def swap_in_intents(token_in, amount_in, token_out):
    """Always re-ask for user confirmation regarding the amount and the token-in and token-out before calling the tool each time. This tool swaps token-in to token-out inside defuse/intents. Remember, this is a swap inside intents, and not a swap in the user's wallet. You can call this tool if user asks to swap inside defuse/intents contract, after user confirmation regarding the amount-in, token-in and token-out. Take the amount and token symbols from the user, and call this tool."""
    with console.status(f"[bold green]Swapping {amount_in} {token_in} to {token_out}...[/bold green]"):
        asyncio.run(intent_swap(env, token_in, token_out, amount_in, data))

def _withdraw_from_intents(amount, token_symbol="", receiverId = env.env_vars.get("ACCOUNT_ID", None)):
    """Before calling the tool, always reconfirm with the user regarding the amount and token they want to withdraw. If the user requests a withdrawal from the defuse/intents contract, explicitly ask for confirmation on the amount and token symbol before proceeding.

    Additionally, verify the receiver account ID:
    If the user provides a receiver id, then set reciverId to that
    Only after receiving explicit confirmation on these details should you proceed with calling the tool."""
    

    with console.status(f"[bold green]Withdrawing {amount} {token_symbol}... This may take up to 15 minutes.[/bold green]"):    
        if token_symbol.upper() == "ZEC":
            if (receiverId == env.env_vars.get("ACCOUNT_ID", None)):
                receiverId = env.env_vars.get("ZCASH_ADDRESS", None)
                
            receiverId = receiverId if receiverId else  env.env_vars.get("ZCASH_ADDRESS", None)
            asyncio.run(zcash.withdraw(env, token_symbol, amount, receiverId, data))
            return
            
        receiverId = receiverId if receiverId else  env.env_vars.get("ACCOUNT_ID", None)
        asyncio.run(withdraw_from_intents(env, token_symbol, amount, receiverId, data))

def swap(token_in, amount_in, token_out, receiverId = env.env_vars.get("ACCOUNT_ID", None), sender = env.env_vars.get("ACCOUNT_ID", None)):
    """Before calling the tool, always reconfirm with the user regarding the amount and token they want to swap. This tool swaps token-in to token-out in the user's wallet. It deposits, then swaps and then withdraws to the withdrawal address. This is not to be called if the swap is in the intents contract."""
    
    with console.status(f"[bold green]Depositing {amount_in} {token_in}... This may take up to 15 minutes.[/bold green]"):
        if token_in.upper() == "ZEC":
            if (sender == env.env_vars.get("ACCOUNT_ID", None)):
                sender = env.env_vars.get("ZCASH_ADDRESS", None)
            sender = sender if sender != "" else  env.env_vars.get("ZCASH_ADDRESS", None)

        else:    
            sender = sender if sender != "" else  env.env_vars.get("ACCOUNT_ID", None)
        asyncio.run(_deposit_to_intents(env, data, amount_in, sender, token_in))

    with console.status(f"[bold green]Swapping {amount_in} {token_in} to {token_out}...[/bold green]"):
        amount = asyncio.run(intent_swap(env, token_in, token_out, amount_in, data))


    with console.status(f"[bold green]Withdrawing {amount} {token_out}... This may take up to 15 minutes.[/bold green]"):    
        if token_out.upper() == "ZEC":
            receiverId = receiverId if receiverId else  env.env_vars.get("ZCASH_ADDRESS", None)
            if (receiverId == env.env_vars.get("ACCOUNT_ID", None)):
                receiverId = env.env_vars.get("ZCASH_ADDRESS", None)
                
            asyncio.run(zcash.withdraw(env, token_out, amount, receiverId, data))
            return

        receiverId = receiverId if receiverId != "" else  env.env_vars.get("ACCOUNT_ID", None)
        asyncio.run(withdraw_from_intents(env, token_out, amount, receiverId, data))

    
def write_strategy(strategy_code):
    
    """
    This is "write_strategy" tool.
    When the user provides a strategy, this function writes the strategy code to a file named 'strategy.py'.
    
    This function should be called after obtaining the strategy from the user 
    and converting it into Python code. 

    Args:
        strategy_code (str): The Python code representing the user's strategy.

    Behavior:
        - Writes the provided strategy code to 'strategy.py'.
        - Confirms the successful formulation of the strategy.

    """
    with console.status(f"[bold green]Formulating Strategy and building plans...[/bold green]"):    
        env.write_file("/home/dc/.nearai/registry/dc1312.near/ZEC-Intents-Trading-Agent/0.0.1/strategy.py", strategy_code)
        utils.reply_with_markdown(env, True, f"Strategy has been formulated. Ask user now whether user want to execute his strategy. If user confirms call the tool 'execute_strategy'. ")
    
    
def execute_strategy():
    
    """
    This is "execute_strategy" tool.
    This tool is called when user ask for execution of the strategy.
    Executes the strategy code. This is the tool that should be called when the user confirms execution of the strategy. 

    Behavior:
        - Executes the user strategy.
        - Should only be invoked when the user requests to execute the strategy.

    """
    with console.status(f"[bold green]Executing Strategy...[/bold green]"):    
        st = strategy.TradingStrategy("ZEC-Intents-Trading-Agent")
        asyncio.run(st.execute(env))
        utils.reply_with_markdown(env, True, f"Staregy has been executed. Can you help in anything else?")


def run(env: Environment):
    
    tool_registry = env.get_tool_registry(new=True)
    tool_registry.register_tool(deposit_to_intents)
    tool_registry.register_tool(swap_in_intents)
    tool_registry.register_tool(_withdraw_from_intents)
    tool_registry.register_tool(wallet_balance)
    tool_registry.register_tool(Intents_balance)
    tool_registry.register_tool(swap)
    tool_registry.register_tool(write_strategy)
    tool_registry.register_tool(execute_strategy)
    
    user = env.env_vars.get("ACCOUNT_ID", "NEAR_ACCOUNID_NOT_IN_ENV")
    zec_address = env.env_vars.get("ZCASH_ADDRESS", "NEAR_ACCOUNID_NOT_IN_ENV")
    
    messages = [{"role": "system", "content": utils.main_prompt}, {"role": "user", "content": f"Do only what I say. The thread is in terminal. My near account address is {user}. My ZEC Address is {zec_address}"}] + env.list_messages()
    
    all_tools = env.get_tool_registry().get_all_tool_definitions()
    reply = env.completions_and_run_tools(messages, tools=all_tools, add_responses_to_messages=False)
    message = reply.choices[0].message
    (message_without_tool_call, tool_calls) = env._parse_tool_call(message)
    if message_without_tool_call:
        console = Console()
        md = Markdown(message_without_tool_call)

        with StringIO() as buf:
            console.file = buf
            console.print(md)
            env.add_reply(buf.getvalue())


run(env)
