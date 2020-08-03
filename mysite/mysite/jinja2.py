# jinja2.py

r'''Defines Jinja2 global environment.
'''

from decimal import Decimal

from django.templatetags.static import static
from django.urls import reverse

from jinja2 import Environment


def blank(value, blank_value=None):
    if value == blank_value:
        return ''
    return value


def roundto(value, decimals=2, comma=True, none_value='N/A'):
    if value is None:
        return none_value
    if not isinstance(value, (float, int, Decimal)):
        return value
    if comma:
        format_str = f"{{:,.{decimals}f}}"
    else:
        format_str = f"{{:.{decimals}f}}"
    ans = format_str.format(value)
    return ans


def dollars(value, decimals=2, none_value='N/A'):
    if value is None:
        return none_value
    if not isinstance(value, (float, int, Decimal)):
        return value
    format_str = f"${{:,.{decimals}f}}"
    ans = format_str.format(value)
    #print("dollarformat arg", repr(decimals), "format_str", repr(format_str),
    #      "ans", repr(ans))
    return ans


def percent(value, decimals=1, none_value='N/A'):
    if value is None:
        return none_value
    if not isinstance(value, (float, int, Decimal)):
        return value
    format_str = f"{{:,.{decimals}f}}%"
    ans = format_str.format(value * 100)
    #print("percent decimals", repr(decimals), "format_str", repr(format_str),
    #      "ans", repr(ans))
    return ans


def short_date(value):
    if value is None:
        return ''
    return value.strftime("%b %d")


def full_date(value):
    if value is None:
        return ''
    return value.strftime("%m/%d/%y")


def url(viewname, *args, **kwargs):
    return reverse(viewname, args=args, kwargs=kwargs)


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': url,
        'float': float,
        'str': str,
        'sum': sum,
        'abs': abs,
    })
    env.filters['blank'] = blank
    env.filters['roundto'] = roundto
    env.filters['dollars'] = dollars
    env.filters['percent'] = percent
    env.filters['short_date'] = short_date
    env.filters['full_date'] = full_date
    return env

