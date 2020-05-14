# models.py

from datetime import datetime, date
from itertools import groupby
from operator import attrgetter
import hashlib

from django.db import models, transaction
from django.db.models import Sum, Q

from .plan_models import *
from .fund_models import *

# Create your models here.

class User(models.Model):
    name = models.CharField(max_length=15)

    def __str__(self):
        return self.name


class split_csv:
    def __init__(self, file):
        self.file = file

    def gen(self):
        blanks = 0
        for line in self.file:
            if not line.strip():
                blanks += 1
                if blanks >= 2: break
            else:
                blanks = 0
                yield line


def hash(x):
    ans = x
    for fn in 'sha3_384 sha512 blake2s'.split():
        ans = hashlib.new(fn, x.encode('utf-8')).hexdigest()
    return ans

class Account(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    account_number = models.CharField(max_length=150)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL,
                                 null=True, blank=True)

    # First and last dates in AccountTransactionHistory.
    transaction_start_date = models.DateField(null=True, blank=True)
    transaction_end_date = models.DateField(null=True, blank=True)

    # First and last dates in AccountShares.
    shares_start_date = models.DateField(null=True, blank=True)
    shares_end_date = models.DateField(null=True, blank=True)

    rebalance_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}: {self.owner}"

    def get_tree(self):
        return self.category.get_tree(self)

    @classmethod
    def get_account_number(cls, account_number):
        return cls.objects.get(account_number=hash(account_number))

    def balance_on_date(self, date):
        r'''Returns the account balance on `date`.
        '''
        shares_by_ticker = self.shares_on_date(date)
        return sum(account_share.balance 
                   for account_share in shares_by_ticker.values())

    def shares_on_date(self, date):
        r'''Returns {ticker: AccountShare} as of `date`.
        '''
        if not (self.shares_start_date <= date <= self.shares_end_date):
            return {}
        return {row.fund_id: row
                for row
                in AccountShares.objects.filter(account=self, date=date).all()}

    @staticmethod
    @transaction.atomic
    def load_csv(file, end_date):
        r'''Loads fund transactions from Vanguard download.

        Returns trans_accts, new_trans_funds.
        '''
        split = split_csv(file)

        accounts = read_balances_csv(split.gen())
        #accounts, new_fund_funds = \
        #  AccountFundHistory.load_csv(split.gen(), end_date)
        trans_accts, new_trans_funds = \
          AccountTransactionHistory.load_csv(split.gen(), end_date)

        # Update transaction_end_date for accounts with no new transactions
        for account, _ in accounts.values():
            if account.id not in trans_accts:
                account.transaction_end_date = end_date
                acct.save()
        #AccountShares.update()
        return len(trans_accts), new_trans_funds

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'],
                                    name='unique_account_name_per_owner'),
        ]
        ordering = ['owner', 'name']


def todate(s):
    r'''Converts Vanguard date to Python date object.

    Vanguard date format is: MM/DD/YYYY

    Note that this is different than Yahoo's format (see fund_models.py)!
    '''
    return datetime.strptime(s, "%m/%d/%Y").date()


class attrs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def read_balances_csv(file):
    r'''Reads the current balance info for each account from Vanguard.

    These are taken from an ofxdownload.csv file manually downloaded from
    Vanguard.

    Returns {account_id: account, {ticker: attrs}}, where attrs as the following
    attributes:

      * acct: the Account object
      * fund: the Fund object
      * shares: the current number of shares
      * share_price: the current share price
      * balance: the dollar value of these shares
    '''
    accts = {acct.account_number: acct
             for acct in Account.objects.all()}
    funds = {fund.ticker: fund
             for fund in Fund.objects.all()}
    ans = {}
    for account_number, rows \
     in groupby(sorted(csv.DictReader(file), key=itemgetter('Account Number')),
                key=itemgetter('Account Number')):
        acct = accts[hash(account_number)]
        tickers = {row['Symbol']: attrs(acct=acct,
                                        fund=funds[row['Symbol']],
                                        shares=float(row['Shares']),
                                        share_price=float(row['Share Price']),
                                        balance=float(row['Total Value']))
                   for row in rows}
        ans[acct.id] = acct, tickers
    return ans


