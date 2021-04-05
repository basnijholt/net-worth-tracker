import glob
import json
from collections import defaultdict


def convert_file(fname):
    with open(fname) as f:
        data = json.load(f)
    new_balances = {}
    renames = {"trust": "bep20"}
    amounts = defaultdict(float)
    for where, bals in data["balances_per_category"].items():
        for coin, amount in bals.items():
            amounts[coin] += amount
    values = data["eur_balances"]
    prices = {coin: values[coin] / amounts[coin] for coin in amounts if coin in values}

    for where, bals in data["balances_per_category"].items():
        new_bals = {}
        for coin, amount in bals.items():
            new_bal = dict(amount=amount)
            if coin in prices:
                new_bal["price"] = prices[coin]
                new_bal["value"] = prices[coin] * amount
            new_bals[coin] = new_bal
        new_balances[renames.get(where, where)] = new_bals
    new_data = {"balances": new_balances, "defi": data["defi"]}
    with open(fname, "w") as f:
        json.dump(new_data, f, indent="  ")


for fname in glob.glob("data/*json"):
    try:
        convert_file(fname)
    except Exception:
        print(fname)
