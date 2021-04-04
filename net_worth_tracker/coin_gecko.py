from collections import defaultdict

from pycoingecko import CoinGeckoAPI


def get_coins(balances, cg: CoinGeckoAPI):
    sym2name = {  # mapping for duplicates
        "auto": "Auto",
        "bifi": "Beefy.Finance",
        "uni": "Uniswap",
        "one": "Harmony",
        "onx": "OnX Finance",
        "bunny": "Pancake Bunny",
    }
    symbols = [c.lower() for c in balances.keys()]

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


def get_balances_in_euro(balances):
    balances = balances.copy()
    renames = {"IOTA": "MIOTA"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)

    prices = get_prices(balances)
    eur_balances = {}
    for coin, amount in balances.items():
        if coin in prices:
            eur_balances[coin] = prices[coin] * amount
        elif coin == "EUR":
            eur_balances[coin] = amount
        elif coin == "Belt-Venus-BLP":
            # Mixture of USD stable coins, so assume BUSD
            eur_balances[coin] = prices["BUSD"] * amount
        else:
            print(f"Fuck, no data for {coin}")

    # Rename back
    for old, new in renames.items():
        if new in eur_balances:
            eur_balances[old] = eur_balances.pop(new)
    return dict(sorted(eur_balances.items(), key=lambda x: x[1], reverse=True))
