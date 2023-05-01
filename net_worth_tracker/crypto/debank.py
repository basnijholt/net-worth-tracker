from __future__ import annotations

from collections import defaultdict
from typing import Literal

import requests

from net_worth_tracker import coin_gecko, utils

DEFAULT_CHAINS = ("matic", "avax", "ftm", "bsc")

RENAMES = {
    "WBTC": "BTC",
    "WETH": "ETH",
    "WFTM": "FTM",
    "WMATIC": "MATIC",
    "am3CRV": "USDC",
    "amDAI": "DAI",
    "amUSDC": "USDC",
    "amUSDT": "USDT",
    "amWBTC": "BTC",
    "amWETH": "ETH",
    "amWMATIC": "MATIC",
    "camWBTC": "BTC",
}


def get_debank(
    address: str | None = None,
    chains=DEFAULT_CHAINS,
    which: Literal["defi", "wallet"] = "defi",
):
    if address is None:
        address = utils.get_password("my_address", "metamask")
    responses = []
    base = "https://openapi.debank.com/v1/user"
    if which == "wallet":
        url = "{base}/token_list?id={address}&chain_id={chain}&is_all=false&has_balance=true"
    elif which == "defi":
        url = "{base}/complex_protocol_list?id={address}&chain_id={chain}"

    for chain in chains:
        _url = url.format(base=base, address=address, chain=chain)
        responses.extend(requests.get(_url).json())
    return responses


def parse_defi_response(responses, calibrate: bool = True, **extra_renames):
    renames = RENAMES.copy()
    renames.update(extra_renames)
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
        if (symbol in prices) and calibrate:
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


def parse_wallet_responses(responses):
    return utils.combine_balances(
        *[
            {
                RENAMES.get(x["symbol"], x["symbol"]): {
                    "amount": x["amount"],
                    "price": x["price"] * utils.euro_per_dollar(),
                    "value": x["price"] * x["amount"] * utils.euro_per_dollar(),
                }
            }
            for x in responses
        ]
    )


def get_debank_balances(address: str | None = None, chains=DEFAULT_CHAINS):
    defi_responses = get_debank(address, chains, "defi")
    wallet_responses = get_debank(address, chains, "wallet")
    balances = parse_defi_response(defi_responses)
    balances["defi_wallet"] = parse_wallet_responses(wallet_responses)
    return balances
