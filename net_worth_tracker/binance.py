from collections import defaultdict
from functools import lru_cache

from binance.client import Client
from binance.exceptions import BinanceAPIException

from .utils import read_config


def get_binance_client() -> Client:
    config = read_config()["binance"]
    return Client(config["api_key"], config["api_secret"])


@lru_cache
def get_binance_balances():
    client = get_binance_client()
    balances = defaultdict(float)

    def normalize(coin):
        return coin if not coin.startswith("LD") else coin[2:]

    # Get wallet and savings
    latest_info = max(
        client.get_account_snapshot(type="SPOT")["snapshotVos"],
        key=lambda x: x["updateTime"],
    )["data"]
    for d in latest_info["balances"]:
        amount = float(d["free"]) + float(d["locked"])
        if amount > 0:
            balances[normalize(d["asset"])] += amount

    # Add Liquidity pool shares
    uri = "https://api.binance.com/sapi/v1/bswap/liquidity"
    try:
        pools = client._request("get", uri, True, data=dict())
    except BinanceAPIException:  # not sure why it happens...
        pass
    else:
        assets = [p["share"]["asset"] for p in pools]
        for d in assets:
            for coin, amount in d.items():
                amount = float(amount)
                if amount > 0:
                    balances[coin] += amount

    return dict(balances)