class AccountTransactionHistory(models.Model):
    r'''Provided by Vanguard.
    
    They can provide a transaction history for any date range.

    The funds and number of shares can be calculated from this for any target
    date by summing the `shares` field for all trade_dates <= the target date.

    Vanguard sends null tickers for both the settlement fund (VMFXX) and
    "CASH" (whatever that is).  These are identified by the "Investment Name"
    provided by Vanguard.  This table converts the ticker (Fund) for the
    settlement fund transactions to 'VMFXX', and leaves the ticker null for
    "CASH" transactions.

    Vanguard also does not send shares or share_prices for the VMFXX fund.  To
    get the total of the "Settlement fund" and "Trade date balance" (as
    reported online by Vanguard) sum the net_amount of the following rows:

        fund_id isnull
     or fund_id != 'VMFXX' and not transaction_type.startswith('Transfer')
     or fund_id = 'VMFXX' and transaction_type = 'Dividend'

    Note that this excludes the "Settlement fund accrued dividends", which
    Vanguard also includes in its account balance.  Generally, these are small
    amounts, and I don't think that Vanguard reports these in the its
    transactions...
    '''
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    trade_date = models.DateField()
    settlement_date = models.DateField()
    transaction_type = models.CharField(max_length=30)
    transaction_desc = models.CharField(max_length=60)
    investment_name = models.CharField(max_length=60)
    fund = models.ForeignKey('Fund', on_delete=models.SET_NULL, null=True)
    shares = models.FloatField()
    share_price = models.FloatField()
    principal_amount = models.FloatField()
    commission_fees = models.FloatField()
    net_amount = models.FloatField()
    accrued_interest = models.FloatField()
    account_type = models.CharField(max_length=20)

    @classmethod
    def load_csv(cls, file, end_date):
        r'''Loads csv `file` produced by Vanguard.

        Updates Account.transaction_start_date and Account.transaction_end_date.

        Returns frozenset of accounts seen, number of funds created.
        '''
        accounts_seen = {}  # account_number: Account, start_date, prev_end_date
        funds_created = 0
        for row in csv.DictReader(file):
            trade_date=todate(row['Trade Date'])

            # Get account record from accounts_seen
            account_number = row['Account Number']
            if account_number in accounts_seen:
                acct, start_date, prev_end_date = accounts_seen[account_number]
            else:
                acct = Account.get_account_number(account_number)

                # These may be None
                start_date = acct.transaction_start_date
                prev_end_date = acct.transaction_end_date

                accounts_seen[account_number] = acct, start_date, prev_end_date

            assert prev_end_date is None or trade_date > prev_end_date, \
                   f"Earlier trade_date than expected.  Got {trade_date}, " \
                     f"expected later than {prev_end_date}."

            if start_date is None or trade_date < start_date:
                start_date = trade_date

            # Automatically create fund records for all funds seen here
            ticker = row['Symbol']

            # The VMFXX settlement fund comes in with a blank ticker.
            # But "CASH" also comes in with a blank ticker.
            # We convert the investment_name 'VANGUARD FEDERAL MONEY MARKET
            # FUND' to a 'VMFXX' ticker.  The "CASH" transactions remain NULL.
            assert ticker != 'VMFXX', f"Got unexpected 'VMFXX' ticker!"
            if not ticker:
                if row['Investment Name'].upper() == \
                       'VANGUARD FEDERAL MONEY MARKET FUND':
                    ticker = 'VMFXX'
                else:
                    # Investment Name should only be either the VMFXX name or
                    # "CASH".  If it's something else, then we should probably
                    # investigate...
                    assert row['Investment Name'].upper() == 'CASH', \
                           f"Got unknown blank ticker investment name: " \
                           f"{row['Investment Name']}"
            if not ticker:
                # "CASH"
                fund = None
            else:
                try:
                    fund = Fund.objects.get(pk=ticker)
                except Fund.DoesNotExist:
                    print("Creating Fund", ticker, row['Investment Name'])
                    fund = Fund(ticker=ticker, name=row['Investment Name'])
                    fund.save()
                    funds_created += 1
            cls(account=acct,
                trade_date=trade_date,
                settlement_date=todate(row['Settlement Date']),
                transaction_type=row['Transaction Type'],
                transaction_desc=row['Transaction Description'],
                investment_name=row['Investment Name'],
                fund=fund,
                shares=float(row['Shares']),
                share_price=float(row['Share Price']),
                principal_amount=float(row['Principal Amount']),
                commission_fees=float(row['Commission Fees']),
                net_amount=float(row['Net Amount']),
                accrued_interest=float(row['Accrued Interest']),
                account_type=row['Account Type'],
            ).save()

            # Update start_date
            accounts_seen[account_number] = acct, start_date, prev_end_date

        # Update transaction_start_date and transaction_end_date in Accounts.
        for acct, start_date, _ in accounts_seen.values():
            acct.transaction_start_date = start_date
            acct.transaction_end_date = end_date
            acct.save()

        return (frozenset(acct for acct, start, end in accounts_seen.values()),
                funds_created)

    class Meta:
        get_latest_by = 'trade_date'
        ordering = ['-trade_date']


