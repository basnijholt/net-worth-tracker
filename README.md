# simple `crypto-tracker`
**See your current portofolio balance without the hassle.**

Can extract crypto portfolio data from:
- Nexo.io
- BlockFi
- Binance Smart Chain (BEP20 tokens + DeFi via [YieldWatch.net](https://www.yieldwatch.net/))
- Binance.com
- Exodus wallet
- Celsius
- ApeBoard for tracking on many DeFi chains
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
sudo apt install chromium-chromedriver keychain # Ubuntu
brew cask install chromedriver  # MacOS
```
