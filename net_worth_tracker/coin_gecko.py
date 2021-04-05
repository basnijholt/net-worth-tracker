from collections import defaultdict

from pycoingecko import CoinGeckoAPI

from net_worth_tracker.utils import euro_per_dollar


def get_coins(balances, cg: CoinGeckoAPI):
    sym2name = {  # mapping for duplicates
        "auto": "Auto",
        "bifi": "Beefy.Finance",
        "uni": "Uniswap",
        "one": "Harmony",
        "onx": "OnX Finance",
        "bunny": "Pancake Bunny",
    }
    symbols = [c.lower() for c in balances]

    coin_list = cg.get_coins_list()

    # Check for duplicate symbols in coin list
    symbol_map = defaultdict(list)
    for c in coin_list:
        symbol_map[c["symbol"]].append(c)
    duplicates = {symbol for symbol, lst in symbol_map.items() if len(lst) > 1}
    duplicates = duplicates.intersection(symbols)
    unknown_duplicates = duplicates.difference(sym2name.keys())
    for symbol in unknown_duplicates:
        raise ValueError(
            f"{symbol} appears twice! Edit `sym2name`. "
            f"Use one of:\n{symbol_map[symbol]}."
        )
    sym2id = {}
    id2sym = {}
    for c in coin_list:
        symbol = c["symbol"].lower()
        if symbol in duplicates and c["name"] != sym2name[symbol]:
            continue
        sym2id[symbol] = c["id"]
        id2sym[c["id"]] = symbol.upper()
    return sym2id, id2sym


def get_prices(balances):
    cg = CoinGeckoAPI()
    sym2id, id2sym = get_coins(balances, cg)
    ids = {sym2id[c.lower()] for c in balances if c.lower() in sym2id}
    ids.add(sym2id["busd"])
    prices = cg.get_price(ids=list(ids), vs_currencies="eur")
    prices = {id2sym[k]: v["eur"] for k, v in prices.items()}
    return prices


def add_value_and_price(balances, ignore=("degiro", "brand_new_day")):
    renames = {"IOTA": "MIOTA"}
    renames_reverse = {v: k for k, v in renames.items()}

    to_fetch = set()
    for where, bals in balances.items():
        for coin, bal in bals.items():
            if "value" not in bal and where not in ignore:
                to_fetch.add(renames.get(coin, coin))

    to_fetch.discard("EUR")
    prices = get_prices(to_fetch)
    prices = {renames_reverse.get(coin, coin): price for coin, price in prices.items()}

    for where, bals in balances.items():
        for coin, bal in bals.items():
            if "value" not in bal and where not in ignore:
                if coin == "EUR":
                    price = 1
                elif coin in prices:
                    price = prices[coin]
                elif coin == "Belt-Venus-BLP":
                    # Mixture of USD stable coins, so assume BUSD
                    price = euro_per_dollar()
                else:
                    print(f"Fuck, no data for {coin}")
                    continue
                bal["price"] = price
                bal["value"] = bal["amount"] * price
