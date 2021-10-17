# views.py

import os.path
import datetime
from collections import OrderedDict

from django.shortcuts import render
from django.http import HttpResponse
from django.db import transaction

from . import models

# Create your views here.


Downloads_dir = os.path.expanduser(os.path.join('~', 'Downloads'))


def prev_month(date, target_day):
    try:
        if date.month == 1:
            return date.replace(year=date.year - 1, month=12,
                                day=target_day)
        return date.replace(month=date.month - 1, day=target_day)
    except ValueError:
        print("prev_month backing up to day", target_day - 1)
        return prev_month(date, target_day - 1)


def index(request):
    print("index called")
    accts = models.Account.objects.all()
    start_date = models.AccountShares.objects.latest().date
    end_date = models.AccountShares.objects.earliest().date

    print("index from", start_date, "back to", end_date)

    # list of (date, [acct_bal, ...])
    balances = []
    date = start_date
    while date >= end_date:
        print("doing date", date)
        row = (date, [acct.balance_on_date(date) for acct in accts])
        print(row)
        balances.append(row)
        date = prev_month(date, start_date.day)

    context = dict(accts=accts,
                   balances=balances,
    )
    print("rendering")
    return render(request, 'index.html', context)


# For Dividends for BLV, Apr 9, 2007 - Apr 17, 2020:
#   https://query1.finance.yahoo.com/v7/finance/download/BLV?period1=1176163200&period2=1587168000&interval=1d&events=div


@transaction.atomic
def clear_history(request, start_date, end_date):
    #models.AccountFundHistory.objects.filter(
    #                            date__range=(start_date, end_date)) \
    #                         .delete()
    models.AccountTransactionHistory.objects.filter(
                                      trade_date__range=(start_date,
                                                         end_date)) \
                                    .delete()
    models.AccountShares.objects.filter(
                                      date__range=(start_date, end_date)) \
                                    .delete()
    #models.AccountSnapshot.objects.filter(
    #                                  date__range=(start_date, end_date)) \
    #                                .delete()
    Account.objects.all().update(transaction_start_date=None,
                                 transaction_end_date=None,
                                 shares_start_date=None,
                                 shares_end_date=None)
    return HttpResponse(f"Cleared history between {start_date} and {end_date}.")


def load_fund_history(request, ticker='ALL'):
    r'''Will take 'ALL' as ticker for all funds.
    '''
    if request.method not in ('POST', 'GET'):
        response = HttpResponse()
        response.status_code = 405  # Method not allowed
    else:
        ticker = ticker.upper()
        if ticker != 'ALL':
            fund = models.Fund.objects.get(pk=ticker)
            try:
                dividend_rows, price_rows = fund.load_history()
                print("dividend_rows", dividend_rows,
                      "price_rows", price_rows)
                message = f"{ticker}: {dividend_rows} dividends loaded, " \
                            f"{price_rows} prices loaded."
                print("DONE:", message)
                response = HttpResponse(message)
            except models.Yahoo_exception as e:
                print(e)
                response = e.response()
        else:
            error_funds = []
            total_dividend_rows = 0
            total_price_rows = 0
            for fund in models.Fund.objects.all():
                try:
                    dividend_rows, price_rows = fund.load_history()
                    print(f"{fund}: {dividend_rows} dividends loaded, "
                            f"{price_rows} prices loaded.")
                    total_dividend_rows += dividend_rows
                    total_price_rows += price_rows
                except models.Yahoo_exception as e:
                    print(e)
                    error_funds.append(fund.ticker)
            if error_funds:
                response = HttpResponse(f"{error_funds} failed")
            else:
                message = f"{total_dividend_rows} dividends loaded, " \
                            f"{total_price_rows} prices loaded."
                print("DONE:", message)
                response = HttpResponse(message)
    return response


def load_transactions(request, end_date, filename='ofxdownload.csv'):
    r'''Loads/updates the AccountTransactionHistory table.
    
    The transactions are taken from the ofxdownload.csv file downloaded
    from Vanguard.
    '''
    if request.method not in ('POST', 'GET'):
        return HttpResponse(status=405)   # Method not allowed
    if end_date >= datetime.date.today():
        return HttpResponse("end_date must be earlier than today",
                            content_type='text/plain',
                            status=400)
    path = os.path.join(Downloads_dir, filename)
    with open(path, newline='') as file:
        trans_accounts, new_trans_funds = models.Account.load_csv(file,
                                                                  end_date)
    response = HttpResponse(
       f"Transactions loaded for {trans_accounts} accounts, "
       f"{new_trans_funds} new funds created."
    )
    return response


