# Generated by Django 3.0.5 on 2020-05-14 15:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('investment_tracker', '0004_auto_20200514_1518'),
    ]

    operations = [
        migrations.RunSQL(
          """UPDATE investment_tracker_accountshares
                SET peak_pct_of_balance = 1/pct_of_peak;"""),
        migrations.RunSQL(
          """UPDATE investment_tracker_accountshares
                SET trough_pct_of_balance = 1/pct_of_trough
              WHERE pct_of_trough is not NULL;"""),
    ]
