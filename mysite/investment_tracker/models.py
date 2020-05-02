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

    """FIX: Delete
    # First and last dates in AccountSnapshot.
    snapshot_start_date = models.DateField(null=True, blank=True)
    snapshot_end_date = models.DateField(null=True, blank=True)
    """

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
    def load_csv(file, end_date):
        r'''Loads fund transactions from Vanguard download.

        Returns trans_accts, new_trans_funds.
        '''
        split = split_csv(file)

        # Discard the first part of the .csv file.
        for line in split.gen():
            pass

        #accounts, new_fund_funds = \
        #  AccountFundHistory.load_csv(split.gen(), end_date)
        trans_accts, new_trans_funds = \
          AccountTransactionHistory.load_csv(split.gen(), end_date)
        #AccountShares.update()
        return trans_accts, new_trans_funds

    """FIX: delete
    def fund_history_dates(self):
        dicts = AccountFundHistory.objects.filter(account=self) \
                                          .values('date') \
                                          .distinct()
        ans = [row['date'] for row in dicts]
        print("dates for", self, ans)
        return ans
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'],
                                    name='unique_account_name_per_owner'),
        ]
        ordering = ['owner', 'name']


def todate(s):
    return datetime.strptime(s, "%m/%d/%Y").date()


"""FIX: delete
class AccountFundHistory(models.Model):
    r'''Provided by Vanguard -- but not used...

    Contains fund/shares/share_prices on a single date.  Vanguard has no way
    to get this information for past dates, so it's not very useful.  Vanguard
    has filed a repair ticket on this, so you may be able to get past dates at
    some point in the future (written Apr 24, 2020).
    '''
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE)
    date = models.DateField()
    shares = models.FloatField()
    share_price = models.FloatField()
    balance = models.FloatField()

    @classmethod
    @transaction.atomic
    def load_csv(cls, file, date):
        r'''Loads csv `file` produced by Vanguard on `date`.

        Returns number_of_accounts seen, number of new Funds created.
        '''
        accounts_seen = {}  # cache of accounts
        funds_created = 0
        for row in csv.DictReader(file):
            if not row['Account Number'].isdigit():
                # Vanguard sends two .csv files (separated by a few blank
                # lines, though there are single blank lines in the first
                # part...)
                break

            # Get account record from accounts_seen
            account_number = row['Account Number']
            if account_number in accounts_seen:
                acct = accounts_seen[account_number]
            else:
                acct = Account.get_account_number(account_number)
                accounts_seen[account_number] = acct

            # Automatically create fund records for all funds seen here
            ticker = row['Symbol']
            try:
                fund = Fund.objects.get(pk=ticker)
            except Fund.DoesNotExist:
                print("Creating Fund", ticker, row['Investment Name'])
                fund = Fund(ticker=ticker, name=row['Investment Name'])
                fund.save()
                funds_created += 1

            # Insert new history row
            cls(account=acct, fund=fund, date=date,
                shares=float(row['Shares']),
                share_price=float(row['Share Price']),
                balance=float(row['Total Value']),
            ).save()
        return accounts_seen, funds_created

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'fund', 'date'],
                                    name='unique_account_fund_per_date'),
        ]
        get_latest_by = 'date'
        ordering = ['-date']
