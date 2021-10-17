# yahoo_test.py

import requests

s = requests.Session()

s.headers.update({
    #'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'
    'user-agent': 'Mozilla'
})

if False:
    r = s.get('https://finance.yahoo.com')
    print("sent url", r.request.url)
    print("sent headers:")
    for name, value in sorted(r.request.headers.items()):
        print(f"  {name}: {value}")
    #print("sent cookies", r.request.cookies)
    print("got status", repr(r.status_code), r.reason)
    print("content type", r.headers['content-type'])
    print("encoding", r.encoding)
    print("cookies", r.cookies)
    print("history", r.history)
    print()
    #print(r.text)
    #print()
    print('-' * 60)
    print()

r = s.get('https://query1.finance.yahoo.com/v7/finance/download/BLV?period1=1176163200&period2=9587168000&interval=1d&events=div')
print("got status", repr(r.status_code), r.reason)
print("sent url", r.request.url)
print("sent headers:")
for name, value in sorted(r.request.headers.items()):
    print(f"  {name}: {value}")
#print("sent cookies", r.request.cookies)
print("content type", r.headers['content-type'])
print("encoding", r.encoding)
print()
print(r.text)