class AccountShares(models.Model):
    r'''The number of shares in each account's fund by date.

    This is extrapolated from AccountTransactionHistory to get the number of
    shares on each date.

    For non-VMFXX funds, this simply sums the `shares` from
    AccountTransactionHistory for that fund.

    For VMFXX, it sums the `net_amount` for all of the following transactions:

        fund_id isnull
     or fund_id != 'VMFXX' and not transaction_type.startswith('Transfer')
     or fund_id = 'VMFXX' and transaction_type = 'Dividend'

    '''
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE)
    date = models.DateField()
    shares = models.FloatField(null=True)
    share_price = models.FloatField(null=True)
    balance = models.FloatField()  # share price taken from FundPriceHistory
    peak_pct_of_balance = models.FloatField()
    peak_date = models.DateField()
    trough_pct_of_balance = models.FloatField(null=True)
    trough_date = models.DateField(null=True)

    @classmethod
    @transaction.atomic
    def update(cls, reload=False):
        r'''Loads new rows from AccountTransactionHistory.
        '''
        if reload:
            # Delete the entire table and rebuild it.
            cls.objects.all().delete()

        for acct in Account.objects.all():
            end_date = acct.transaction_end_date

            ath_query = AccountTransactionHistory.objects \
                                                 .filter(account_id=acct.id)
            try:
                latest = cls.objects.filter(account_id=acct.id).latest()
                last_date = latest.date
                assert last_date == acct.shares_end_date, \
                       f"last_date, {last_date}, != " \
                         f"shares_end_date, {acct.shares_end_date}"
                starting_shares = {row.fund_id: row.shares
                                   for row
                                    in cls.objects.filter(account_id=acct.id,
                                                          date=last_date)
                                                  .all()}
                start_date = last_date + One_day
                ath_within_dates = ath_query.filter(trade_date__gte=start_date)
                fph_query = \
                  FundPriceHistory.objects.filter(
                    date__gte=start_date - One_week)
            except cls.DoesNotExist:
                last_date = None
                start_date = acct.transaction_start_date
                ath_within_dates = ath_query
                fph_query = FundPriceHistory.objects

            print("Doing", acct, "last_date", last_date,
                  "start_date", start_date, "end_date", end_date)

            fund_history = {(fph.fund_id, fph.date): fph
                            for fph in fph_query.all()}

            def get_fph(ticker, date, count=0):
                if (ticker, date) in fund_history:
                    return fund_history[ticker, date]
                assert count < 5, \
                       f"Missing fund history date for {ticker} on {date}"
                return get_fph(ticker, date - One_day, count + 1)

            # Gather all but VMFXX funds:
            ordered_ath = ath_within_dates.filter(fund_id__isnull=False) \
                                          .exclude(fund_id='VMFXX') \
                                          .exclude(shares=0) \
                                          .order_by('fund_id', 'trade_date')

            new_rows = []
            tickers_seen = set()
            for ticker, ath in groupby(ordered_ath.all(),
                                       key=attrgetter('fund_id')):
                tickers_seen.add(ticker)
                # Get starting number of shares
                if last_date is None:
                    shares = 0.0
                else:
                    shares = starting_shares.get(ticker, 0.0)

                print(ticker, "starting shares", shares)

                next_date = start_date
                for a in ath:
                    if abs(shares) > 0.01:
                        #print("shares", shares)
                        while next_date < a.trade_date:
                            assert shares >= 0, \
                                   f"Got unexpected negative shares on " \
                                     f"{next_date}"
                            fph = get_fph(ticker, next_date)
                            new_rows.append(
                              cls(account_id=acct.id, fund_id=ticker,
                                  date=next_date, shares=shares,
                                  share_price=fph.close,
                                  balance=shares * fph.close,
                                  peak_pct_of_balance=fph.peak_pct_of_close,
                                  peak_date=fph.peak_date,
                                  trough_pct_of_balance=fph.trough_pct_of_close,
                                  trough_date=fph.trough_date))
                            next_date += One_day
                    else:
                        next_date = a.trade_date
                    shares += a.shares

                if abs(shares) > 0.01:
                    assert shares >= 0, \
                           f"Got unexpected negative shares on {next_date}"
                    while next_date <= end_date:
                        fph = get_fph(ticker, next_date)
                        new_rows.append(
                          cls(account_id=acct.id, fund_id=ticker,
                              date=next_date, shares=shares,
                              share_price=fph.close,
                              balance=shares * fph.close,
                              peak_pct_of_balance=fph.peak_pct_of_close,
                              peak_date=fph.peak_date,
                              trough_pct_of_balance=fph.trough_pct_of_close,
                              trough_date=fph.trough_date))
                        next_date += One_day

            # Bring forward any shares that didn't have any transactions.
            for ticker, shares in starting_shares.items():
                if ticker != 'VMFXX' and ticker not in tickers_seen and \
                   abs(shares) > 0.01:
                    assert shares >= 0, \
                           f"Got unexpected negative shares on {next_date}"
                    next_date = start_date
                    while next_date <= end_date:
                        fph = get_fph(ticker, next_date)
                        new_rows.append(
                          cls(account_id=acct.id, fund_id=ticker,
                              date=next_date, shares=shares,
                              share_price=fph.close,
                              balance=shares * fph.close,
                              peak_pct_of_balance=fph.peak_pct_of_close,
                              peak_date=fph.peak_date,
                              trough_pct_of_balance=fph.trough_pct_of_close,
                              trough_date=fph.trough_date))
                        next_date += One_day

            # Gather VMFXX fund:
            ordered_ath = \
              ath_within_dates \
                .exclude(net_amount=0) \
                .filter(Q(fund_id__isnull=True) |
                        ~(Q(fund_id='VMFXX') |
                          Q(transaction_type__startswith='Transfer')) |
                        Q(fund_id='VMFXX', transaction_type='Dividend')) \
                .order_by('trade_date')

            if last_date is None:
                shares = 0.0
            else:
                shares = starting_shares['VMFXX']

            next_date = start_date
            for a in ordered_ath.all():
                #print("shares", shares)
                while next_date < a.trade_date:
                    assert shares >= 0, \
                           f"Got unexpected negative shares, {shares}, " \
                             f"on {next_date}"
                    new_rows.append(
                      cls(account_id=acct.id, fund_id='VMFXX',
                          date=next_date, shares=shares, share_price=1.0,
                          peak_pct_of_balance=1.0, peak_date=next_date,
                          balance=shares))
                    next_date += One_day
                shares += a.net_amount

            while next_date <= end_date:
                assert shares >= 0, \
                       f"Got unexpected negative shares on {next_date}"
                new_rows.append(
                  cls(account_id=acct.id, fund_id='VMFXX',
                      date=next_date, shares=shares, share_price=1.0,
                      peak_pct_of_balance=1.0, peak_date=next_date,
                      balance=shares))
                next_date += One_day

            #print("  Creating new rows")
            cls.objects.bulk_create(new_rows)

            if acct.shares_start_date is None:
                print("setting", acct, "shares_start_date to", start_date)
                acct.shares_start_date = start_date
            print("setting", acct, "shares_end_date to", end_date)
            acct.shares_end_date = end_date
            acct.save()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'fund', 'date'],
                                    name='unique_account_shares_per_date'),
        ]
        get_latest_by = 'date'