"""

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

    Note that this exclude the "Settlement fund accrued dividends", which
    Vanguard also includes in its account balance.  Generally, these are small
    amounts, and I don't think that Vanguard reports these in the its
    transactions.
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
    @transaction.atomic
    def load_csv(cls, file, end_date):
        r'''Loads csv `file` produced by Vanguard.

        Updates Account.shares_start_date and Account.shares_end_date.
        '''
        accounts_seen = {}  # account_number: Account, start_date, end_date
        funds_created = 0
        for row in csv.DictReader(file):
            trade_date=todate(row['Trade Date'])

            # Get account record from accounts_seen
            account_number = row['Account Number']
            if account_number in accounts_seen:
                acct, start_date, end_date = accounts_seen[account_number]
            else:
                acct = Account.get_account_number(account_number)

                # These may be None
                start_date = acct.transaction_start_date
                prev_end_date = acct.transaction_end_date

                accounts_seen[account_number] = acct, start_date, end_date

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

            # Update start_date and end_date
            accounts_seen[account_number] = acct, start_date, end_date

        # Update shares_start_date and shares_end_date in Accounts.
        for acct, start_date, end_date in accounts_seen.values():
            acct.transaction_start_date = start_date
            acct.transaction_end_date = end_date
            acct.save()

        return len(accounts_seen), funds_created

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
    pct_of_peak = models.FloatField()
    peak_date = models.DateField()
    pct_of_trough = models.FloatField(null=True)
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
                    shares = starting_shares[ticker]

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
                                  pct_of_peak=fph.pct_of_peak,
                                  peak_date=fph.peak_date,
                                  pct_of_trough=fph.pct_of_trough,
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
                              pct_of_peak=fph.pct_of_peak,
                              peak_date=fph.peak_date,
                              pct_of_trough=fph.pct_of_trough,
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
                              pct_of_peak=fph.pct_of_peak,
                              peak_date=fph.peak_date,
                              pct_of_trough=fph.pct_of_trough,
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
                          pct_of_peak=1.0, peak_date=next_date,
                          balance=shares))
                    next_date += One_day
                shares += a.net_amount

            while next_date <= end_date:
                assert shares >= 0, \
                       f"Got unexpected negative shares on {next_date}"
                new_rows.append(
                  cls(account_id=acct.id, fund_id='VMFXX',
                      date=next_date, shares=shares, share_price=1.0,
                      pct_of_peak=1.0, peak_date=next_date,
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


"""FIX: Delete
class AccountSnapshot(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    date = models.DateField()
    depth = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField()
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE, null=True)
    shares = models.FloatField(null=True)
    share_price = models.FloatField(null=True)
    balance = models.FloatField()
    peak_balance = models.FloatField()
    peak_date = models.DateField()
    trough_balance = models.FloatField(null=True)
    trough_date = models.DateField(null=True)
    plan_balance = models.FloatField()
    plan_pct_of_group = models.FloatField()
    plan_pct_of_account = models.FloatField()

    @classmethod
    @transaction.atomic
    def update(cls, start_date=None, reload=False):
        r'''This is done in batches by account in asc date sequence.

        Returns end_date (date of last snapshot created).
        '''
        if reload:
            # Delete the entire table and rebuild it.
            cls.objects.all().delete()

        for acct in Account.objects.all():
            if acct.category is None:
                print("skipping Account -- no Category", acct)
                continue
            print("loading Account", acct)
            try:
                last_date = cls.objects.filter(account=acct).latest().date
            except cls.DoesNotExist:
                last_date = None

            if start_date is not None:
                assert last_date is None, \
                       f"start_date not allowed with prior rows loaded " \
                         f"(up to {last_date})."
                assert acct.snapshot_start_date is None or \
                       acct.snapshot_start_date == start_date, \
                       f"{acct} snapshot_start_date, " \
                         f"{acct.snapshot_start_date}, " \
                         f"not equal to start_date provided."
                if acct.snapshot_start_date is None:
                    acct.snapshot_start_date = start_date
                    acct.save()
                date = start_date
                yesterday = None
            elif last_date is None:
                # Start with acct.snapshot_start_date
                assert acct.snapshot_start_date is not None, \
                       f"start_date required on first load"
                start_date = acct.snapshot_start_date
                date = start_date
                yesterday = None
            else:
                # Start with the day after the last date on record for this
                # account.
                start_date = cls.objects.filter(account=acct).earliest().date
                if acct.snapshot_start_date is None:
                    acct.snapshot_date_date = start_date
                    acct.save()
                date = last_date + One_day
                yesterday = {snap.category_id: snap
                             for snap
                             in cls.objects.filter(account=acct, date=last_date)
                                           .all()}

            end_date = acct.shares_end_date
            assert end_date is not None, \
                   "Can't update AccountSnapshot until " \
                     "AccountTransactionHistory is loaded"
            try:
                last_fundhistory_date = FundPriceHistory.objects.latest().date
            except FundPriceHistory.DoesNotExist:
                raise AssertionError(f"No FundPriceHistory!")
            assert last_fundhistory_date >= start_date, \
                   f"Need more FundPriceHistory, last date is only " \
                     f"{last_fundhistory_date}"
            if last_fundhistory_date < end_date:
                print("Can't load everything, only have FundPriceHistory up to",
                      last_fundhistory_date, "will load what I can...")
                end_date = last_fundhistory_date

            # load date independent info for all Categories
            cat_info = {}  # cat_id: info
            order = 1
            def get_cat_info(cat, depth=1):
                nonlocal order

                fields = dict(account_id=acct.id, category=cat, depth=depth,
                              order=order)
                order += 1
                children = cat.get_children(acct)
                info = dict(fields=fields, children=children,
                            plan=cat.get_plan(acct))
                cat_info[cat.id] = info
                if not children:
                    fields['fund'] = cat.get_fund(acct)
                else:
                    for child in children:
                        get_cat_info(child, depth + 1)
            get_cat_info(acct.category)

            # load rows for each date
            while date <= end_date:
                yesterday = cls.update_acct_on_date(acct, date, cat_info,
                                                    yesterday)
                date += One_day

            acct.snapshot_end_date = end_date
            acct.save()
        return end_date

    @classmethod
    def update_acct_on_date(cls, acct, date, cat_info, yesterday):
        r'''This is done in two steps:

        1. Figure out everything but the plan_* fields in bottom up
           Category sequence (descending order).
        2. Figure out the plan_* fields in top down sequence (ascending order).

        Returns new date as {cat_id: new_fields} for use as
        next date's `yesterday`.  Note that these do not have their 'id'
        fields (due to using bulk_create).
        '''

        # Copy info['fields'] into the starting rows to create for this date.
        rows = {}  # cat_id: new_fields
        for cat_id, info in cat_info.items():
            fields = info['fields'].copy()
            fields['date'] = date
            rows[cat_id] = fields

        # FIX, The values of this changed from shares to AccountShare objects...
        shares_by_ticker = acct.shares_on_date(date)

        def load_balances(cat):
            r'''Sets everything but the plan_ fields.

            Works bottom up.
            '''
            info = cat_info[cat.id]
            children = info['children']
            fields = rows[cat.id]

            if not children:
                fund = info['fields']['fund']
                shares = fields['shares'] = shares_by_ticker.get(fund.ticker,
                                                                 0.0)
                share_price = fields['share_price'] = fund.get_price(date)
                balance = shares * share_price
            else:
                balance = sum(load_balances(child) for child in children)

            fields['balance'] = balance

            if yesterday is None or balance > yesterday[cat.id]['peak_balance']:
                # New peak!
                fields['peak_balance'] = balance
                fields['peak_date'] = date
                # no trough info until tomorrow...
            else:
                # Not a new peak...  Copy peak info forward from yesterday.
                y = yesterday[cat.id]

                # Bring peak_balance forward from yesterday
                fields['peak_balance'] = y['peak_balance']
                fields['peak_date'] = y['peak_date']

                # Check for new trough
                if 'trough_balance' not in y or balance < y['trough_balance']:
                    # New trough!
                    fields['trough_balance'] = balance
                    fields['trough_date'] = date
                else:
                    # Bring trough_balance forward from yesterday
                    fields['trough_balance'] = y['trough_balance']
                    fields['trough_date'] = y['trough_date']
            return balance

        account_balance = load_balances(acct.category)

        def load_plans(cat, starting_balance, remaining_balance, last):
            info = cat_info[cat.id]
            plan = info['plan']
            children = info['children']
            fields = rows[cat.id]

            pct_of_group, plan_balance = \
              plan.plan_balance(starting_balance, remaining_balance, last)
            plan_balance = plan_balance
            fields['plan_balance'] = plan_balance
            fields['plan_pct_of_group'] = pct_of_group
            #print(f"plan_balance {plan_balance!r}, "
            #        f"account_balance {account_balance!r}")
            fields['plan_pct_of_account'] = plan_balance / account_balance

            starting_balance = plan_balance
            remaining_balance = starting_balance
            for i, child in enumerate(children, 1):
                remaining_balance -= \
                  load_plans(child, starting_balance, remaining_balance,
                             last=(i == len(children)))
            return plan_balance

        load_plans(acct.category, account_balance, account_balance, True)

        today = [cls(**new_fields)
                 for new_fields in rows.values()
                  if 'balance' in new_fields]

        print(f"Inserting {rows[1]['account_id']} {rows[1]['category']} "
                f"{rows[1]['date']}")

        # Insert new snapshot rows
        cls.objects.bulk_create(today)

        # The `yesterday` value for the next date.
        return rows


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'category', 'date'],
                                    name='unique_account_snapshot_per_date'),
        ]
        get_latest_by = 'date'
        ordering = ['order']
"""
