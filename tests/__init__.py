# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.stock_lot_expiry.tests.test_stock_lot_expiry import suite
except ImportError:
    from .test_stock_lot_expiry import suite

__all__ = ['suite']
