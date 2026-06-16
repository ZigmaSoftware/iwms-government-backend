# core/management/commands/seeders/base.py
from django.db import transaction

class BaseSeeder:
    name = "base"

    @transaction.atomic
    def run(self):
        raise NotImplementedError("---Seeder must implement run()---")

    def log(self, message):
        print(f"[{self.name.upper()}] {message}")

    def log_error(self, message):
        print(f"[{self.name.upper()} ERROR] {message}")