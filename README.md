# simple `crypto-tracker`
**See your current portofolio balance without the hassle.**

Can extract data from:
- Nexo.io
- Blockfi
- Binance Smart Chain
- Binance
- Exodus wallet

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
