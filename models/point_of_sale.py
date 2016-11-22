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
import time

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

    
    company_taxes = fields.One2many('pos.order.line.company_tax', 'order_id', 'Order Company Taxes',
                                    readonly=True)

    @api.multi
    def get_taxes_values(self):
        for order in self:
            tax_grouped = {}

            if order.company_id.partner_id.property_account_position_id:
                fp = self.env['account.fiscal.position'].search(
                    [('id', '=', order.company_id.partner_id.property_account_position_id.id)])
                fp.ensure_one()

                tax_ids = [tax.tax_id.id for tax in fp.tax_ids_invoice]
                tax_ids = self.env['account.tax'].browse(tax_ids)

                for tax_id in tax_ids:
                    tax = tax_id.compute_all(order.amount_total - order.amount_tax, order.pricelist_id.currency_id, partner=order.partner_id)['taxes'][0]

                    val = {
                        'order_id': order.id,
                        'description': tax['name'],
                        'tax_id': tax['id'],
                        'amount': tax['amount'],
                        'sequence': tax['sequence'],
                        'account_id': tax['account_id'] #or tax['']
                    }

                    key = str(tax['id']) + '-' + str(tax['account_id'])
                    if key not in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']

                return tax_grouped
            else:
                raise UserError(_('Debe definir una posicion fiscal para el partner asociado a la compañía actual'))

    @api.multi
    def _compute_company_taxes(self):
        company_tax = self.env['pos.order.line.company_tax']
        ctx = dict(self._context)

        for order in self:
            tax_grouped = order.get_taxes_values()

            for tax in tax_grouped.values():
                company_tax.create(tax)

        return self.with_context(ctx).write({'company_taxes': []})

    @api.onchange('lines.price_subtotal', 'amount_total', 'company_taxes')
    def _onchange_company_taxes(self):
        tax_grouped = self.get_taxes_values()
        company_taxes = self.company_taxes.browse([])

        for value in tax_grouped.values():
            company_taxes += company_taxes.new(value)
        self.company_taxes = company_taxes
        return

    @api.model
    def _process_order(self, order):
        order_id = super(PosOrder, self)._process_order(order)
        return order_id

    @api.model
    def _order_fields(self, ui_order):
        order = super(PosOrder, self)._order_fields(ui_order)
        return order

    @api.model
    def create(self, values):
        if values.get('session_id'):
            # set name based on the sequence specified on the config
            session = self.env['pos.session'].browse(values['session_id'])
            try:
                if 'REFUND' not in values['name']:
                    values['name'] = session.config_id.sequence_id._next()
                else:
                    values['name'] = session.config_id.sequence_refund_id._next()
            except KeyError:
                values['name'] = session.config_id.sequence_id._next()

            values.setdefault('session_id', session.config_id.pricelist_id.id)
        else:
            # fallback on any pos.order sequence
            values['name'] = self.env['ir.sequence'].next_by_code('pos.order')

        orders = super(models.Model, self).create(values)
        for order in orders:
            order._compute_company_taxes()
        return orders

    @api.multi
    def refund(self):
        abs = super(PosOrder, self).refund()

        refund_ids = abs['res_id']
        orders = self.env['pos.order'].browse(refund_ids)
        for order in orders:
            for tax in order.company_taxes:
                tax.write({'amount': -tax.amount})

        return abs

    @api.multi
    def _create_account_move_line(self, session=None, move_id=None):
        res = super(PosOrder, self)._create_account_move_line(session, move_id)

        move = self.env['account.move'].sudo().browse(move_id)
        move.ensure_one()

        all_lines = []
        items = {}
        for order in self:

            for line in order.company_taxes:
                tax = self.env['account.tax'].browse(line.tax_id.id)[0]
                counter_account_id = tax.account_id_counterpart.id

                values = [{
                    'name': line.description,
                    'quantity': 1,
                    'account_id': line.account_id.id,
                    'credit': ((line.amount>0) and line.amount) or 0.0,
                    'debit': ((line.amount<0) and -line.amount) or 0.0,
                    'tax_line_id': line.tax_id.id,
                    'partner_id': order.partner_id and self.env["res.partner"]._find_accounting_partner(order.partner_id).id or False,
                    'move_id': move_id
                },
                {
                    'name': line.description,
                    'quantity': 1,
                    'account_id': counter_account_id,
                    'credit': ((line.amount<0) and -line.amount) or 0.0,
                    'debit': ((line.amount>0) and line.amount) or 0.0,
                    'tax_line_id': line.tax_id.id,
                    'partner_id': order.partner_id and self.env["res.partner"]._find_accounting_partner(order.partner_id).id or False,
                    'move_id': move_id
                }]
                map(lambda x: all_lines.append((0, 0, x)), values)

        if move_id:
            move.with_context(dont_create_taxes=True).write({'line_ids': all_lines})
            move.post()
        return res

class PosOrderLineCompanyTaxes(models.Model):
    _name = 'pos.order.line.company_tax'

    description = fields.Char(related='tax_id.name', string="Tax description")
    account_id = fields.Many2one('account.account', string='Account',
        required=True)
    amount = fields.Float("Amount")
    order_id = fields.Many2one('pos.order', string='Order', ondelete='cascade')
    tax_id = fields.Many2one('account.tax', string='Tax', ondelete='restrict')
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of invoice tax.")

class PosConfig(models.Model):
    _name = 'pos.config'
    _inherit = 'pos.config'

    sequence_refund_id = fields.Many2one('ir.sequence', 'Refund Order IDs Sequence', readonly=True,
                                  help="This sequence is automatically created by Odoo but you can change it "\
                                  "to customize the reference numbers of your orders.", copy=False)

    @api.model
    def create(self, values):
        IrSequence = self.env['ir.sequence']

        val = {
            'name': 'POS Refund %s' % values['name'],
            'padding': 4,
            'prefix': "%s/" % values['name'],
            'code': "pos.order",
            'company_id': values.get('company_id', False)
        }
        values['sequence_refund_id'] = IrSequence.create(val).id

        return super(PosConfig, self).create(values)
