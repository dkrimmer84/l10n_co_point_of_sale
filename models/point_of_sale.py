import logging

import openerp.addons.decimal_precision as dp
from openerp import tools, models, SUPERUSER_ID
from openerp.osv import fields, osv
from openerp.tools import float_is_zero
from openerp.tools.translate import _
from openerp.exceptions import UserError

from openerp import api, fields as Fields

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = "pos.order"

    def _order_fields(self, cr, uid, ui_order, context=None):
        order = super(PosOrder, self)._order_fields(cr, uid, ui_order, context=context)
        return order

    def create(self, cr, uid, values, context=None):
        if values.get('session_id'):
            # set name based on the sequence specified on the config
            session = self.pool['pos.session'].browse(cr, uid, values['session_id'], context=context)
            values['name'] = session.config_id.sequence_id._next()
            values.setdefault('session_id', session.config_id.pricelist_id.id)
        else:
            # fallback on any pos.order sequence
            values['name'] = self.pool.get('ir.sequence').next_by_code(cr, uid, 'pos.order', context=context)
        return super(models.Model, self).create(cr, uid, values, context=context)

