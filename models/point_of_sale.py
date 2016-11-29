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


    company_taxes = fields.One2many('pos.order.line.company_tax', 'order_id', 'Order Company Taxes')


    def _prepare_tax_line_vals(self, tax):
        return {
            'order_id': self.id or self._origin.id,
            'description': tax['name'],
            'tax_id': tax['id'],
            'amount': tax['amount'],
            'sequence': tax['sequence'],
            'account_id': tax['account_id'],
            'account_analytic_id': tax['analytic'] or False,
        }

    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}

        for order in self:
            if order.company_id.partner_id.property_account_position_id:
                fp = self.env['account.fiscal.position'].search(
                    [('id', '=', order.company_id.partner_id.property_account_position_id.id)])
                fp.ensure_one()

                fp_tax_ids = [tax.tax_id.id for tax in fp.tax_ids_invoice]
                tax_ids = self.env['account.tax'].browse(fp_tax_ids)
                taxes = tax_ids.compute_all(order.amount_total - order.amount_tax, order.pricelist_id.currency_id, partner=order.partner_id)['taxes']

                for tax in taxes:
                    val = self._prepare_tax_line_vals(tax)
                    key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                    if key not in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']
            else:
                raise UserError(_('Debe definir una posicion fiscal para el partner asociado a la compañía actual'))

        return tax_grouped

    @api.multi
    def _compute_company_taxes(self):
        company_tax = self.env['pos.order.line.company_tax']
        ctx = dict(self._context)

        for order in self:
            tax_grouped = order.get_taxes_values()

            for tax in tax_grouped.values():
                company_tax.create(tax)

        return self.with_context(ctx).write({'lines': []})

    @api.onchange('lines')
    def _onchange_company_taxes(self):
        tax_grouped = self.get_taxes_values()
        company_taxes = self.company_taxes.browse([])

        for value in tax_grouped.values():
            company_taxes += company_taxes.new(value)
        self.company_taxes = company_taxes
#        self.update({'company_taxes': tax_grouped.values()})
        return

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

        order = super(models.Model, self).create(values)
        if not order.company_taxes:
            order._compute_company_taxes()
        return order

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
        taxes = {}
        for order in self:


            for line in order.company_taxes:
                tax = self.env['account.tax'].browse(line.tax_id.id)
                counter_account_id = tax.account_id_counterpart.id

                key = (order.partner_id.id or "", line.tax_id.id)

                if key not in items:
                    taxes[key] = line
                else:
                    tax_line = taxes[key]
                    tax_line.amount += line.amount

            for key,line in taxes.iteritems(): 
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
                items[key] = values

            if order.company_id.anglo_saxon_accounting:
                for i_line in order.lines:
                    anglo_saxon_lines = order._anglo_saxon_sale_move_lines(i_line)
                    _logger.info(anglo_saxon_lines)
                    all_lines.extend(anglo_saxon_lines)

        map(lambda x: map (lambda y: all_lines.append((0, 0, y)), x), items.values())

        _logger.info(all_lines)
        if move_id:
            move.with_context(dont_create_taxes=True).write({'line_ids': all_lines})
            move.post()
        return res

    @api.model
    def _anglo_saxon_sale_move_lines(self, i_line):
        """Return the additional move lines for sales invoices and refunds.

        i_line: An account.invoice.line object.
        res: The move line entries produced so far by the parent move_line_get.
        """
        order = i_line.order_id
        company_currency = order.company_id.currency_id.id

        if i_line.product_id.type in ('product', 'consu'): #and i_line.product_id.valuation == 'real_time':
            fpos = i_line.order_id.fiscal_position_id
            accounts = i_line.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=fpos)
            # debit account dacc will be the output account

            dacc = accounts['stock_output'].id
            # credit account cacc will be the expense account
            cacc = accounts['expense'].id
            if dacc and cacc:
                price_unit = i_line._get_anglo_saxon_price_unit()
                return [
                    {
                        'type':'src',
                        'name': i_line.name[:64],
                        'price_unit': price_unit,
                        'quantity': i_line.qty,
                        'price': self.env['pos.order.line']._get_price(inv, company_currency, i_line, price_unit),
                        'account_id':dacc,
                        'product_id':i_line.product_id.id,
                        'uom_id':i_line.product_id.uom_id.id,
                    },
                    {
                        'type':'src',
                        'name': i_line.name[:64],
                        'price_unit': price_unit,
                        'quantity': i_line.qty,
                        'price': -1 * self.env['pos.order.line']._get_price(inv, company_currency, i_line, price_unit),
                        'account_id':cacc,
                        'product_id':i_line.product_id.id,
                        'uom_id':i_line.product_id.uom_id.id,
                    },
                ]
        return []

    # def _prepare_refund(self, cr, uid, invoice, date_invoice=None, date=None, description=None, journal_id=None, context=None):
    #     invoice_data = super(account_invoice, self)._prepare_refund(cr, uid, invoice, date_invoice, date,
    #                                                                 description, journal_id, context=context)
    #     #for anglo-saxon accounting
    #     if invoice.company_id.anglo_saxon_accounting and invoice.type == 'in_invoice':
    #         fiscal_position = self.pool.get('account.fiscal.position')
    #         for dummy, dummy, line_dict in invoice_data['invoice_line_ids']:
    #             if line_dict.get('product_id'):
    #                 product = self.pool.get('product.product').browse(cr, uid, line_dict['product_id'], context=context)
    #                 counterpart_acct_id = product.property_stock_account_output and \
    #                         product.property_stock_account_output.id
    #                 if not counterpart_acct_id:
    #                     counterpart_acct_id = product.categ_id.property_stock_account_output_categ_id and \
    #                             product.categ_id.property_stock_account_output_categ_id.id
    #                 if counterpart_acct_id:
    #                     fpos = invoice.fiscal_position_id or False
    #                     line_dict['account_id'] = fiscal_position.map_account(cr, uid,
    #                                                                           fpos,
    #                                                                           counterpart_acct_id)
    #     return invoice_data

class PosOrderLine(models.Model):
    _name = 'pos.order.line'
    _inherit = 'pos.order.line'

    def _get_anglo_saxon_price_unit(self):
        self.ensure_one()
        return self.product_id.standard_price

    @api.model
    def _get_price(self, inv, company_currency, i_line, price_unit):
        cur_obj = self.env['res.currency']
        if inv.currency_id.id != company_currency:
            price = cur_obj.with_context(date=inv.date_invoice).compute(company_currency, inv.currency_id.id, price_unit * i_line.quantity)
        else:
            price = price_unit * i_line.quantity
        return round(price, inv.currency_id.decimal_places)

class PosOrderLineCompanyTaxes(models.Model):
    _name = 'pos.order.line.company_tax'
    _order = 'sequence'

    description = fields.Char(related='tax_id.name', string="Tax description")
    account_id = fields.Many2one('account.account', string='Account',
        required=True)
    account_analytic_id = fields.Many2one('account.account', string='Analytic Account')
    amount = fields.Float("Amount")
    order_id = fields.Many2one('pos.order', string='Order', ondelete='cascade', index=True)
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
