from django.contrib import admin

# Register your models here.

from .models import Account, Category, Plan


admin.site.register(Account)
admin.site.register(Category)
admin.site.register(Plan)
