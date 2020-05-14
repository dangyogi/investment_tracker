# fund_models.py

import calendar
from datetime import datetime, date, time, timedelta
from io import StringIO
import csv
from operator import attrgetter, itemgetter
from itertools import groupby

import requests

from django.db import models, transaction, IntegrityError
from django.http import HttpResponse

# Create your models here.

# These are not tied to users.


class Yahoo_exception(Exception):
    def response(self):
        r = HttpResponse(self.args[0])
        r.status_code = 503
        return r


One_day = timedelta(days=1)
One_week = timedelta(weeks=1)

def yahoo_period(d, as_end_date=False):
    r'''Yahoo uses standard Unix seconds since the epoch for its periods.

    If `as_end_date` is False, returns midnight UTC on the morning of day `d`.
    Otherwise, returns midnight UTC at the end of day `d`.

    `d` must be a Python date object.
    '''
    if as_end_date:
        d += One_day
    return calendar.timegm(d.timetuple())

def yahoo_url(ticker, events, start_date=None, end_date=None):
    r'''Returns the URL to query Yahoo for fund history.

    `start_date` is the first day to include in the data (defaults to
    the beginning of time).

    `end_date` is the last day to include in the data (defaults to yesterday).

    This asserts that start_date <= end_date, and end_date < today.
    '''
    if start_date:
        period1 = yahoo_period(start_date, as_end_date=False)
        print("start_date is", start_date, "period1 is", period1)
    else:
        # default to the beginning of time...
        period1 = 0
    if end_date is None:
        # default to yesterday
        end_date = date.today() - One_day
    period2 = yahoo_period(end_date, as_end_date=True)
    print("end_date is", end_date, "period2 is", period2)

    assert period1 <= period2, \
           f"yahoo_url: start_date, {start_date}, must be <= end_date, " \
             f"{end_date}"

    assert end_date < date.today(), \
           f"yahoo_url: end_date, {end_date}, must be < today"

    return f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}" \
           f"?period1={period1}&period2={period2}&interval=1d&events={events}"


def todate(s):
    r'''This converts a date downloaded from Yahoo into a Python date object.

    The Yahoo format is: YYYY-MM-DD

    Note that this is different than Vanguard's format (see models.py)!
    '''
    return datetime.strptime(s, "%Y-%m-%d").date()


class Fund(models.Model):
    ticker = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=60, unique=True)

    def __str__(self):
        return self.ticker

    def get_price(self, date, first_date=None):
        r'''Returns the Fund's closing price on `date`.
        '''
        if self.ticker == 'VMFXX':
            return 1.0
        try:
            return FundPriceHistory.objects.get(fund=self, date=date).close
        except FundPriceHistory.DoesNotExist:
            #print(f"get_price({self.ticker}, {date}) does not exist")
            if first_date is None:
                first_date = FundPriceHistory.objects.filter(fund=self) \
                                                     .earliest().date
            if date < first_date:
                print("No price history for", date, "first_date", first_date)
                raise
            return self.get_price(date - One_day, first_date)

    @transaction.atomic
    def load_history(self):
        r'''Does both load_dividends and load_prices.

        Returns dividend_rows, price_rows.
        '''
        dividend_rows = self.load_dividends()
        price_rows = self.load_prices()
        return dividend_rows, price_rows

    def load_dividends(self):
        r'''Brings FundDividendHistory up to date from yahoo.

        Returns the number of rows added.
        '''
        return FundDividendHistory.load_dividends(self.ticker)

    def load_prices(self):
        r'''Brings FundPriceHistory up to date from yahoo.

        Returns the number of rows added.
        '''
        return FundPriceHistory.load_prices(self)


class FundDividendHistory(models.Model):
    r''' Provided by Yahoo, but not yet needed...
    '''
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE)
    date = models.DateField()
    dividends = models.FloatField()
    adj_shares = models.FloatField(null=True)  # after reinvesting dividends

    @classmethod
    def load_dividends(cls, ticker):
        r'''Brings FundDividendHistory up to date from yahoo.

        Returns the number of rows added.
        '''
        try:
            last_date = cls.objects.filter(fund_id=ticker).latest().date
            print(f"{ticker} last dividend recorded is on", last_date)
            r = requests.get(yahoo_url(ticker, 'div', last_date + One_day))
        except FundDividendHistory.DoesNotExist:
            last_date = date(1,1,1)
            print(f"{ticker} got DoesNotExist looking for last dividend "
                    "recorded")
            r = requests.get(yahoo_url(ticker, 'div'))
        if r.status_code != 200:
            raise Yahoo_exception(
                    f"Bad status code from yahoo for {ticker} dividends: "
                      f"{r.status_code}")
        if r.headers['content-type'] != 'text/plain':
            raise Yahoo_exception(
                    f"Expected text/plain from yahoo for {ticker} dividends, "
                      f"got {r.headers['content-type']}")
        rows = 0
        for row in csv.DictReader(StringIO(r.text)):
            #print(row)
            row_date = todate(row['Date'])
            if row_date > last_date:
                cls(fund_id=ticker,
                    date=row_date,
                    dividends=float(row['Dividends']),
                ).save()
                rows += 1
            else:
                print(f"Got {row_date} from Yahoo for {ticker} dividends, "
                        f"expected > {last_date} -- IGNORED")
        return rows

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fund', 'date'],
                                    name='unique_funddiv_by_date'),
        ]
        get_latest_by = 'date'
        ordering = ['-date']


