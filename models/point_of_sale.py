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
from datetime import datetime

from uuid import getnode as get_mac
from openerp import api, fields as Fields
import locale
from openerp.tools.misc import formatLang

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = "pos.order"

    company_taxes = fields.One2many('pos.order.line.company_tax', 'order_id', 'Order Company Taxes')
    type = fields.Selection([
        ('out_invoice','Customer Invoice'),
        ('out_refund','Customer Refund')
    ], readonly=True, default='out_invoice')
    resolution_number = fields.Char('Resolution number in order')
    resolution_date = fields.Date()
    resolution_number_from = fields.Integer("")
    resolution_number_to = fields.Integer("")


    def _prepare_tax_line_vals(self, tax):
        return {
            'order_id': self.id or self._origin.id,
            'name': tax['name'],
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
        return

    @api.model
    def create(self, values):
        if values.get('session_id'):
            # set name based on the sequence specified on the config
            session = self.env['pos.session'].browse(values['session_id'])
            sequence = None
            try:
                if 'REFUND' not in values['name']:
                    values['name'] = session.config_id.sequence_id._next()
                    sequence = self.env['ir.sequence.dian_resolution'] \
                                   .search([('sequence_id','=',session.config_id.sequence_id.id),
                                            ('active_resolution','=',True)], limit=1)
                else:
                    values['name'] = session.config_id.sequence_refund_id._next()
                    sequence = self.env['ir.sequence.dian_resolution'] \
                                   .search([('sequence_id','=',session.config_id.sequence_refund_id.id),
                                            ('active_resolution','=',True)], limit=1)
            except KeyError:
                values['name'] = session.config_id.sequence_id._next()

            values.setdefault('session_id', session.config_id.pricelist_id.id)
        else:
            # fallback on any pos.order sequence
            values['name'] = self.env['ir.sequence'].next_by_code('pos.order')

        values['resolution_number'] = sequence['resolution_number']
        values['resolution_number_from'] = sequence['number_from']
        values['resolution_number_to'] = sequence['number_to']
        values['resolution_date'] = sequence['date_from']

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
            order.write({'type': 'out_refund'})
            for tax in order.company_taxes:
                tax.write({'amount': -tax.amount})

        return abs

    def _prepare_tax_vals(self, line, partner_id):
        vals = {
            'name': line.name,
            'account_id': line.account_id.id,
            'amount': line.amount,
            'tax_id': line.tax_id.id,
            'partner_id': partner_id
        }
        return vals

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
                key = (order.type, order.partner_id.id or "", line.tax_id.id)
                val = self._prepare_tax_vals(line, order.partner_id)

                if key not in items:
                    taxes[key] = val
                else:
                    taxes[key]['amount'] += val['amount']

            if order.company_id.anglo_saxon_accounting:
                for i_line in order.lines:
                    anglo_saxon_lines = order._anglo_saxon_sale_move_lines(i_line)
                    all_lines.extend(anglo_saxon_lines)

        for key,val in taxes.iteritems():
            type, dummy, dummy = key
            if type in 'out_refund':
                name = 'Refund ' + val['name']
            else:
                name = val['name']

            tax = self.env['account.tax'].browse(val['tax_id'])
            counter_account_id = tax.account_id_counterpart.id

            values = [{
                'name': name[:64],
                'quantity': 1,
                'account_id': val['account_id'],
                'credit': ((val['amount']>0) and val['amount']) or 0.0,
                'debit': ((val['amount']<0) and -val['amount']) or 0.0,
                'tax_line_id': val['tax_id'],
                'partner_id': val['partner_id'] and self.env["res.partner"]._find_accounting_partner(val['partner_id']).id or False,
                'move_id': move_id
            },
            {
                'name': name[:64],
                'quantity': 1,
                'account_id': counter_account_id,
                'credit': ((val['amount']<0) and -val['amount']) or 0.0,
                'debit': ((val['amount']>0) and val['amount']) or 0.0,
                'tax_line_id': val['tax_id'],
                'partner_id': val['partner_id'] and self.env["res.partner"]._find_accounting_partner(val['partner_id']).id or False,
                'move_id': move_id
            }]
            items[key] = values

        map(lambda x: map (lambda y: all_lines.append((0, 0, y)), x), items.values())

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
                price = self.env['pos.order.line']._get_price(order, company_currency, i_line, price_unit)
                return [
                    (0, 0, {
                        'name': i_line.name[:64],
                        'debit': ((price<0) and -price) or 0.0,
                        'credit': ((price>0) and price) or 0.0,
                        'account_id': dacc,
                        'quantity': i_line.qty,
                        'product_id': i_line.product_id.id,
                        'product_uom_id': i_line.product_id.uom_id.id,
                        'partner_id': order.partner_id and self.env["res.partner"]._find_accounting_partner(order.partner_id).id or False,
                        'move_id': order.account_move.id
                    }),
                    (0, 0, {
                        'name': i_line.name[:64],
                        'debit': ((price>0) and price) or 0.0,
                        'credit': ((price<0) and -price) or 0.0,
                        'account_id': cacc,
                        'quantity': i_line.qty,
                        'product_id': i_line.product_id.id,
                        'product_uom_id': i_line.product_id.uom_id.id,
                        'partner_id': order.partner_id and self.env["res.partner"]._find_accounting_partner(order.partner_id).id or False,
                        'move_id': order.account_move.id
                    }),
                ]
        return []


class PosOrderLine(models.Model):
    _name = 'pos.order.line'
    _inherit = 'pos.order.line'
    price_subtotal_line = fields.Float('Subtotal', compute='_compute_amount_line_all', digits=0, store=True)

    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        for line in self:
            currency = line.order_id.pricelist_id.currency_id
            taxes = line.tax_ids.filtered(lambda tax: tax.company_id.id == line.order_id.company_id.id)
            fiscal_position_id = line.order_id.fiscal_position_id
            if fiscal_position_id:
                taxes = fiscal_position_id.map_tax(taxes)
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.price_subtotal_incl = price * line.qty
            if taxes:
                taxes = taxes.compute_all(price, currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                line.price_subtotal = taxes['total_excluded']
                line.price_subtotal_incl = taxes['total_included']

            line.price_subtotal = currency.round(line.price_subtotal)
            line.price_subtotal_incl = currency.round(line.price_subtotal_incl)
            line.price_subtotal_line =  line.price_subtotal

    def _get_anglo_saxon_price_unit(self):
        self.ensure_one()
        if self.order_id.picking_id:
            move = self.order_id.picking_id.move_lines.search([('picking_id','=',self.order_id.picking_id.id),
                                                               ('product_id','=',self.product_id.id)])
        return move[0].price_unit

    @api.model
    def _get_price(self, order, company_currency, i_line, price_unit):
        cur_obj = self.env['res.currency']
        if order.company_id.currency_id.id != company_currency:
            price = cur_obj.with_context(date=order.create_date).compute(company_currency, order.company_id.currency_id.id, price_unit * i_line.qty)
        else:
            price = price_unit * i_line.qty
        return round(price, order.company_id.currency_id.decimal_places)


class PosOrderLineCompanyTaxes(models.Model):
    _name = 'pos.order.line.company_tax'
    _order = 'sequence'

    name = fields.Char(string="Tax description", required=True)
    account_id = fields.Many2one('account.account', string='Account',
        required=True)
    account_analytic_id = fields.Many2one('account.account', string='Analytic Account')
    amount = fields.Float("Amount")
    order_id = fields.Many2one('pos.order', string='Order', ondelete='cascade', index=True)
    tax_id = fields.Many2one('account.tax', string='Tax', ondelete='restrict', required=True)
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of invoice tax.")


class PosConfig(models.Model):
    _name = 'pos.config'
    _inherit = 'pos.config'

    @api.multi
    def _get_has_valid_dian_info(self):
        for pos in self:
            if pos.sequence_id.use_dian_control:
                remaining_numbers = pos.sequence_id.remaining_numbers
                remaining_days = pos.sequence_id.remaining_days
                dian_resolution = pos.env['ir.sequence.dian_resolution'].search([('sequence_id','=',pos.sequence_id.id),('active_resolution','=',True)])
                today = datetime.strptime(fields.Date.context_today(pos), '%Y-%m-%d')

                if len(dian_resolution) > 0:
                    dian_resolution.ensure_one()
                    date_to = datetime.strptime(dian_resolution['date_to'], '%Y-%m-%d')
                    days = (date_to - today).days

                    pos.not_has_valid_dian = False
                    spent = False

                    if dian_resolution['number_to'] - dian_resolution['number_next'] < remaining_numbers or days < remaining_days:
                        pos.not_has_valid_dian = True
                    if dian_resolution['number_next'] > dian_resolution['number_to']:
                        spent = True
                    if spent:
                        pass # This is when the resolution it's spent and we keep generating numbers

    not_has_valid_dian = fields.Boolean(compute='_get_has_valid_dian_info', default=False)
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

class pos_session(models.Model):
    _inherit = 'pos.session'

    taxes_description = fields.Html('taxes Description', compute = 'compute_taxes_description')
    amount_change = fields.Float('Change', compute = 'compute_amount_change')
    mac = fields.Char('MAC')
    macpc = get_mac()

    @api.model
    def create(self, values):
        macpc = get_mac()
        values.update({'mac' : macpc})

        res = super(pos_session, self).create(values)

        if res:
            pass
            #self.val_metodos_pago_ids( res )

        return res 

    def number_format( self, currency_id, amount ):
        return formatLang(self.env, amount, currency_obj = currency_id, digits=0 ).replace(",", ".")

    @api.one
    def compute_amount_change(self):

        res = {}
        currency_id = False
        _change = 0
        if self.order_ids:
            for order in self.order_ids:
                for change  in order.statement_ids:
                    if change.amount < 0:  
                        _change = _change + change.amount           

        #html = """
        #<div style="float: left;margin-right: 20px;"><strong>Amount Change : </strong></div><div><span>%s</span></div>
        #""" % (self.number_format(currency_id, _change))
        self.amount_change = _change    


    @api.one
    def compute_taxes_description(self):

        res = {}
        currency_id = False
        _cambio = 0
        if self.order_ids:
            for order in self.order_ids:
                if order.lines:
                    for line in order.lines:
                        _id_tax = line.tax_ids_after_fiscal_position.id

                        if line.tax_ids_after_fiscal_position.price_include:
                            subtotal = round((line.price_unit / (1 + (line.tax_ids_after_fiscal_position.amount/100))) * line.qty, 0)
                        else:
                            subtotal = round(line.price_unit * line.qty, 0)
                        discount_line = round((subtotal * line.discount)/100 , 0)
                        tax_line = round(((subtotal - discount_line) * line.tax_ids_after_fiscal_position.amount)/100 , 0)
                        total = round((subtotal + tax_line - discount_line) , 0)

                        if _id_tax in res:
                            data = res[_id_tax]
                            subtotal = data.get('subtotal') + subtotal
                            discount_line = data.get('discount_line') + discount_line
                            tax_line = data.get('tax_line') + tax_line
                            total = data.get('total') + total

                            res[_id_tax] = {
                                'id' : _id_tax,
                                'name' : line.tax_ids_after_fiscal_position.name,
                                'subtotal' : subtotal,
                                'discount_line' : discount_line,
                                'tax_line' : tax_line,
                                'total' : total
                            }

                        else:
                            res[_id_tax] = {
                                'id' : _id_tax,
                                'name' : line.tax_ids_after_fiscal_position.name,
                                'subtotal' : subtotal,
                                'discount_line' : discount_line,
                                'tax_line' : tax_line,
                                'total' : total
                            }               
        html = ''
        for result in res:
            html += """
            <div><h4><strong>%s : </strong><span>%s</span></h4></div>
            <div style="float: left;margin-right: 20px;"><strong>%s :</strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="margin-bottom: 10px;float: left;margin-right: 20px;"><strong>Total : </strong>
            </div><div><span>$ %s</span></div>""" % (_('Sales POS - Tax'), res[result].get('name'), _('Sales'),
                                             self.number_format(currency_id, res[result].get('subtotal')), _('Discount'),
                                             self.number_format(currency_id, res[result].get('discount_line')), _('Subtotal'),
                                             self.number_format(currency_id, res[result].get('subtotal') -
                                                                              res[result].get('discount_line')), _('Tax iva'),
                                             self.number_format(currency_id, res[result].get('tax_line')),
                                             self.number_format(currency_id, res[result].get('total')))
        self.taxes_description = html 



