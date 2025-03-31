import requests
import swap
import utils
from nearai.agents.environment import Environment
import json
from decimal import Decimal


class TradingStrategy:
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name

    def get_price(self, token: str) -> float:
        
        with open("tokens.json", "r") as file:
            data = json.load(file)

        id = token
        for token_data in data:
            if token_data["symbol"] == token.upper():
                id = token_data["cgId"]      
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={id}&vs_currencies=usd"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            val = response.json().get(id, {}).get("usd", 0)
            return Decimal(val)
        except Exception as e:
            raise ValueError(f"Error fetching price for {token}: {e}") 
    async def execute(self, env: Environment):  
        # Execute the strategy: Swap all tokens to ZEC if ZEC price > 34 USD.
        zec_price = self.get_price("ZEC")
        if zec_price > 34:
            # Fetch wallet balances
            balances = await utils._wallet_balance(env, env.env_vars.get("ACCOUNT_ID", None))
            for balance in balances:
                if balance["symbol"] == "USDT" or balance["symbol"] == "ETH":
                    token_in = balance["symbol"]
                    amount_in = balance["balance"]
                    token_out = "ZEC"
                    print(f"Swapping {amount_in} {token_in} for {token_out} at ${zec_price}")
                    await swap.swap(env, token_in, amount_in, token_out, env.env_vars.get("ACCOUNT_ID", None))
        else:
            print(f"No swap needed. Current ZEC price: ${zec_price}")