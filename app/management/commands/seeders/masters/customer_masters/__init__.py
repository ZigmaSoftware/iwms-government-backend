# core/management/commands/seeders/customers/__init__.py
from .customerCreation import CustomerCreationSeeder
from .userChargeRule import UserChargeRuleSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
    UserChargeRuleSeeder,
]
