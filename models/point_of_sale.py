# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2016  Dominic Krimmer                                         #
#                     Luis Alfredo da Silva (luis.adasilvaf@gmail.com)        #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU Affero General Public License as published by #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU Affero General Public License for more details.                         #
#                                                                             #
# You should have received a copy of the GNU Affero General Public License    #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
###############################################################################
import logging

import openerp.addons.decimal_precision as dp
from openerp import tools, models, SUPERUSER_ID
from openerp import fields, api
from openerp.tools import float_is_zero
from openerp.tools.translate import _
from openerp.exceptions import UserError

from openerp import api, fields as Fields

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = "pos.order"

    @api.depends('amount_tax', 'amount_total')
    def _compute_company_taxes(self):
        company_tax_line = self.env['pos.order.line.company_tax']
        for order in self:
            vals = [(0, 0, {
                'description': "prueba",
                'account_id': 1234,
                'amount': 123.5,
                'order_id': order.id
            })]

            tax_grouped = {}
            if order.company_id.partner_id.property_account_position_id:
                fp = self.env['account.fiscal.position'].search(
                    [('id', '=', self.company_id.partner_id.property_account_position_id.id)])
                fp.ensure_one()

                tax_ids = self.env['account.tax'].search([('id', 'in', [tax.tax_id.id for tax in fp.tax_ids_invoice]),
                                                          ('type_tax_use', '=', 'sale')])
                for tax_id in tax_ids:
                    tax = tax_id.compute_all(order.amount_total - order.amount_tax, order.pricelist_id.currency_id, partner=order.partner_id)['taxes'][0]

                    val = {
                        'order_id': order.id,
                        'description': tax['name'],
#                        'tax_id': tax['id'],
                        'amount': tax['amount'],
#                        'sequence': tax['sequence'],
#                        'account_id': self.type in ('out_invoice', 'in_invoice') and tax['account_id'] or tax['refund_account_id'],
                        'account_id': tax['account_id']
                    }
                    _logger.info("%s" % val)
#                    key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)
                    key = tax['name']
                    if key not in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']
            else:
                raise UserError(_('Debe definir una posicion fiscal para el partner asociado a la compañía actual'))

            company_taxes = self.company_taxes.browse([])
            for tax in tax_grouped.values():
                company_taxes += company_taxes.new(tax)
            self.company_taxes = company_taxes

        return
#            res = company_tax_line.create(vals)

#        self.write({'company_taxes': res})

    company_taxes = fields.One2many('pos.order.line.company_tax', 'order_id', 'Order Company Taxes', compute=_compute_company_taxes)

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

class PosOrderLineCompanyTaxes(models.Model):
    _name = 'pos.order.line.company_tax'

    description = fields.Char(string="Tax description")
    account_id = fields.Integer("Tax Account")
    amount = fields.Float("Amount")
    order_id = fields.Many2one('pos.order', string='Order', ondelete='cascade')
