# urls.py

from datetime import datetime

from django.urls import path, register_converter

from . import views


class DateConverter:
    regex = r'[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}'
    format = '%Y-%m-%d'

    def to_python(self, value):
        return datetime.strptime(value, self.format).date()

    def to_url(self, value):
        return value.strftime(self.format)

register_converter(DateConverter, 'date')


class FloatConverter:
    regex = r'-?(?:[0-9]*\.[0-9]+)|(?:[0-9]+)'

    def to_python(self, value):
        return float(value)

    def to_url(self, value):
        return str(value)

register_converter(FloatConverter, 'float')


urlpatterns = [
    path('', views.index, name='index'),
    path('clear_history/<date:start_date>/<date:end_date>',
         views.clear_history, name='clear_history'),
    path('load_fund_history', views.load_fund_history,
         name='load_all_fund_history'),
    path('load_fund_history/<ticker>', views.load_fund_history,
         name='load_fund_history'),
    path('load_transactions/<filename>/<date:end_date>',
         views.load_transactions, name='load_transactions'),
    path('dates', views.dates, name='dates'),
    path('account/<int:account_id>/<date:date>', views.account, name='account'),
    path('check_structure', views.check_structure, name='check_structure'),
    path('get_plan/<cat_name>', views.get_plan),
    path('get_plan/<cat_name>/<int:account_id>', views.get_plan),
    path('get_fund/<cat_name>', views.get_fund),
    path('get_fund/<cat_name>/<int:account_id>', views.get_fund),
    path('get_children/<cat_name>', views.get_children),
    path('get_children/<cat_name>/<int:account_id>', views.get_children),
    path('get_tree/<int:account_id>', views.get_tree),
    #path('update_snapshot', views.update_snapshot),
    #path('update_snapshot/<date:start_date>', views.update_snapshot),
    #path('update_snapshot/<int:reload>', views.update_snapshot),
    #path('update_snapshot/<date:start_date>/<int:reload>',
    #     views.update_snapshot),
    path('update_shares', views.update_shares, name='update_shares'),
    path('update_shares/<int:reload>', views.update_shares,
         name='reload_shares'),
    path('shares/<int:account_id>/<date:date>', views.shares),
    path('help', views.help, name='help'),
    path('rebalance/<int:owner_id>/<float:adj_pct>', views.rebalance,
         name='rebalance'),
    path('rebalanced/<int:owner_id>', views.rebalanced, name='rebalanced'),
]

