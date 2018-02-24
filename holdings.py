#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict, namedtuple
import functools as ft
import time

import ccxt

from private_variables import apis


def get_exchange(exchange, api_config):
    client = getattr(ccxt, exchange)(api_config)
    client.load_markets()
    return client


@ft.lru_cache()
def get_pairs(client):
    pairs = defaultdict(list)
    bi_pairs = defaultdict(list)
    for market in client.markets.values():
        quote = market['quote']
        base = market['base']
        pairs[quote].append(base)
        bi_pairs[quote].append(base)
        bi_pairs[base].append(quote)
    return pairs, bi_pairs


def get_symbol(sell, buy, client):
    pairs, bi_pairs = get_pairs(client)
    if buy not in bi_pairs[sell]:
        raise Exception(f"Market for {sell} to {buy} doesn't exist")

    if sell in pairs and buy in pairs[sell]:
        symbol = f'{buy}/{sell}'
        direction = 'asks'
    else:
        symbol = f'{sell}/{buy}'
        direction = 'bids'

    return symbol, direction


def get_orderbooks(client, symbols=None):
    orderbooks = {}
    for symbol, t in client.fetch_tickers().items():
        if symbols is not None and symbol not in symbols:
            continue

        if client.name == 'Binance':
            asks = [(float(t['ask']), float(t['askVolume']))]  # price, amount
            bids = [(float(t['bid']), float(t['bidVolume']))]  # price, amount
        else:
            orderbook = client.fetch_order_book(symbol)
            asks = orderbook['asks']
            bids = orderbook['bids']
        orderbooks[symbol] = dict(asks=asks, bids=bids, timestamp=time.time())
    return orderbooks


def get_price(symbol, direction, orderbooks):
    price, _ = orderbooks[symbol][direction][0]
    return price if direction == 'asks' else 1 / price


def get_price_via_btc(sell, orderbooks, units_of, client):
    """The price of `units_of` via BTC."""
    if sell == units_of:
        price = 1
    elif units_of == 'BTC':
        price = get_price(*get_symbol(sell, 'BTC', client), orderbooks)
    elif sell == 'BTC':
        price = get_price(*get_symbol(sell, units_of, client), orderbooks)
    else:
        price = (get_price(*get_symbol(sell, 'BTC', client), orderbooks)
                 * get_price(*get_symbol('BTC', units_of, client), orderbooks))
    return price


def get_balances(client):
    balances = client.fetch_balance()['free'].items()
    return {coin: amount for coin, amount in balances if amount > 0}


def dollar(exchange):
    if exchange in ['cex']:
        return 'USD'
    else:
        return 'USDT'


if __name__ == "__main__":
    total = 0
    for exchange, api_config in apis:
        usd = dollar(exchange)
        client = get_exchange(exchange, api_config)
        balances = get_balances(client)
        symbols = [get_symbol(coin, 'BTC', client)[0] for coin in list(balances.keys()) + [usd]
                   if coin != 'BTC']
        orderbooks = get_orderbooks(client, symbols)
        on_exchange = sum(amount / get_price_via_btc(coin, orderbooks, usd, client) for coin, amount in balances.items())
        total += on_exchange
        print(f"${on_exchange} on {exchange}")
    print('------------------------')
    print(f'${total} in total')
