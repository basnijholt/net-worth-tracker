from collections import defaultdict
from functools import lru_cache
from typing import Optional

from bscscan import BscScan
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait

from net_worth_tracker.utils import read_config


@lru_cache
def get_bep20_balances(my_address: Optional[str] = None, api_key: Optional[str] = None):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    if api_key is None:
        api_key = config["bscscan"]["api_key"]

    bsc = BscScan(api_key)
    my_address = my_address.lower()
    txs = bsc.get_bep20_token_transfer_events_by_address(
        address=my_address, startblock=0, endblock=999999999, sort="asc"
    )
    balances = defaultdict(float)
    for d in txs:
        if d["to"].lower() == my_address:
            # Incoming tokens
            sign = +1
        else:
            sign = -1
        balances[d["tokenSymbol"]] += sign * float(d["value"]) / 1e18

    # Get BNB balance
    balances["BNB"] += float(bsc.get_bnb_balance(address=my_address)) / 1e18

    # Remove 0 or negative balances
    # TODO: why can it become negative?
    balances = {k: v for k, v in balances.items() if v > 0}
    renames = {"Belt.fi bDAI/bUSDC/bUSDT/bBUSD": "BUSD"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)

    return balances


@lru_cache
def scrape_yieldwatch(
    my_address: Optional[str] = None, headless=True, timeout: int = 30
):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    with webdriver.Chrome(options=chrome_options) as driver:
        WebDriverWait(driver, timeout)
        driver.get("https://www.yieldwatch.net/")
        for letter in my_address:
            address_bar = driver.find_element_by_id("addressInputField")
            address_bar.send_keys(letter)

        icon_bar = driver.find_element_by_class_name("centered.bottom.aligned.row")
        buttons = icon_bar.find_elements_by_class_name("center.aligned.column")
        for button in buttons:
            grayscale = button.find_element_by_class_name(
                "ui.centered.image"
            ).value_of_css_property("filter")
            if grayscale == "grayscale(1)":
                button.click()

        button = driver.find_element_by_class_name("binoculars")
        button.click()

        # Wait until the next page is loaded
        element_present = presence_of_element_located((By.CLASS_NAME, "content.active"))
        WebDriverWait(driver, timeout).until(element_present)

        infos = defaultdict(dict)
        segments = driver.find_elements_by_class_name("ui.segment")
        for segment in segments:
            # Many elements have the "ui segment" class, only pick the ones with
            # the "accordion ui" style.
            for defi in segment.find_elements_by_class_name("accordion.ui"):
                boxes = defi.find_elements_by_class_name("ui.equal.width.grid")
                if not boxes:
                    continue
                which = defi.text.split("\n")[0]
                for box in boxes:
                    header, content = box.find_elements_by_class_name("row")
                    box_name = header.text.split("\n")[0]
                    # Get the columns in the box, only the first two are relevant
                    columns = content.find_elements_by_class_name(
                        "collapsing.right.aligned"
                    )
                    names = columns[0].text.split("\n")
                    amounts = columns[1].text.split("\n")
                    d = defaultdict(list)
                    for i, amount in enumerate(amounts):
                        amount, coin = amount.split(" ", 1)
                        name = names[min(i, len(names) - 1)]
                        d[name].append((float(amount), coin))
                    infos[which][box_name] = dict(d)
    return dict(infos)


def yieldwatch_to_balances(yieldwatch):
    vault_coin_mapping = {
        "BELT-BNB BELT LP": "BELT-BNB-LP",
        "Belt Venus BLP": "Belt-Venus-BLP",
        "AUTO-WBNB Pool": "AUTO-WBNB-LP",
    }
    coin_renames = {"Cake": "CAKE", "sBDO": "SBDO"}
    balances = defaultdict(float)
    for defi, vaults in yieldwatch.items():
        for vault, info in vaults.items():
            for (type_, amount_coin_list) in info.items():
                if type_ == "Harvest":
                    # is already taken into account in wallet balance
                    continue
                for amount, coin in amount_coin_list:
                    norm_coin = vault_coin_mapping.get(vault, coin)
                    norm_coin = coin_renames.get(norm_coin, norm_coin)
                    balances[norm_coin] += float(amount)
    return dict(balances)