def dates(request):
    accounts = sorted(models.Account.objects.all(),
                      key=lambda acct: (acct.owner.name, acct.name))
    return render(request, 'dates.html', dict(accounts=accounts))


def get_populated_tree_by_date(acct, date, tags=''):
    tree = acct.get_tree(tags=tags)

    # {ticker: account_share}
    shares_by_ticker = acct.shares_on_date(date)

    tickers = [cat.ticker for cat in tree if cat.ticker is not None]
    share_prices = models.FundPriceHistory.share_prices(tickers, date)

    # Add shares to tree
    for row in tree:
        if row.ticker is not None:
            if row.ticker in shares_by_ticker:
                row.account_share = shares_by_ticker[row.ticker]
                row.shares = row.account_share.shares
                row.share_price = row.account_share.share_price
                row.balance = row.account_share.balance
                row.peak_pct_of_balance = row.account_share.peak_pct_of_balance
                row.peak_date = row.account_share.peak_date
                row.trough_pct_of_balance = \
                  row.account_share.trough_pct_of_balance
                row.trough_date = row.account_share.trough_date
            else:
                row.fph = share_prices[row.ticker]
                row.shares = 0.0
                row.share_price = row.fph.close
                row.balance = 0.0
                row.peak_pct_of_balance = row.fph.peak_pct_of_close
                row.peak_date = row.fph.peak_date
                row.trough_pct_of_balance = row.fph.trough_pct_of_close
                row.trough_date = row.fph.trough_date

    calc_balance(tree[0])

    return tree

def calc_balance(cat):
    r'''Calculate group balances.
    '''
    if cat.ticker is None:
        cat.balance = sum(calc_balance(c) for c in cat.children)
    return cat.balance

def get_populated_tree_by_ofxdownload(acct, ticker_info, tags=''):
    tree = acct.get_tree(tags=tags)

    # Add shares to tree
    for row in tree:
        if row.ticker is not None:
            if row.ticker in ticker_info:
                attrs = ticker_info[row.ticker]
                row.shares = attrs.shares
                row.share_price = attrs.share_price
                row.balance = attrs.balance
            else:
                row.shares = 0
                row.share_price = 0
                row.balance = 0

    calc_balance(tree[0])

    current_balance = sum(info.balance for info in ticker_info.values())
    print("Account", acct.id, "tree balance", tree[0].balance,
          "current_balance", current_balance)
    tree[0].balance = current_balance

    return tree

def add_plans(tree):
    # Calculate plans:
    acct_balance = tree[0].balance
    def calc_plan(cat, starting_bal, remaining_bal, last):
        cat.plan_pct_of_group, cat.plan_balance = \
          cat.plan.plan_balance(starting_bal, remaining_bal, last)
        cat.plan_pct_of_acct = cat.plan_balance / acct_balance
        remaining = cat.plan_balance
        for i, c in enumerate(cat.children, 1):
            remaining -= calc_plan(c, cat.plan_balance, remaining,
                                   last=(i == len(cat.children)))
        return cat.plan_balance
    calc_plan(tree[0], acct_balance, acct_balance, True)

    # Add adj_plan_balance == plan_balance (as a default)
    #
    # Find US and Bonds Categories
    for cat in tree:
        cat.adj_plan_balance = cat.plan_balance
        cat.adj_pct = 1.0
        if cat.name == 'Bonds':
            bond_cat = cat
        elif cat.name == 'US':
            us_cat = cat

    return us_cat, bond_cat


def adjust(cat, pct):
    cat.adj_plan_balance *= pct
    cat.adj_pct = pct
    for c in cat.children:
        adjust(c, pct)


def adjust_plan(us_cat, bond_cat, adj_pct):
    r'''Multiplies all us_cat balances by adj_pct.

    Takes the extra money needed out of bond_cat.
    '''
    adj_dollars = us_cat.plan_balance * adj_pct
    print("adj_pct", adj_pct, "adj_dollars", adj_dollars,
          "bond.plan_balance", bond_cat.plan_balance)
    if adj_dollars - us_cat.plan_balance >= bond_cat.plan_balance:
        # Not enough in bonds to cover adj_dollars...
        # Put all of bonds into US.
        adjust(us_cat, 1.0 + bond_cat.plan_balance / us_cat.plan_balance)
        adjust(bond_cat, 0)
    else:
        adjust(us_cat, adj_pct)
        adjust(bond_cat,
          1.0 - (adj_dollars - us_cat.plan_balance) / bond_cat.plan_balance)


