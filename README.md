# simple `crypto-tracker`
**See your current portofolio balance without the hassle.**

Can extract crypto portfolio data from:
- Nexo.io
- BlockFi
- Binance Smart Chain (BEP20 tokens + DeFi via [YieldWatch.net](YieldWatch.net))
- Binance.com
- Exodus wallet
- Celsius
- CoinGecko (for prices)

and stock/cash balance from:
- Brand New Day
- DeGiro


### Usage
Run [`crypto-tracker.ipynb`](crypto-tracker.ipynb) and download the correct data.

Set cronjob, using crontab -e
```
0 * * * * ~/Sync/Overig/crypto-tracker/run-and-upload.sh
```

### Install

```
pip install -r requirements.txt
```
and
```
sudo apt install chromium-chromedriver  # Ununtu
brew cask install chromedriver  # MacOS
```
