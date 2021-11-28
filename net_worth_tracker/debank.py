from __future__ import annotations

from collections import defaultdict

import requests

from net_worth_tracker import coin_gecko, utils

renames = {
    "WBTC": "BTC",
    "WETH": "ETH",
    "WFTM": "FTM",
    "WMATIC": "MATIC",
    "am3CRV": "USDT",
    "amDAI": "DAI",
    "amUSDC": "USDC",
    "amUSDT": "USDT",
    "amWBTC": "BTC",
    "amWETH": "ETH",
    "amWMATIC": "MATIC",
    "camWBTC": "BTC",
}


def get_debank(address: str | None = None, chains=("matic", "avax", "ftm", "bsc")):
    if address is None:
        address = utils.get_password("my_address", "metamask")
    responses = []
    for chain in chains:
        url = f"https://openapi.debank.com/v1/user/complex_protocol_list?id={address}&chain_id={chain}"
        responses.extend(requests.get(url).json())
    return responses


def parse_response(responses):
    balances = []
    for platform_dict in responses:
        for portfolio_item in platform_dict["portfolio_item_list"]:
            detail = portfolio_item["detail"]
            for key in ["supply_token_list", "token_list", "borrow_token_list"]:
                if key in detail:
                    infos = detail[key]
                    for info in infos:
                        balance = dict(
                            platform=platform_dict["id"],
                            symbol=renames.get(info["symbol"], info["symbol"]),
                            amount=info["amount"],
                            price=info["price"],
                            value=info["amount"] * info["price"],
                        )
                        if key == "borrow_token_list":
                            balance["value"] *= -1
                            balance["amount"] *= -1
                        balances.append(balance)

    prices = coin_gecko.get_prices({bal["symbol"] for bal in balances})

    # 1 amWETH ≠ 1 ETH, so calibrate the amount of coins by using the value
    balances_calibrated = []
    for balance in balances:
        balance = balance.copy()
        balance["value"] *= utils.euro_per_dollar()
        symbol = balance["symbol"]
        if symbol in prices:
            price = prices[symbol]
            balance["amount"] = balance["value"] / price
            balance["price"] = price
        else:
            # Price from DeBank is in USD
            balance["price"] *= utils.euro_per_dollar()
        balances_calibrated.append(balance)

    # Check that total value is still the same
    tot_balances = sum(x["value"] for x in balances) * utils.euro_per_dollar()
    tot_balances_calibrated = sum(x["value"] for x in balances_calibrated)
    assert abs(tot_balances - tot_balances_calibrated) < 1e-8

    # Combine coins from different platforms
    balances2 = defaultdict(list)
    for balance in balances_calibrated:
        balance = balance.copy()
        platform = balance.pop("platform")
        symbol = balance.pop("symbol")
        balances2[platform].append({symbol: balance})
    balances2 = dict(balances2)
    balances_final = {
        platform: utils.combine_balances(*_balances)
        for platform, _balances in balances2.items()
    }
    return balances_final


def get_balances(address: str | None = None, chains=("matic", "avax", "ftm", "bsc")):
    responses = get_debank(address, chains)
    return parse_response(responses)