def account(request, account_id, date, tags=''):
    acct = models.Account.objects.get(pk=account_id)

    if not (acct.shares_start_date <= date <= acct.shares_end_date):
        return HttpResponse(f"date must be between {acct.shares_start_date} "
                              f"and {acct.shares_end_date}",
                            content_type='text/plain',
                            status=400)

    #tags = tags.split(',') if tags else ()
    print("account", acct, "date", date, "Category root", acct.category, "tags", tags)

    tree = get_populated_tree_by_date(acct, date, tags=tags)
    us_cat, bond_cat = add_plans(tree)

    def find_min_pct(cat):
        if cat.ticker is not None:
            if cat.plan_balance:
                return cat.peak_pct_of_balance
            return 100
        return min(find_min_pct(c) for c in cat.children)

    adjust_plan(us_cat, bond_cat, find_min_pct(us_cat))

    context = dict(acct=acct, date=date, tree=tree,
    )
    return render(request, 'account.html', context)


def check_structure(request):
    tested = set()
    for acct in models.Account.objects.all():
        if acct.category_id is not None:
            print(f"Checking {acct}")
            tested.update(acct.category.check_structure())
    categories = frozenset(cat.id for cat in models.Category.objects.all())
    unlinked_cats = categories.difference(tested)
    if unlinked_cats:
        print(f"Unlinked categories {unlinked_cats}")
    return HttpResponse("Category checks complete.  "
                          "Examine http log for results.")


def get_plan(request, cat_name, account_id=1, tags=''):
    acct = models.Account.objects.get(pk=account_id)
    cat = models.Category.objects.get(name=cat_name)
    tags = tags.split(',') if tags else ()
    return HttpResponse(str(cat.get_plan(acct, tags=tags)),
                        content_type="text/plain")


def get_fund(request, cat_name, account_id=1):
    acct = models.Account.objects.get(pk=account_id)
    cat = models.Category.objects.get(name=cat_name)
    return HttpResponse(str(cat.get_fund(acct)), content_type="text/plain")


def get_children(request, cat_name, account_id=1, tags=()):
    acct = models.Account.objects.get(pk=account_id)
    cat = models.Category.objects.get(name=cat_name)
    tags = tags.split(',') if tags else ()
    return HttpResponse('\r\n'.join(str(child)
                                    for child in cat.get_children(acct, tags=tags)),
                        content_type="text/plain")


def get_tree(request, account_id, tags=()):
    acct = models.Account.objects.get(pk=account_id)
    tags = tags.split(',') if tags else ()
    context = dict(
        acct=acct,
        tree=acct.get_tree(tags=tags),
    )
    return render(request, 'tree.html', context)


def update_shares(request, reload=False):
    if request.method not in ('POST', 'GET'):
        response = HttpResponse()
        response.status_code = 405  # Method not allowed
    else:
        models.AccountShares.update(reload)
        response = HttpResponse(f"Done.", content_type="text/plain")
    return response


def shares(request, account_id, date):
    acct = models.Account.objects.get(pk=account_id)
    shares_by_ticker = acct.shares_on_date(date)
    print(sorted(shares_by_ticker.items()))
    context = dict(
        account=acct,
        date=date,
        shares_by_ticker=sorted(shares_by_ticker.items()),
        balance=sum(s.balance for s in shares_by_ticker.values()),
    )
    return render(request, 'shares.html', context)
 

def help(request):
    return render(request, 'help.html')


