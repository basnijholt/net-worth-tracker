import json

import requests

from .utils import get_password

BASE_URL = "https://wallet-api.celsius.network"


def get_headers(api_key, partner_key):
    return {
        "X-Cel-Api-Key": api_key,  # get via the app
        "X-Cel-Partner-Token": partner_key,  # need to request via email to partners@celsius.network
    }


def get_headers_from_keyring():
    api_key = get_password("api_key", "celsius")
    partner_key = get_password("partner_key", "celsius")
    return get_headers(api_key, partner_key)


def parse_response(response):
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        return response


def get_balance(headers):
    response = requests.get(BASE_URL + "/wallet/balance", headers=headers)
    return parse_response(response)


def get_interest(headers):
    response = requests.get(BASE_URL + "/wallet/interest", headers=headers)
    return parse_response(response)


def get_stats(headers):
    response = requests.get(BASE_URL + "/util/statistics?timestamp=", headers=headers)
    return parse_response(response)


def get_transactions(headers, pages):
    response = requests.get(
        BASE_URL + "/wallet/transactions",
        headers=headers,
        params=pages,
    )
    return parse_response(response)
