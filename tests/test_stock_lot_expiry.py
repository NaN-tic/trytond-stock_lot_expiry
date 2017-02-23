# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.modules.company.tests import create_company, set_company


class TestStockLotExpiryCase(ModuleTestCase):
    'Test Stock Lot Expiry module'
    module = 'stock_lot_expiry'

    @with_transaction()
    def test0010_lot_on_change_product_and_expired(self):
        'Test Lot.on_change_product() and Lot.expired'
        pool = Pool()
        Lot = pool.get('stock.lot')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        transaction = Transaction()

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test Lot.on_change_product() and Lot.expired',
                    'type': 'goods',
                    'consumable': True,
                    'list_price': Decimal(1),
                    'cost_price': Decimal(0),
                    'cost_price_method': 'fixed',
                    'default_uom': unit.id,
                    'life_time': 20,
                    'expiry_time': 10,
                    'alert_time': 5,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        lot, lot2, = Lot.create([{
                    'number': '001',
                    'product': product.id,
                    }, {
                    'number': '002',
                    'product': product.id,
                    }])
        lot.on_change_product()
        lot.save()

        today = datetime.date.today()
        self.assertEqual(lot.life_date, (today + relativedelta(days=20)))
        self.assertEqual(lot.expiry_date, (today + relativedelta(days=10)))
        self.assertEqual(lot.removal_date, None)
        self.assertEqual(lot.alert_date, (today + relativedelta(days=5)))

        self.assertEqual(lot2.expiry_date, None)

        with transaction.set_context(stock_move_date=today):
            self.assertEqual(Lot(lot.id).expired, False)
            self.assertEqual(Lot(lot2.id).expired, False)
        with transaction.set_context(
                stock_move_date=(today + relativedelta(days=10))):
            self.assertEqual(Lot(lot.id).expired, True)
            self.assertEqual(Lot(lot2.id).expired, False)

    @with_transaction()
    def test0020_move_check_allow_expired(self):
        '''
        Test Lot check_allow_expired.
        '''
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        company = create_company()
        with set_company(company):

            unit, = Uom.search([('name', '=', 'Unit')])
            template, = Template.create([{
                        'name': 'Test Lot.on_change_product() and Lot.expired',
                        'type': 'goods',
                        'consumable': True,
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'life_time': 20,
                        'expiry_time': 10,
                        'alert_time': 5,
                        }])
            product, = Product.create([{
                        'template': template.id,
                        }])
            lot, lot2, = Lot.create([{
                        'number': '001',
                        'product': product.id,
                        }, {
                        'number': '002',
                        'product': product.id,
                        }])
            lot.on_change_product()
            lot.save()
            self.assertEqual(lot.expiry_date,
                datetime.date.today() + datetime.timedelta(days=10))

            lost_found, = Location.search([('type', '=', 'lost_found')])

            storage, = Location.search([('code', '=', 'STO')])
            storage.allow_expired = True
            storage.save()

            expired_loc, not_allowed_expired_loc = Location.create([{
                        'name': 'Expired Location',
                        'type': 'storage',
                        'expired': True,
                        'parent': storage.parent.id,
                        }, {
                        'name': 'Not Allowed Expired Location',
                        'type': 'storage',
                        'allow_expired': False,
                        'parent': storage.id,
                        }])
            self.assertEqual(expired_loc.allow_expired, True)

            today = datetime.date.today()
            expired_date = today + relativedelta(days=10)

            not_allowed_move, = Move.create([{
                        'product': product.id,
                        'lot': lot.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': lost_found.id,
                        'to_location': not_allowed_expired_loc.id,
                        'planned_date': today,
                        'unit_price': Decimal('1'),
                        }])
            not_allowed_move.effective_date = expired_date
            not_allowed_move.save()

            moves = Move.create([{
                        'product': product.id,
                        'lot': lot.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': lost_found.id,
                        'to_location': not_allowed_expired_loc.id,
                        'planned_date': today,
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'lot': lot.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'planned_date': expired_date,
                        'effective_date': expired_date,
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'lot': lot.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': lost_found.id,
                        'to_location': expired_loc.id,
                        'planned_date': expired_date,
                        'effective_date': expired_date,
                        'unit_price': Decimal('1'),
                        }])
            Move.do(moves)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        TestStockLotExpiryCase))
    return suite
