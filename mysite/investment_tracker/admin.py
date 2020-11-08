from django.contrib import admin

# Register your models here.

from .models import (
    User, Account, Category, CategoryLink, Plan, CategoryFund, Fund
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    ordering = ('name',)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'name')
    ordering = ('owner', 'name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    ordering = ('name',)


@admin.register(CategoryLink)
class CategoryLinkAdmin(admin.ModelAdmin):
    list_display = ('parent', 'child', 'owner', 'account', 'order')
    ordering = ('parent__name', 'order')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('category', 'owner', 'account', '__str__')
    ordering = ('category__name', 'owner__name', 'account__name')


@admin.register(CategoryFund)
class CategoryFundAdmin(admin.ModelAdmin):
    list_display = ('category', 'owner', 'account', 'fund')
    ordering = ('category__name', 'owner__name', 'account__name')


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticker')
    ordering = ('name',)
