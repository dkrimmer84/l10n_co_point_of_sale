odoo.define('l10n_co_pos_sequence.main', function(require) {
    "use strict";

    var core = require('web.core');
    var screens = require('point_of_sale.screens');
    var models = require('point_of_sale.models');
    var devices = require('point_of_sale.devices');
    var chrome = require('point_of_sale.chrome');
    var gui = require('point_of_sale.gui');
    var popups = require('point_of_sale.popups');
    var Class = require('web.Class');
    var utils = require('web.utils');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var Model = require('web.DataModel');
    var _t = core._t;

    

    models.load_models([
        {
            model: 'ir.sequence',
            fields: ['prefix','remaining_numbers', 'remaining_days', 'dian_resolution_ids'],
            domain: function(self){ return ['|', ['name', 'in', self.config.sequence_id],
                                            ['name', 'in', self.config.sequence_refund_id]]; },
            loaded : function(self, sequences) {
                self.dian_resolution = sequences[0];
                self.dian_resolution_refund = sequences[1];

            }
        },
        {
            model: 'ir.sequence.dian_resolution',
            fields: ['resolution_number', 'date_from', 'date_to', 'number_from', 'number_to', 'number_next', 'active_resolution'],
            domain: function(self){

                var ids = [];
                self.resolutions_ids = ids;

                var dian_resolution_ids = self.dian_resolution.dian_resolution_ids;
                for( var resolution in dian_resolution_ids ) {
                    ids.push( dian_resolution_ids[ resolution ] );
                }



                return [['id','in', ids],['active_resolution', '=', true]];
            },
            loaded: function(self, resolutions) {

                if(resolutions.length >= 2) {
                    self.dian_resolution_sequence = resolutions[0];
                    self.dian_resolution_sequence_refund = resolutions[1];
                } else {
                    self.dian_resolution_sequence = resolutions[0];
                    /*self.dian_resolution_sequence = {
                        active_resolution: false
                    }*/
                    self.dian_resolution_sequence_refund = {
                        active_resolution: false
                    }
                }

                if( self.dian_resolution_sequence == undefined ){
                    self.dian_resolution_sequence = {
                        active_resolution: false
                    }
                }

                var check_active_dian = setInterval(function(){
                    var actual_date = new Date().getTime();

                    if( self.dian_resolution_sequence == undefined ){
                        clearInterval( check_active_dian );
                        return;
                    }


                    var date_to = new Date( self.dian_resolution_sequence.date_to ).getTime();

                    if( self.dian_resolution_sequence.number_next >= self.dian_resolution_sequence.number_from && 
                        self.dian_resolution_sequence.number_next <= self.dian_resolution_sequence.number_to   &&  
                        actual_date <= date_to && 
                        self.dian_resolution_sequence.active_resolution ){



                    } else {
                        try{
                            new Model('ir.sequence').call('check_active_resolution', [self.dian_resolution.id]).then(function(data){

                                if( data ){
                                    location.reload();
                                }

                            })
                        } catch( e ){

                        }
                        

                    }

                }, 3000)
            }
        },
    ])

    var __super__ = models.Order.prototype;
    var Order = models.Order.extend({
        initialize: function(attributes,options) {
            this.number_next_dian = false;
            __super__.initialize.apply(this,[attributes,options]);
        },
        export_as_JSON: function() {
            var _super = __super__.export_as_JSON.apply(this);
            _super.number_next_dian = this.number_next_dian;
            return _super;
        },
        export_for_printing: function() {
            var receipt = __super__.export_for_printing.apply(this);
            var company_partner = this.pos.company_partner[0];
            var dian_resolution_sequence;

            if(this.get_total_with_tax() < 0) {
                dian_resolution_sequence = this.pos.dian_resolution_sequence_refund;
            } else {
                dian_resolution_sequence = this.pos.dian_resolution_sequence;
            }

            if(company_partner.street) {
                var street = company_partner.street.split(",").map(function(text) { return text.trim() + '<br />'; });
                receipt.company.street = street.join("");
            } else {
                receipt.company.street = "compañía sin dirección";
            }

            if( dian_resolution_sequence != undefined ){
                if(dian_resolution_sequence.active_resolution != false) {
                    function zero_pad(num,size){
                        var s = ""+num;
                        while (s.length < size) {
                            s = "0" + s;
                        }
                        return s;
                    }
                    dian_resolution_sequence.number_from  = zero_pad(dian_resolution_sequence.number_from, 4)
                    dian_resolution_sequence.number_to  = zero_pad(dian_resolution_sequence.number_to, 4)
                    receipt.dian_resolution_sequence = dian_resolution_sequence;

                }
            }

            

            receipt.company.formatedNit = company_partner.formatedNit ? company_partner.formatedNit : "no posee";

            if (!this.number_next_dian) {
                receipt.number_next_dian = this.number_next_dian;
            }

            return receipt;
        },
        get_client_xidentification: function() {
            var client = this.get('client');
            return client ? client.xidentification : "";
        },
        get_client_formatedNit: function() {
            var client = this.get('client');
            return client ? client.formatedNit : "";
        },
        get_client_tel: function() {
            var client = this.get('client');
            return client ? client.phone : "";
        },
        get_client_address: function() {
            var client = this.get('client');
            return client ? client.street : "";
        }
    });
    models.Order = Order;

    var __payment_super__ = screens.PaymentScreenWidget;
    screens.PaymentScreenWidget.include({
        validate_order: function(force_validation) {

            var self = this;
            var order = this.pos.get_order();

            // FIXME: this check is there because the backend is unable to
            // process empty orders. This is not the right place to fix it.
            if (order.get_orderlines().length === 0) {
                this.gui.show_popup('error',{
                    'title': _t('Empty Order'),
                    'body':  _t('There must be at least one product in your order before it can be validated'),
                });
                return false;
            }

            var plines = order.get_paymentlines();
            
            for (var i = 0; i < plines.length; i++) {
                if (plines[i].get_type() === 'bank' && plines[i].get_amount() < 0) {

                    this.gui.show_popup('error',{
                        'title': _t('Negative Bank Payment'),
                        'body': _t('You cannot have a negative amount in a Bank payment. Use a cash payment method to return money to the customer.'),
                    });
                    return false;
                }
            }

            if (!order.is_paid() || this.invoicing) {
                return false;
            }

            // The exact amount must be paid if there is no cash payment method defined.
            if (Math.abs(order.get_total_with_tax() - order.get_total_paid()) > 0.00001) {
                var cash = false;
                for (var i = 0; i < this.pos.cashregisters.length; i++) {
                    cash = cash || (this.pos.cashregisters[i].journal.type === 'cash');
                }
                if (!cash) {
                    this.gui.show_popup('error',{
                        title: _t('Cannot return change without a cash payment method'),
                        body:  _t('There is no cash payment method available in this point of sale to handle the change.\n\n Please pay the exact amount or add a cash payment method in the point of sale configuration'),
                    });
                    return false;
                }
            }

            // if the change is too large, it's probably an input error, make the user confirm.
            if (!force_validation && order.get_total_with_tax() > 0 && (order.get_total_with_tax() * 1000 < order.get_total_paid())) {
                this.gui.show_popup('confirm',{
                    title: _t('Please Confirm Large Amount'),
                    body:  _t('Are you sure that the customer wants to  pay') + 
                           ' ' + 
                           this.format_currency(order.get_total_paid()) +
                           ' ' +
                           _t('for an order of') +
                           ' ' +
                           this.format_currency(order.get_total_with_tax()) +
                           ' ' +
                           _t('? Clicking "Confirm" will validate the payment.'),
                    confirm: function() {
                        self.validate_order('confirm');
                    },
                });
                return false;
            }

            var value = false;


            for( var pos in order.get_orderlines() ){
                var line = order.get_orderlines(  )[ pos ];

                if( value && value > 0 ){
                    if( line.get_price_with_tax() < 0 ){
                        self.show_popup_validation_value();
                        return false
                    }
                } else if( value && value < 0 ){
                    if( line.get_price_with_tax() > 0 ){
                        self.show_popup_validation_value();
                        return false;
                    }
                }
                value = line.get_price_with_tax();

            }

            for( var pos in order.get_orderlines() ){
                var line = order.get_orderlines(  )[ pos ];

                if( line.get_quantity() == 0 ){
                    this.gui.show_popup('error',{
                        title: _t("Sales with quantity '0'"),
                        body:  _t("Sales with quantity '0' are not allowed. Please re-check your order!!!"),
                    });
                    return false;
                }

            }


            //var is_valid = self.order_is_valid(force_validation);
            if(order.get_total_with_tax() >= 0 && this.pos.dian_resolution_sequence != undefined) {
                order.number_next_dian = this.pos.dian_resolution.prefix +
                this.pos.dian_resolution_sequence.number_next++;
            } else {
                order.number_next_dian = this.pos.dian_resolution_refund.prefix +
                this.pos.dian_resolution_sequence_refund.number_next++;
            }
            



            /*if(is_valid) {
                var order = this.pos.get_order();
                if(order.get_total_with_tax() >= 0) {
                    order.number_next_dian = this.pos.dian_resolution.prefix +
                        this.pos.dian_resolution_sequence.number_next++;
                } else {
                    order.number_next_dian = this.pos.dian_resolution_refund.prefix +
                        this.pos.dian_resolution_sequence_refund.number_next++;
                }

            }*/
            this._super(force_validation);
        },
        show_popup_validation_value : function(){
            this.gui.show_popup('error',{
                title: _t('Cannot create sales and refund in the same transaction'),
                body:  _t("Please seperate normal sales from refund transactions"),
            });
        }
    });

});



