# Generated by Django 3.0.5 on 2020-04-29 19:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investment_tracker', '0002_auto_20200429_1706'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='transaction_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='account',
            name='transaction_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.DeleteModel(
            name='AccountFundHistory',
        ),
    ]
