from functools import lru_cache

import js2py
import requests
from web3 import HTTPProvider, Web3

from net_worth_tracker.utils import euro_per_dollar

# from https://github.com/beefyfinance/beefy-app/blob/edbf199aee36728f06e16c05af1a2af36475f068/src/common/networkSetup.js
RPCS = {
    "bsc": "https://bsc-dataseed.binance.org",
    "heco": "https://http-mainnet.hecochain.com",
    "avalanche": "https://api.avax.network/ext/bc/C/rpc",
    "polygon": "https://polygon-rpc.com",
    "fantom": "https://rpc.ftm.tools",
    "harmony": "https://api.s0.t.hmny.io/",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "celo": "https://forno.celo.org",
    "moonriver": "https://rpc.moonriver.moonbeam.network",
}

GITHUB_RAW = "https://raw.githubusercontent.com/beefyfinance/beefy-app/master"


@lru_cache
def get_abis():
    # Get ABIs for Beefy
    r = requests.get(f"{GITHUB_RAW}/src/features/configure/abi.js")

    abis = {}
    for line in r.text.split("\n"):
        name, js = line.split(" = ")
        name = name.replace("export const ", "")
        abis[name] = js2py.eval_js(js).to_list()
    return abis


@lru_cache
def get_prices():
    oracles = {
        "lps": requests.get("https://api.beefy.finance/lps").json(),
        "tokens": requests.get("https://api.beefy.finance/prices").json(),
    }
    return oracles


@lru_cache
def get_pools():
    networks = [
        "arbitrum",
        "avalanche",
        "bsc",
        "celo",
        "fantom",
        "harmony",
        "heco",
        "moonriver",
        "polygon",
    ]
    base = GITHUB_RAW + "/src/features/configure/vault/{name}_pools.js"
    pools = {}
    for network in networks:
        r = requests.get(base.format(name=network))
        text = r.text.split(" = ")
        assert len(text) == 2
        lst = js2py.eval_js(text[1]).to_list()
        pools[network] = {info["id"]: info for info in lst}
    return pools


def get_from_blockchain(vault):
    w3 = Web3(
        HTTPProvider(
            endpoint_uri=RPCS[vault["chain"]],
            request_kwargs={"timeout": 10},
        )
    )
    ID = vault["id"]
    pool = get_pools()[vault["chain"]][ID]
    c = w3.eth.contract(
        pool["earnContractAddress"],
        abi=get_abis()[vault["abi"]],
    )
    balance = c.caller.balanceOf(vault["my_address"]) * c.caller.getPricePerFullShare()
    decimals = c.caller.decimals()
    balance /= (10 ** decimals) ** 2
    prices = get_prices()
    price = prices[pool["oracle"]][pool["oracleId"]]
    value = balance * price * euro_per_dollar()
    return {"amount": balance, "value": value, "price": price}
