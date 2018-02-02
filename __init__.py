# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import stock


def register():
    Pool.register(
        stock.Template,
        stock.Lot,
        stock.Location,
        stock.Move,
        module='stock_lot_expiry', type_='model')
