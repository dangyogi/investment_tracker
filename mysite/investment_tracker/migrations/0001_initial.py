# Generated by Django 3.0.5 on 2020-04-29 17:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40)),
                ('account_number', models.CharField(max_length=150)),
                ('shares_start_date', models.DateField(blank=True, null=True)),
                ('shares_end_date', models.DateField(blank=True, null=True)),
                ('rebalance_date', models.DateField(blank=True, null=True)),
            ],
            options={
                'ordering': ['owner', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='Fund',
            fields=[
                ('ticker', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=60, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=15)),
            ],
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.FloatField(blank=True, null=True)),
                ('percent', models.FloatField(blank=True, null=True)),
                ('numerator', models.IntegerField(blank=True, null=True)),
                ('denominator', models.IntegerField(blank=True, null=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Category')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.User')),
            ],
        ),
        migrations.CreateModel(
            name='FundPriceHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('close', models.FloatField()),
                ('peak_close', models.FloatField()),
                ('peak_date', models.DateField()),
                ('trough_close', models.FloatField(null=True)),
                ('trough_date', models.DateField(null=True)),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Fund')),
            ],
            options={
                'ordering': ['-date'],
                'get_latest_by': 'date',
            },
        ),
        migrations.CreateModel(
            name='FundDividendHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('dividends', models.FloatField()),
                ('adj_shares', models.FloatField(null=True)),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Fund')),
            ],
            options={
                'ordering': ['-date'],
                'get_latest_by': 'date',
            },
        ),
        migrations.CreateModel(
            name='CategoryLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField()),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('child', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_links', related_query_name='parent_link', to='investment_tracker.Category')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.User')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='child_links', related_query_name='child_link', to='investment_tracker.Category')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='CategoryFund',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Category')),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Fund')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.User')),
            ],
        ),
        migrations.CreateModel(
            name='AccountTransactionHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trade_date', models.DateField()),
                ('settlement_date', models.DateField()),
                ('transaction_type', models.CharField(max_length=30)),
                ('transaction_desc', models.CharField(max_length=60)),
                ('investment_name', models.CharField(max_length=60)),
                ('shares', models.FloatField()),
                ('share_price', models.FloatField()),
                ('principal_amount', models.FloatField()),
                ('commission_fees', models.FloatField()),
                ('net_amount', models.FloatField()),
                ('accrued_interest', models.FloatField()),
                ('account_type', models.CharField(max_length=20)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('fund', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='investment_tracker.Fund')),
            ],
            options={
                'ordering': ['-trade_date'],
                'get_latest_by': 'trade_date',
            },
        ),
        migrations.CreateModel(
            name='AccountShares',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('shares', models.FloatField(null=True)),
                ('share_price', models.FloatField(null=True)),
                ('balance', models.FloatField()),
                ('pct_of_peak', models.FloatField(null=True)),
                ('peak_date', models.DateField(null=True)),
                ('pct_of_trough', models.FloatField(null=True)),
                ('trough_date', models.DateField(null=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Fund')),
            ],
            options={
                'get_latest_by': 'date',
            },
        ),
        migrations.CreateModel(
            name='AccountFundHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('shares', models.FloatField()),
                ('share_price', models.FloatField()),
                ('balance', models.FloatField()),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Account')),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.Fund')),
            ],
            options={
                'ordering': ['-date'],
                'get_latest_by': 'date',
            },
        ),
        migrations.AddField(
            model_name='account',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='investment_tracker.Category'),
        ),
        migrations.AddField(
            model_name='account',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='investment_tracker.User'),
        ),
        migrations.AddConstraint(
            model_name='fundpricehistory',
            constraint=models.UniqueConstraint(fields=('fund', 'date'), name='unique_fundprice_by_date'),
        ),
        migrations.AddConstraint(
            model_name='funddividendhistory',
            constraint=models.UniqueConstraint(fields=('fund', 'date'), name='unique_funddiv_by_date'),
        ),
        migrations.AddConstraint(
            model_name='categorylink',
            constraint=models.UniqueConstraint(fields=('parent', 'child'), name='unique_category_links'),
        ),
        migrations.AddConstraint(
            model_name='accountshares',
            constraint=models.UniqueConstraint(fields=('account', 'fund', 'date'), name='unique_account_shares_per_date'),
        ),
        migrations.AddConstraint(
            model_name='accountfundhistory',
            constraint=models.UniqueConstraint(fields=('account', 'fund', 'date'), name='unique_account_fund_per_date'),
        ),
        migrations.AddConstraint(
            model_name='account',
            constraint=models.UniqueConstraint(fields=('owner', 'name'), name='unique_account_name_per_owner'),
        ),
    ]
