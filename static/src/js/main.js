 odoo.define('l10n_co_point_of_sale.main', function(require) {
"use strict";

var core = require('web.core');
var module = require('point_of_sale.models');
var Model = require('web.DataModel');
var gui = require('point_of_sale.gui');
var screens = require('point_of_sale.screens');
var _t = core._t;

var models = module.PosModel.prototype.models;
var partner_fields = ['x_name1',
                      'x_name2',
                      'x_lastname1',
                      'x_lastname2',
                      'is_company',
                      'personType',
                      'doctype',
                      'xidentification'];

var set_fields_to_model = function(fields, models) {
    for(var i = 0; i < models.length; i++) {
        if(models[i].model == 'res.partner') {
            var model = models[i];
            for(var j = 0; j < fields.length; j++){
                model.fields.push(fields[j]);
            }
        }
    }
}
set_fields_to_model(partner_fields, models);

// extending client screen behavior
screens.ClientListScreenWidget.include({

    is_company_click_handler: function(event, $el) {
        if($el.prop("checked") == true){
            $('.partner-names').hide();
        } else {
            $('.partner-names').show();
        }
    },

    display_client_details: function(visibility,partner,clickpos) {
        var self = this;
        this._super(visibility,partner,clickpos);
        this.$('.client-is-company').click(function(event){
            self.is_company_click_handler(event, $(this));
        });

    },
});

});