def rebalance(request, owner_id, adj_pct=1.0, filename='ofxdownload.csv', tags=''):
    user = models.User.objects.get(pk=owner_id)
    accts = models.Account.objects.filter(owner_id=owner_id).all()

    path = os.path.join(Downloads_dir, filename)
    with open(path, newline='') as file:
        current_accts, _ = models.read_balances_csv(
                             models.split_csv(file).gen())

    #tags = tags.split(',') if tags else ()
    trees = [get_populated_tree_by_ofxdownload(acct, current_accts[acct.id][1], tags=tags)
             for acct in accts]

    #if adj_pct < 1.0:
    #    return HttpResponse(f"adj_pct must be >= 1.0, got {adj_pct}",
    #                        content_type='text/plain', status=400)

    if request.method == 'GET':
        balances = {tree[0].account.id: tree[0].balance
                    for tree in trees}
        share_prices = {cat.ticker: cat.share_price
                        for cat in trees[0] if cat.ticker is not None}
    else:
        if request.method != 'POST':
            return HTTPResponse("Only GET and POST methods allowed", 
                                content_type='text/plain', status=405)
        # Get account balances
        balances = {acct.id: float(request.POST['balance_{}'.format(acct.id)])
                    for acct in accts}

        # Get share_prices
        tickers = [cat.ticker for cat in trees[0] if cat.ticker is not None]
        share_prices = {ticker: float(request.POST[ticker])
                        for ticker in tickers}

    # Set account balances
    for tree in trees:
        tree[0].balance = balances[tree[0].account.id]

    # Add plans, adj_plans and change_in_shares
    for tree in trees:
        us_cat, bond_cat = add_plans(tree)
        adjust_plan(us_cat, bond_cat, adj_pct)

        # Calculate change_in_shares
        for cat in tree:
            if cat.ticker is not None:
                change = cat.adj_plan_balance - cat.balance
                if change == 0:
                    cat.change_in_shares = 0
                else:
                    cat.share_price = share_prices[cat.ticker]
                    if cat.share_price:
                        cat.change_in_shares = \
                          (cat.adj_plan_balance - cat.balance) / cat.share_price
                    else:
                        cat.change_in_shares = "Ask Vanguard"

    # goal is list of (ticker, share_price, acct categories) ordered by
    # rebalance amount (sells first, buys last) based on first account in accts.
    #
    # Step 1: convert the cats representing funds for each tree into a
    #         {ticker: cat} map.
    trees_by_ticker = [{cat.ticker: cat for cat in tree
                                         if cat.ticker is not None}
                       for tree in trees]
    #
    # Step 2: Add obsolete funds (funds in current_accts that are not in
    #         trees_by_ticker).  These are set to sell everything.
    for tree, ticker_info in zip(trees_by_ticker, (current_accts[acct.id][1]
                                                   for acct in accts)):
        for ticker, info in ticker_info.items():
            if ticker not in tree:
                tree[ticker] = models.attrs(share_price=info.share_price,
                                            balance=info.balance,
                                            adj_plan_balance=0,
                                            change_in_shares=-info.shares)
    #
    # Step 3: Create the ticker rows for the template.  Each row is:
    #         (ticker, share_price, cats_per_acct)
    tickers_seen = set()
    ticker_rows = []
    for tree in trees_by_ticker:
        for ticker, cat in tree.items():
            if ticker not in tickers_seen:
                ticker_rows.append((ticker,
                                    cat.share_price,
                                    [tree.get(ticker)
                                     for tree in trees_by_ticker]))
                tickers_seen.add(ticker)
    #
    # Step 4: Sort the ticker_rows by change amount (sells before buys)
    ticker_rows.sort(key=lambda row:
                           sum(r.adj_plan_balance - r.balance
                               for r in row[2] if r is not None))

    # list of (balance, sum(balances), sum(adj_plan_balances)), one per acct
    totals = [(balances[accts[i].id],
               sum(cats[i].balance
                   for _, _, cats in ticker_rows
                    if cats[i] is not None),
               sum(cats[i].adj_plan_balance
                   for _, _, cats in ticker_rows
                    if cats[i] is not None))
              for i in range(len(accts))]

    print("totals", totals)

    context = dict(
        user=user,
        accts=accts,
        balances=balances,
        adj_pct=adj_pct,
        filename=filename,
        ticker_rows=ticker_rows,
        totals=totals,
    )

    return render(request, 'rebalance.html', context)


@transaction.atomic
def rebalanced(request, owner_id):
    if request.method not in ('POST', 'GET'):
        response = HttpResponse()
        response.status_code = 405  # Method not allowed
    else:
        models.Account.objects.filter(owner_id=owner_id) \
                              .update(rebalance_date=datetime.date.today())
        response = HttpResponse(f"Done.", content_type="text/plain")
    return response
