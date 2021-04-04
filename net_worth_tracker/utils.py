from configparser import ConfigParser
from pathlib import Path

import keyring

DEFAULT_CONFIG = Path("~/.config/crypto_etf.conf").expanduser()


def get_password(username: str, service: str):
    pw = keyring.get_password(service, username)
    if not pw:
        raise Exception(f"python -m keyring set {service} {username}")
    return pw


def read_config(path: Path = DEFAULT_CONFIG):
    """Create a config file at ~/.config/crypto_etf.conf with the
    following information and structure:
        [binance]
        api_key = ...
        api_secret = ...

        [bsc]
        address = ...

        [bscscan]
        api_key = ...

    Uses https://docs.python.org/3/library/configparser.html
    """
    config = ConfigParser()
    config.read(DEFAULT_CONFIG)
    if config == []:
        print(
            "Create a config file at ~/.config/crypto_etf.conf with api keys \
            according to configparser."
        )
    return config
