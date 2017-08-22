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
from openerp.osv import osv

_logger = logging.getLogger(__name__)



"""class PosAccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    base_tax = fields.Float('Base Tax')"""

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
    resolution_date_to = fields.Date()
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
            tipo_factura = 'sale'
            if order.type in ('in_invoice', 'in_refund'):
                tipo_factura = 'purchase'
            if order.company_id.partner_id.property_account_position_id:
                fp = self.env['account.fiscal.position'].search(
                    [('id', '=', order.company_id.partner_id.property_account_position_id.id)])
                
                fp.ensure_one()
                
                for taxs in fp.tax_ids_invoice:
                    sql_diarios = "Select * from account_journal_taxes_ids_rel slt where tax_id = "+ str(taxs.id)+"" 
                    self.env.cr.execute( sql_diarios )
                    records = self.env.cr.dictfetchall()

                    if not records:
                        tax_ids = self.env['account.tax'].browse(taxs.tax_id.id)
                        
                        if tax_ids.type_tax_use == tipo_factura:

                            taxes = tax_ids.compute_all(order.amount_total - order.amount_tax, order.pricelist_id.currency_id, partner=order.partner_id)['taxes']
                            for tax in taxes:
                                val = self._prepare_tax_line_vals(tax)
                                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                                if key not in tax_grouped:
                                    tax_grouped[key] = val
                                else:
                                    tax_grouped[key]['amount'] += val['amount']
                        
                    else:        
                        for loc in records:
                            if loc.get('journal_id') == order.sale_journal.id:
                                ql_tax_id = "Select tax_id from account_fiscal_position_base_tax slt where id = "+ str(loc.get('tax_id'))+"" 
                                self.env.cr.execute( ql_tax_id )
                                records = self.env.cr.dictfetchall()
                                fp_tax_ids = [tax.get('tax_id') for tax in records]
                                tax_ids = self.env['account.tax'].browse(fp_tax_ids)
                                if tax_ids.type_tax_use == tipo_factura:
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
        order = super(models.Model, self).create(values)
        if values.get('session_id'):


            # set name based on the sequence specified on the config
            session = self.env['pos.session'].browse(values['session_id'])
            sequence = None

            if 'REFUND' not in values['name'] and order.amount_total > 0:
                values['name'] = session.config_id.sequence_id._next()
                sequence = self.env['ir.sequence.dian_resolution'] \
                               .search([('sequence_id','=',session.config_id.sequence_id.id),
                                        ('active_resolution','=',True)], limit=1)
            else:
                values['name'] = session.config_id.sequence_refund_id._next()
                sequence = self.env['ir.sequence.dian_resolution'] \
                               .search([('sequence_id','=',session.config_id.sequence_refund_id.id),
                                        ('active_resolution','=',True)], limit=1)
            if sequence.exists():
                order.write({
                    'resolution_number': sequence['resolution_number'],
                    'resolution_number_from': sequence['number_from'],
                    'resolution_number_to': sequence['number_to'],
                    'resolution_date': sequence['date_from'],
                    'resolution_date_to': sequence['date_to']
                })
            values.setdefault('session_id', session.config_id.pricelist_id.id)
        else:
            # fallback on any pos.order sequence
            values['name'] = self.env['ir.sequence'].next_by_code('pos.order')
        if order.amount_total < 0:
            _type = 'out_refund'
        else:
            _type = 'out_invoice'
        order.write({
            'name': values['name'],
            'type' : _type
        })
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

                if key not in taxes:
                    taxes[key] = val
                else:
                    taxes[key]['amount'] += val['amount']
                    #taxes[key]['subtotal'] += val['subtotal']
                   
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

                price_unit = i_line._get_anglo_saxon_price_unit() or 0.0
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

    @api.model
    def create(self, values):   

        if 'order_id' in values:
            pos_order = self.env['pos.order']
            order_id = pos_order.browse( values.get('order_id') )

            if order_id:
                if order_id.session_id:
                    if order_id.session_id.config_id:
                        values.update({
                            'name' : order_id.session_id.config_id.name
                        })

        res = super(PosOrderLine, self).create(values)

        return res

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
    refund_description = fields.Html('Refund Description', compute = 'compute_refund_description')
    amount_change = fields.Float('Change', compute = 'compute_amount_change')
    mac = fields.Char('MAC')
    macpc = get_mac()

    @api.multi
    def _confirm_orders(self):
        res = super(pos_session, self)._confirm_orders()
        if res:
            aml_model = self.env['account.move.line']
            for order in self.order_ids:
                currency = False
                for aml in order.account_move.line_ids:

                    if aml.account_id.reconcile and not aml.full_reconcile_id:
                        if not currency and aml.currency_id.id:
                            currency = aml.currency_id.id


                        condition = [('ref', '=', aml.ref),('account_id', '=', aml.account_id.id),
                        ('name', 'ilike', order.name),('full_reconcile_id', '=', False)]

                        if aml.partner_id:
                            condition.append( ('partner_id', '=', aml.partner_id.id) )
                        else:
                            condition.append( ('partner_id', '=', False) )

                        if order.amount_total > 0:
                            condition.append( ('credit', '>', 0) ) 
                        elif order.amount_total < 0:
                            condition.append( ('debit', '>', 0) ) 
                            

                        aml2_id = aml_model.search(condition)

                        if aml2_id:
                            if len( aml2_id ) == 1:
                                move_lines = aml_model.browse([ aml.id, aml2_id.id ])
                                move_lines.with_context(skip_full_reconcile_check='amount_currency_excluded', manual_full_reconcile_currency=currency).reconcile()
                                move_lines_filtered = move_lines.filtered(lambda aml: not aml.reconciled)
                                if move_lines_filtered:
                                    move_lines_filtered.with_context(skip_full_reconcile_check='amount_currency_only', manual_full_reconcile_currency=currency).reconcile()
                                move_lines.compute_full_after_batch_reconcile()

        return res    

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
    def first_orden(self):
        res = {}
        _order_first = False
        i = -1
        if self.order_ids:
            for order in self.order_ids:
                if self.order_ids[i].type != 'out_refund':
                    _order_first = self.order_ids[i].name
                    break
                else:
                    i = i - 1
        
        return _order_first         
    @api.one
    def ultima_orden(self):
        res = {}
        _order_end = False
        i = 0
        if self.order_ids:
            for order in self.order_ids:
                _logger.info(self.order_ids[i])
                if self.order_ids[i].type != 'out_refund':
                    _order_end = self.order_ids[i].name
                    break
                else:
                    i = i + 1
        
        return _order_end                    

    @api.one
    def compute_amount_change(self):

        res = {}
        currency_id = False
        _change = 0
        if self.order_ids:
            for order in self.order_ids:
                if order.type != 'out_refund':
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
        resul = {}
        currency_id = False
        _cambio = 0
        if self.order_ids:
            for order in self.order_ids:
                if order.type != 'out_refund':
                    if order.lines:

                        for line in order.lines:
                            _id_tax = line.tax_ids_after_fiscal_position.id
                            
                            if line.tax_ids_after_fiscal_position.price_include: 
                                discount_line = round((((line.price_unit / (1 + (line.tax_ids_after_fiscal_position.amount /100))) * line.qty) * line.discount)/100 , 0)
                            else:
                                discount_line = round(((line.price_unit  * line.qty) * line.discount)/100 , 0)
                            subtotal = line.price_subtotal
                            tax_line = line.price_subtotal_incl - line.price_subtotal
                            total = subtotal + tax_line
                            
                            if _id_tax in res:
                                data = res[_id_tax]
                                discount_line = data.get('discount_line') + discount_line
                                subtotal = data.get('subtotal') + subtotal
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
            <div><h4><strong>%s </strong><span>%s</span></h4></div>
            <div style="float: left;margin-right: 20px;"><strong>%s :</strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="margin-bottom: 10px;float: left;margin-right: 20px;"><strong>Total : </strong>
            </div><div><span>$ %s</span></div>""" % (_('Sales POS - Tax'), res[result].get('name'), _('Sales'),
                                             self.number_format(currency_id, res[result].get('subtotal') + res[result].get('discount_line')), _('Discount'),
                                             self.number_format(currency_id, res[result].get('discount_line')), _('Subtotal'),
                                             self.number_format(currency_id, res[result].get('subtotal')), _('Tax iva'),
                                             self.number_format(currency_id, res[result].get('tax_line')),
                                             self.number_format(currency_id, res[result].get('total')))
        
        self.taxes_description = html
        

    @api.one
    def compute_refund_description(self):
        resul = {}
        currency_id = False
        _cambio = 0
        n = 0
        if self.order_ids:
            for order in self.order_ids:
                if order.type == 'out_refund':
                    n += 1
                    if order.lines:
                        for line in order.lines:
                            _id_tax = line.tax_ids_after_fiscal_position.id
                            
                            subtotal_dev = line.price_subtotal
                            tax_line_dev = line.price_subtotal_incl - line.price_subtotal
                            total_dev = subtotal_dev + tax_line_dev
                            

                            if _id_tax in resul:
                                data = resul[_id_tax]
                                subtotal_dev = data.get('subtotal') + subtotal_dev
                                tax_line_dev = data.get('tax_line') + tax_line_dev
                                total_dev = data.get('total') + total_dev

                                resul[_id_tax] = {
                                    'id' : _id_tax,
                                    'name' : line.tax_ids_after_fiscal_position.name,
                                    'subtotal' : subtotal_dev,
                                    'tax_line' : tax_line_dev,
                                    'total' : total_dev
                                }

                            else:
                                resul[_id_tax] = {
                                    'id' : _id_tax,
                                    'name' : line.tax_ids_after_fiscal_position.name,
                                    'subtotal' : subtotal_dev,
                                    'tax_line' : tax_line_dev,
                                    'total' : total_dev
                                }

        
        html_dev = ''
        for resultado in resul:
            html_dev += """
            <div><h4><strong>%s </strong><span>%s</span></h4></div>
            <div style="float: left;margin-right: 20px;"><strong>%s :</strong></div><div><span>%s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s :</strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="float: left;margin-right: 20px;"><strong>%s : </strong></div><div><span>$ %s</span></div>
            <div style="margin-bottom: 10px;float: left;margin-right: 20px;"><strong>Total : </strong>
            </div><div><span>$ %s</span></div>""" % (_('Devoluciones POS - Tax'), resul[resultado].get('name'),
                                             _('Number Refunds'), n , _('Devoluciones'),
                                             self.number_format(currency_id, resul[resultado].get('subtotal')),
                                             _('Subtotal'),self.number_format(currency_id, resul[resultado].get('subtotal')), _('Refund Tax iva'),
                                             self.number_format(currency_id, resul[resultado].get('tax_line')),
                                             self.number_format(currency_id, resul[resultado].get('total')))
        self.refund_description = html_dev

class account_cashbox_bank_statement(models.Model):
    _name = 'account.bank.statement.cashbox'
    _inherit = 'account.bank.statement.cashbox'

    @api.model
    def default_get(self, vals):   

        result = super(account_cashbox_bank_statement, self).default_get(vals)

        _cashbox_lines_ids = []
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 100000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 50000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 20000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 10000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 5000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 2000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 1000,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 500,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 200,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 100,'number' : 0,'subtotal' : 0}) )
        _cashbox_lines_ids.append( (0,0,{'coin_value' : 50,'number' : 0,'subtotal' : 0}) )

        

        result.update({
            'cashbox_lines_ids' : _cashbox_lines_ids
        })

        
        return result

class inherit_report_pos_order(models.Model):
    _name = 'report.pos.order'
    _inherit = 'report.pos.order'

    costo_total = fields.Float('Costo Total', readonly=True)
    costo_promedio = fields.Float('Costo Promedio', readonly=True)
    rentabilidad = fields.Float('Rentabilidad', readonly=True)
    margen_precio = fields.Float('Margen Precio', readonly=True)
    margen_costo = fields.Float('Margen Costo', readonly=True)
    subtotalmargen = fields.Float('Total Sin Iva', readonly=True)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):

        new_res = []

        res = super(inherit_report_pos_order, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)    


        for record in res:

            costo_promedio = record.get('costo_promedio')
            price_total = record.get('price_total')
            margen_precio = record.get('rentabilidad')
            margen_costo = record.get('margen_costo')

            if costo_promedio == None or margen_precio == None or margen_costo == None:
                new_res.append( record )
                continue

            product = record.get('product_qty', 1)
            venta = record.get('subtotalmargen', 1)
            costo = record.get('costo_total', 1)

            """if product <= 0:
                                                    record.update({
                                                        'costo_total' : 0,                    
                                                        'costo_promedio' : 0,
                                                        'margen_precio' : 0,
                                                        'margen_costo' : 0,
                                                        'rentabilidad' : 0,
                                                        'price_total' : 0
                                                    })
                                    
                                                    new_res.append( record )
                                                    continue"""

            margen_precio = 0
            if venta != 0:
                margen_precio =  (record.get('rentabilidad') / venta) * 100

            costo_promedio = 0
            if product != 0:
                costo_promedio = (record.get('costo_promedio') / product)

            margen_costo = 0
            if costo != 0:
                margen_costo = (record.get('rentabilidad') / costo) * 100   


            record.update({
                'costo_promedio' : costo_promedio,
                'margen_precio' : margen_precio,
                'margen_costo' : margen_costo
            })

            new_res.append( record )
        return new_res
    
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_pos_order')
        cr.execute("""
            create or replace view report_pos_order as (
                select
                    min(l.id) as id,
                    count(*) as nbr,
                    s.date_order as date,
                    sum(l.qty) as product_qty,
                    sum(l.qty * l.price_unit) as price_sub_total,
                    sum((l.qty * l.price_unit) * (100 - l.discount) / 100) as price_total,
                    sum((l.qty * l.price_unit) * (l.discount / 100)) as total_discount,
                    (sum(l.qty*l.price_unit)/sum(l.qty * u.factor))::decimal as average_price,
                    sum(cast(to_char(date_trunc('day',s.date_order) - date_trunc('day',s.create_date),'DD') as int)) as delay_validation,
                    s.partner_id as partner_id,
                    s.state as state,
                    s.user_id as user_id,
                    s.location_id as location_id,
                    s.company_id as company_id,
                    s.sale_journal as journal_id,
                    l.product_id as product_id,
                    pt.categ_id as product_categ_id,
                    p.product_tmpl_id,
                    ps.config_id,
                    pt.pos_categ_id,
                    pc.stock_location_id,
                    s.pricelist_id,
                    s.invoice_id IS NOT NULL AS invoiced,
                    s.picking_id,
                    
                    (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) as subtotalmargen,

                    (select case when l.qty > 0 then sum(sm.price_unit * sm.product_uom_qty) else sum(sm.price_unit * sm.product_uom_qty)* -1 end as costo_total  from stock_move sm 
                    where sm.picking_id = s.picking_id and sm.product_id = l.product_id limit 1),

                    (select case when l.qty > 0 then sum(sm.price_unit * sm.product_uom_qty) else sum(sm.price_unit * sm.product_uom_qty) * -1  end from stock_move sm 
                    where sm.picking_id = s.picking_id and sm.product_id = l.product_id limit 1) as costo_promedio,

                    (select case when l.qty >  0 then (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) - sum(sm.price_unit * sm.product_uom_qty)  else  
                    (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) - sum((sm.price_unit * sm.product_uom_qty)* -1) 
                    end  as rentabilidad  from stock_move sm 
                    where sm.picking_id = s.picking_id and sm.product_id = l.product_id limit 1),

                    (select case when l.qty > 0 then (case when (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) > 0 then ((select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) - sum(sm.price_unit * sm.product_uom_qty)) / (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) else 0 end)  else  
            
                    (case when (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id)* -1 > 0 then (((select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id)* -1) - sum(sm.price_unit * sm.product_uom_qty)) / (select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) else 0 end) 
                            end * 100 as margen_precio  from stock_move sm 
                    where sm.picking_id = s.picking_id and sm.product_id = l.product_id limit 1),

                    (select case when l.qty > 0 then (case when sum(sm.price_unit * sm.product_uom_qty) > 0 then ((select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) - sum(sm.price_unit * sm.product_uom_qty)) / sum(sm.price_unit * sm.product_uom_qty) else 0 end) else  
                    (case when sum(sm.price_unit * sm.product_uom_qty) > 0 then ((select  sum( case when atx.price_include then ((l.price_unit / (1 + (atx.amount/100))) * sum(l.qty)) * ((100 - l.discount) / 100) else (l.price_unit * l.qty) * ((100 - l.discount) / 100) end) 
                    from account_tax atx, product_taxes_rel ptr, product_template pt where atx.id = ptr.tax_id and pt.id = ptr.prod_id and pt.id = p.product_tmpl_id) - (sum(sm.price_unit * sm.product_uom_qty)* -1 )) / sum(sm.price_unit * sm.product_uom_qty) else 0 end)
                            end  * 100 as margen_costo  from stock_move sm 
                    where sm.picking_id = s.picking_id and sm.product_id = l.product_id limit 1)
            
                from pos_order_line as l
                    left join pos_order s on (s.id=l.order_id)
                    left join product_product p on (l.product_id=p.id)
                    left join product_template pt on (p.product_tmpl_id=pt.id)
                    left join product_uom u on (u.id=pt.uom_id)
                    left join pos_session ps on (s.session_id=ps.id)
                    left join pos_config pc on (ps.config_id=pc.id)
                
                group by
                    s.date_order, s.partner_id,s.state, pt.categ_id,
                    s.user_id,s.location_id,s.company_id,s.sale_journal,s.pricelist_id,s.invoice_id,l.product_id,s.create_date,pt.categ_id,pt.pos_categ_id,p.product_tmpl_id,ps.config_id,pc.stock_location_id,
                    s.picking_id, l.price_unit, l.qty, l.discount
                having
                    sum(l.qty * u.factor) != 0)""")





