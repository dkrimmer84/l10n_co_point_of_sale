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
            fields: ['resolution_number', 'date_from', 'number_from', 'number_to', 'number_next', 'active_resolution'],
            domain: function(self){
                var ids = [self.dian_resolution.dian_resolution_ids[0],
                           self.dian_resolution_refund.dian_resolution_ids[0]];

                return [['id','in', ids],['active_resolution', '=', true]];
            },
            loaded: function(self, resolutions) {
                if(resolutions.length >= 2) {
                    self.dian_resolution_sequence = resolutions[0];
                    self.dian_resolution_sequence_refund = resolutions[1];
                } else {
                    self.dian_resolution_sequence = {
                        active_resolution: false
                    }
                    self.dian_resolution_sequence_refund = {
                        active_resolution: false
                    }
                }
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
        }
    });
    models.Order = Order;

    var __payment_super__ = screens.PaymentScreenWidget;
    screens.PaymentScreenWidget.include({
        validate_order: function(force_validation) {
            var self = this;

            var is_valid = self.order_is_valid(force_validation);

            if(is_valid) {
                var order = this.pos.get_order();
                if(order.get_total_with_tax() >= 0) {
                    order.number_next_dian = this.pos.dian_resolution.prefix +
                        this.pos.dian_resolution_sequence.number_next++;
                } else {
                    order.number_next_dian = this.pos.dian_resolution_refund.prefix +
                        this.pos.dian_resolution_sequence_refund.number_next++;
                }

            }
            this._super(force_validation);
        },
    });

});



