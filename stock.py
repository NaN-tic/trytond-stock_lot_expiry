# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import date, timedelta

from trytond.model import Workflow, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

__all__ = ['Lot', 'Location', 'Move']


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    expired = fields.Function(fields.Boolean('Expired'),
        'get_expired', searcher='search_expired')

    def get_rec_name(self, name):
        rec_name = super(Lot, self).get_rec_name(name)
        if self.expired:
            rec_name += ' (%s)' % gettext('stock_lot_expiry.expired')
        return rec_name

    def get_expired(self, name):
        pool = Pool()
        Date = pool.get('ir.date')

        if not self.expiration_date:
            return False

        context = Transaction().context
        date = Date.today()
        if context.get('stock_move_date'):
            date = context['stock_move_date']
        elif context.get('stock_date_end'):
            date = context['stock_date_end']
        return self.expiration_date <= date

    @classmethod
    def search_expired(cls, name, domain=None):
        pool = Pool()
        Date = pool.get('ir.date')

        if not domain:
            return []

        context = Transaction().context
        date = Date.today()
        if context.get('stock_move_date'):
            date = context['stock_move_date']
        elif context.get('stock_date_end'):
            date = context['stock_date_end']
        _, op, operand = domain
        search_expired = (op == '=' and operand
            or op == '!=' and not operand)
        if search_expired:
            return [
                ('expiration_date', '!=', None),
                ('expiration_date', '<=', date),
                ]
        else:
            return [
                'OR', [
                    ('expiration_date', '=', None),
                    ], [
                    ('expiration_date', '>', date),
                    ]]


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    expired = fields.Boolean('Expired Products\' Location',
        help='This option identifies this location as a container for expired '
        'products (provably it is a temporal location until the product is '
        'returned or removed).\n'
        'Take care that if you set this location as a child of the Storage '
        'location of a Warehouse, the products in this location will be '
        'computed as available stock.')
    allow_expired = fields.Boolean('Allow Expired', states={
            'invisible': Eval('expired', False),
            }, depends=['expired'],
        help='Check this option to allow move expired lots to this location.')

    @fields.depends('expired', 'allow_expired')
    def on_change_expired(self):
        if self.expired:
            self.allow_expired = True

    @classmethod
    def create(cls, vlist):
        for vals in vlist:
            if vals.get('expired'):
                vals['allow_expired'] = True
        return super(Location, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for locations, values in zip(actions, actions):
            if values.get('expired'):
                values['allow_expired'] = True
            args.extend((locations, values))
        super(Location, cls).write(*args)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    to_location_allow_expired = fields.Function(
        fields.Boolean('Destination Allow Expired'),
        'on_change_with_to_location_allow_expired')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.lot.domain.append(
            If((Eval('state', 'draft') == 'draft')
                & ~Eval('to_location_allow_expired'),
                ('expired', '=', False),
                ()),
            )
        if not cls.lot.context:
            cls.lot.context = {}
        cls.lot.context['stock_move_date'] = If(
            Bool(Eval('effective_date', False)),
            Eval('effective_date'),
            Eval('planned_date'))

        cls.lot.loading = 'lazy'

        for fname in ('state', 'to_location_allow_expired', 'effective_date',
                'planned_date'):
            if fname not in cls.lot.depends:
                cls.lot.depends.append(fname)

    @fields.depends('to_location')
    def on_change_with_to_location_allow_expired(self, name=None):
        return self.to_location and self.to_location.allow_expired or False

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        for move in moves:
            move.check_allow_lot_expired()
        super(Move, cls).do(moves)

    def check_allow_lot_expired(self):
        if self.to_location.allow_expired or not self.lot:
            return

        error = False
        with Transaction().set_context(stock_move_date=self.effective_date):
            error = not self.to_location.allow_expired and self.lot.expired
        if error:
            self.raise_user_error('expired_lot_invalid_destination', {
                    'move': self.rec_name,
                    'lot': self.lot.rec_name,
                    'to_location': self.to_location.rec_name,
                    })
