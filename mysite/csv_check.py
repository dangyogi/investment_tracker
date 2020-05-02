# csv_check.py

import csv


with open('/home/bruce/Downloads/ofxdownload.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        print(row)
