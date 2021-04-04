import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import text_to_be_present_in_element
from selenium.webdriver.support.ui import WebDriverWait

from .utils import get_password


def scrape_nexo_csv(
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout=30,
):
    if username is None:
        username = get_password("username", "nexo")
    if password is None:
        password = get_password(username, "nexo")

    chrome_options = Options()

    with webdriver.Chrome(options=chrome_options) as driver:

        # Login
        driver.get("https://platform.nexo.io/")
        element_present = text_to_be_present_in_element(
            (By.CLASS_NAME, "Modal.FormLogin"), "Login"
        )
        WebDriverWait(driver, timeout).until(element_present)

        username_bar, password_bar = driver.find_elements_by_tag_name("input")
        username_bar.send_keys(username)
        password_bar.send_keys(password)

        continue_button = next(
            b for b in driver.find_elements_by_tag_name("button") if "Login" in b.text
        )
        continue_button.click()

        # Manually add 2FA and login!

        # Wait until page is loaded
        element_present = text_to_be_present_in_element(
            (By.TAG_NAME, "nav"), "Transactions"
        )
        wait = WebDriverWait(driver, 60)
        wait.until(element_present)

        transactions_button = next(
            s
            for s in driver.find_elements_by_tag_name("span")
            if "Transaction" in s.text
        )
        transactions_button.click()

        element_present = text_to_be_present_in_element(
            (By.CLASS_NAME, "text"), "Export"
        )
        wait = WebDriverWait(driver, 5)
        wait.until(element_present)

        export_button = next(
            b for b in driver.find_elements_by_tag_name("button") if "Export" in b.text
        )
        fname = Path("~/Downloads/nexo_transactions.csv").expanduser()
        if fname.exists():
            fname.unlink()
        export_button.click()
        for _ in range(10):
            time.sleep(1)
            if fname.exists():
                print(f"Downloaded {fname}")
                return
        print("Didn't download the file")


@lru_cache
def get_nexo_balances(
    csv_fname: str = "~/Downloads/nexo_transactions.csv",
):
    print("Download csv from https://platform.nexo.io/transactions")
    df = pd.read_csv(csv_fname)
    summed = df[df.Type == "Deposit"].groupby("Currency").sum("Amount")
    balances = {i: row.Amount for i, row in summed.iterrows()}
    renames = {"NEXOBEP2": "NEXO"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)
    nexo = df[df.Type == "Interest"].groupby("Currency").sum("Amount")
    assert len(nexo) == 1
    balances["NEXO"] = balances.get("NEXO", 0) + nexo.iloc[0].Amount
    return balances


if __name__ == "__main__":
    scrape_nexo_csv()
