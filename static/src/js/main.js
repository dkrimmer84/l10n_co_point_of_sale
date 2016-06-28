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

    is_company_click_handler: function($el) {
        var is_company = $(".client-is-company");
        var name = $(".client-name");

        name.val("");
        if(is_company.is(":checked")) {
            name.removeAttr("disabled");
            $(".client-first-name").val("");
            $(".client-second-name").val("");
            $(".client-first-lastname").val("");
            $(".client-second-lastname").val("");
            $('.partner-names').hide();
        } else {
            name.attr("disabled", "disabled");
            $('.partner-names').show();
        }

    },

    _concat_names: function(event, $el) {
        var first_name = $el.find(".client-first-name").val();
        var second_name = $el.find(".client-second-name").val();
        var first_lastname = $el.find(".client-first-lastname").val();
        var second_lastname = $el.find(".client-second-lastname").val();

        $el.find(".client-name").val(first_name + " " + second_name + " " +
                              first_lastname+ " " + second_lastname);
    },

    setup_res_partner_logic: function() {
        this.is_company_click_handler($(this));
        var self = this;

        var names = [".client-first-name",
                     ".client-second-name",
                     ".client-first-lastname",
                     ".client-second-lastname"];

        $(names.join(", ")).keyup(function(event) {
              console.log("test");
              self._concat_names(event, $(".client-details"));
        });
        this.$('.client-is-company').click(function(event){
            self.is_company_click_handler($(this));
        });
    },

    display_client_details: function(visibility,partner,clickpos) {
        this._super(visibility,partner,clickpos);
        this.setup_res_partner_logic();
    },
});

});
