# plan_models.py

r'''Categories, Plans and Fund assignments.

This defines three parallel structures:

 * a tree of Categories

 * a plan for each Category

 * a fund for each leaf Category

Each of these structures are designed to be shared across accounts and users.
This is done through two override fields: `owner` and `account`.

 * Leaving both fields NULL establishes a system default for all users and all
   accounts.

 * Setting the `owner` field (but leaving the `account` field NULL)
   establishes a user default for a single user.  This overrides a system
   default for all accounts owned by that user.

 * Setting the `account` field makes this element only used by that one account.
   This overrides both a system default, and a user default.
   (You may, or may not, leave the `owner` field NULL).

The overrides for the Category tree are at the parent/child link level, rather
than directly on the Category objects.
'''

from django.db import models

# Create your models here.


def field_or(field, value1, *rest_values):
    r'''Creates django "or" query expression.

    Returns a django query expression object.
    '''
    f = models.F(field)
    ans = models.Q(**{field: value1})
    for v in rest_values:
        ans |= models.Q(**{field: v})
    #print("field_or", field, value1, rest_values, ans)
    return ans

def add_context(query, account):
    r'''This modifies `query` to only select rows relevant to `account`.

    Also sorts the most relavent first (so that, for example, you can just use
    .first() on the returned query to get the desired row).

    Returns a django queryset object.
    '''
    return query.filter(field_or('owner_id', None, account.owner_id)) \
                .filter(field_or('account_id', None, account.id)) \
                .order_by(models.F('account_id').asc(nulls_last=True),
                          models.F('owner_id').asc(nulls_last=True))


class Category(models.Model):
    name = models.CharField(max_length=40)

    def __str__(self):
        return self.name

    def get_tree(self, account, depth=0, order=1):
        r'''Gets the whole Category tree for this account.

        Returns the tree as a list of Categories ordered from top to bottom.

        Each Category object has the following attributes added to it:

          - account

          - depth (from the root, starting with 0 at the root)

          - order (each Categories place in the final list of trees, starting
                   with 1)

          - plan

          - ticker (null if none assigned)

          - children (in order)

        '''
        tree = []
        order = 1

        def fill_in_cat(cat, depth=0):
            nonlocal order

            tree.append(cat)
            cat.account = account
            cat.depth = depth
            cat.order = order
            order += 1
            cat.plan = cat.get_plan(account)
            cat.ticker = cat.get_ticker(account)
            cat.children = cat.get_children(account)
            for child in cat.children:
                fill_in_cat(child, depth=depth+1)

        fill_in_cat(self)

        return tree

    def get_plan(self, account):
        r'''Returns the associated Plan object.
        '''
        return add_context(Plan.objects.filter(category=self), account).first()

    def get_ticker(self, account):
        r'''Returns the ticker associated with this Category.

        Returns None if no fund is associated with this Category.
        '''
        cf = add_context(CategoryFund.objects.filter(category=self), account) \
               .first()
        if cf is None:
            return None
        return cf.fund_id

    def get_children(self, account):
        r'''Returns a list of this Category's children.
        '''
        ans = []
        last_order = -10000
        for link in add_context(self.child_links.order_by('order'),
                                account).all():
            if link.order != last_order:
                assert link.order > last_order, \
                       "Category.child_links not ordered by `order`."
                ans.append(link.child)
                last_order = link.order
        return ans

    def check_structure(self, path=()):
        r'''Checks for child cycles.

        Returns all ids checked.
        '''
        new_path = path + (self.id,)
        if self.id in path:
            print(f"{self}: Cycle {new_path}")
            return set()
        tested = set([self.id])
        for link in self.child_links.all():
            tested.update(link.child.check_structure(new_path))
        return tested


class CategoryLink(models.Model):
    r'''Links subordinate Categories to their parent Categories.

    These links are sharable by all users, or all accounts for one user.  See
    the module doc string for more information.  The overrides are applied for
    all children with the same `order`.
    '''
    parent = models.ForeignKey(Category, on_delete=models.CASCADE,
                               related_name='child_links',
                               related_query_name='child_link')
    child = models.ForeignKey(Category, on_delete=models.CASCADE,

                              # Doesn't really make sense to use these,
                              # because how would you tell what parent is the
                              # right one?
                              related_name='parent_links',
                              related_query_name='parent_link')
    order = models.PositiveSmallIntegerField()

    # These apply to the `child`; i.e., whether this child participates in the
    # set of children for this `parent` or not.
    owner = models.ForeignKey('User', on_delete=models.CASCADE,
                              null=True, blank=True)
    account = models.ForeignKey('Account', on_delete=models.CASCADE,
                                null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['parent', 'child'],
                                    name='unique_category_links'),
        ]
        ordering = ['order']


class Plan(models.Model):
    r'''The Plan establishes a percentage for one Category.

    This Category may be either a group, or a leaf.  The percentage is applied
    to the balance of the parent Category (rather than the entire Account
    balance).

    The percentage may be specified in one of three ways:

     * A fixed dollar `amount`.  E.g., for a Cash Category.

     * A straight `percent`.

     * A fractional percentage with a `numerator` and `denominator` to get an
       exact 1/3, for example.

    These are sharable by all users, or all accounts for one user.  See
    the module doc string for more information.
    '''
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.FloatField(null=True, blank=True)
    percent = models.FloatField(null=True, blank=True)
    numerator = models.IntegerField(null=True, blank=True)
    denominator = models.IntegerField(null=True, blank=True)

    owner = models.ForeignKey('User', on_delete=models.CASCADE,
                              null=True, blank=True)
    account = models.ForeignKey('Account', on_delete=models.CASCADE,
                                null=True, blank=True)

    def __str__(self):
        if self.amount is not None:
            return f"${self.amount}"
        if self.percent is not None:
            return f"{self.percent * 100}%"
        if self.numerator is not None:
            return f"{self.numerator}/{self.denominator}"
        return "..."

    def plan_balance(self, starting_balance, remaining_balance, last=False):
        r'''Returns % of category, category_balance
        '''
        if self.amount is not None:
            return self.amount / starting_balance, self.amount
        if self.percent is not None:
            return (self.percent, starting_balance * self.percent)
        if self.numerator is not None:
            percent = self.numerator / self.denominator
            return percent, starting_balance * percent
        assert last, \
               f"Plan {self.id} has no percent and is not the last in " \
               f"its category"
        return (remaining_balance / starting_balance, remaining_balance)


class CategoryFund(models.Model):
    r'''CategoryFund identifies the Fund to use for a leaf Category. 

    These are sharable by all users, or all accounts for one user.  See
    the module doc string for more information.
    '''
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    fund = models.ForeignKey('Fund', on_delete=models.CASCADE)

    owner = models.ForeignKey('User', on_delete=models.CASCADE,
                              null=True, blank=True)
    account = models.ForeignKey('Account', on_delete=models.CASCADE,
                                null=True, blank=True)