class FundPriceHistory(models.Model):
    r'''Provided by yahoo.
    '''
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE)
    date = models.DateField()

    # Includes splits, but not dividends.
    # This is "Close" on finance.yahoo.com; _not_ "Adj Close"!
    close = models.FloatField()

    peak_close = models.FloatField()
    peak_date = models.DateField()
    trough_close = models.FloatField(null=True)
    trough_date = models.DateField(null=True)

    @property
    def peak_pct_of_close(self):
        return self.peak_close / self.close

    @property
    def trough_pct_of_close(self):
        if self.trough_close is None:
            return None
        return self.trough_close / self.close

    @classmethod
    def share_prices(cls, tickers, date):
        r'''Returns {ticker: FundPriceHistory} for all `tickers` on `date`.
        '''
        tickers = list(tickers)
        def get_dict(add_cash=False):
            rows = cls.objects.filter(fund_id__in=tickers,
                                      date__range=(date - One_week, date)) \
                              .order_by('fund_id', '-date').all()
            ans = {fund_id: next(fph)
                   for fund_id, fph
                    in groupby(rows, key=attrgetter('fund_id'))}
            if add_cash:
                ans['VMFXX'] = FundPriceHistory(fund_id='VMFXX', date=date,
                                                close=1.0, peak_close=1.0,
                                                peak_date=date)
            return ans

        if 'VMFXX' in tickers:
            tickers.remove('VMFXX')
            return get_dict(add_cash=True)
        return get_dict(add_cash=False)

    @classmethod
    def load_prices(cls, fund):
        r'''Brings FundPriceHistory up to date from yahoo.

        Returns the number of rows added.
        '''
        try:
            latest = cls.objects.filter(fund=fund).latest()
            last_date = latest.date
            print(f"{fund.ticker} last close recorded is on", last_date)
            start_date = last_date + One_day
            if start_date >= date.today():
                print(f"Skipping {fund}, last date is {last_date} -- "
                        "up to date!")
                return 0
            peak_close = latest.peak_close
            peak_date = latest.peak_date
            trough_close = latest.trough_close
            trough_date = latest.trough_date
            r = requests.get(yahoo_url(fund.ticker, 'history', start_date))
        except cls.DoesNotExist:
            last_date = date(1,1,1)
            print(f"{fund.ticker} got DoesNotExist looking for last close "
                    "recorded")
            peak_close = 0
            peak_date = None
            trough_close = None
            trough_date = None
            r = requests.get(yahoo_url(fund.ticker, 'history'))
        if r.status_code != 200:
            print(f"Bad status code from Yahoo {r.status_code} "
                    f"for {fund.ticker} prices, "
                    f"content-type {r.headers['content-type']}")
            print(r.text)
            raise Yahoo_exception(
                    f"Bad status code from yahoo for {fund.ticker} prices: "
                      f"{r.status_code}")
        if r.headers['content-type'] != 'text/plain':
            raise Yahoo_exception(
                    f"Expected text/plain from yahoo for {fund.ticker} prices, "
                      f"got {r.headers['content-type']}")
        rows = 0
        for row in sorted(csv.DictReader(StringIO(r.text)),
                          key=itemgetter('Date')):
            #print(row)
            row_date = todate(row['Date'])
            assert row_date > last_date, \
                   f"Got {row_date} from Yahoo for {fund.ticker} prices, " \
                     f"expected > {last_date}"
            if row['Close'] == 'null':
                print(f"{fund.ticker} has null Close on {row_date} -- ignored")
            else:
                close = float(row['Close'])
                if close > peak_close:
                    peak_close = close
                    peak_date = row_date
                    trough_close = None
                    trough_date = None
                elif trough_close is None or close < trough_close:
                    trough_close = close
                    trough_date = row_date
                fph = cls(fund=fund, date=row_date, close=close,
                          peak_close=peak_close, peak_date=peak_date,
                          trough_close=trough_close, trough_date=trough_date)
                #print("inserting", fund, row_date)
                fph.save()
                rows += 1
                last_date = row_date  # we're seeing duplicate dates from yahoo!
        return rows

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fund', 'date'],
                                    name='unique_fundprice_by_date'),
        ]
        get_latest_by = 'date'
        ordering = ['-date']

