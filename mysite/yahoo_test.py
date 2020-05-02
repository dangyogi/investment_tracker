# yahoo_test.py

import requests


r = requests.get('https://query1.finance.yahoo.com/v7/finance/download/BLV?period1=1176163200&period2=9587168000&interval=1d&events=div')
print("got status", repr(r.status_code))
print("content type", r.headers['content-type'])
print("encoding", r.encoding)
print()
print(r.text)
