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
            domain: function(self){ return [['name', 'in', self.config.sequence_id]]; },
            loaded : function(self, sequences) {
                self.dian_resolutions = sequences[0];
            }
        },
        {
            model: 'ir.sequence.dian_resolution',
            fields: ['resolution_number', 'date_from', 'number_from', 'number_to', 'number_next', 'active_resolution'],
            domain: function(self){
                return [['id','in', self.dian_resolutions.dian_resolution_ids],['active_resolution', '=', true]];
            },
            loaded: function(self, resolutions) {
                if(resolutions[0]) {
                    self.dian_resolution_sequence = resolutions[0];
                } else {
                    self.dian_resolution_sequence = {
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
            var dian_resolution_sequence = this.pos.dian_resolution_sequence

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
                order.number_next_dian = this.pos.dian_resolutions.prefix + this.pos.dian_resolution_sequence.number_next++;
            }
            this._super(force_validation);
        },
    });

});



