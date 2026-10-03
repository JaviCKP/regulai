from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .models import Engine, EngineModel


class PriceUnitsTests(TestCase):
    def test_price_per_token_is_rejected_and_free_or_per_million_price_is_valid(self):
        engine = Engine.objects.create(name='Price boundary')
        model = EngineModel(engine=engine, name='Price', model_id='price')
        for value in ('0.00000001', '0.00009999'):
            model.input_price = Decimal(value)
            with self.assertRaises(ValidationError):
                model.full_clean()
        for value in ('0', '0.0001', '2.50'):
            model.input_price = model.output_price = Decimal(value)
            model.full_clean()


class PriceUnitsMigrationTests(TransactionTestCase):
    def test_old_prices_survive_forward_and_reverse_and_units_are_explicit(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [('front', '0028_auditlog_company')]
        target = [('front', '0029_model_price_units')]
        try:
            executor.migrate(old_target)
            old = executor.loader.project_state(old_target).apps
            engine = old.get_model('front', 'Engine').objects.create(name='Old prices')
            model = old.get_model('front', 'EngineModel').objects.create(engine_id=engine.pk,
                name='Old', model_id='old', input_price=Decimal('2.5'), output_price=Decimal('0'))
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            migrated = executor.loader.project_state(target).apps.get_model('front', 'EngineModel')
            retained = migrated.objects.get(pk=model.pk)
            self.assertEqual(retained.input_price, Decimal('2.5'))
            self.assertEqual(retained.output_price, Decimal('0'))
            self.assertIn('USD per million', migrated._meta.get_field('input_price').help_text)
            retained.input_price = Decimal('0.00001')
            with self.assertRaises(ValidationError):
                retained.full_clean()
            MigrationExecutor(connection).migrate(old_target)
            self.assertEqual(old.get_model('front', 'EngineModel').objects.get(pk=model.pk).input_price, Decimal('2.5'))
        finally:
            MigrationExecutor(connection).migrate(latest)
