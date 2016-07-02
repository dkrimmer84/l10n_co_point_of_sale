odoo.define('l10n_co_point_of_sale.main', function(require) {
"use strict";

var core = require('web.core');
var module = require('point_of_sale.models');
var Model = require('web.Model');
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
        var is_company = $(".client-is-company").is(":checked");
        var name = $(".client-name");

        name.val("");
        if(is_company) {
            name.removeAttr("disabled");
            $(".client-first-name").val("");
            $(".client-second-name").val("");
            $(".client-first-lastname").val("");
            $(".client-second-lastname").val("");
            $('.partner-names').hide();
            name.attr("placeholder", _t("Nombre de la compañía"));
            $(".client-persontype").removeAttr("disabled").val('2');
        } else {
            name.attr("disabled", "disabled");
            name.attr("placeholder", _t("Nombre"));
            $(".client-persontype").attr("disabled", "disabled").val('1');
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
              self._concat_names(event, $(".client-details"));
        });
        this.$('.client-is-company').click(function(event){
            self.is_company_click_handler($(this));
        });

        new Model('res.partner').call('get_persontype').then(function(values){
            $.each(values, function(key, value) {
                $('.client-persontype').append($('<option>', {
                    value: key,
                    text : value
                }));
            });
        });

        new Model('res.partner').call('get_doctype').then(function(values){
            $.each(values, function(key, value) {
                $('.client-doctype').append($('<option>', {
                    value: key,
                    text : value
                }));
            });
        });

        $('.client-doctype').on('change', function(event) {
            self.doctype_event_handler(event);
        });

        $('.identification-number').css("visibility", "hidden")
                                   .attr("disabled", "disabled");

        $('.client-identification-number').on('change', function(event) {
            var xidentification = $(event.target).val();
            var doctype = $('.client-doctype').val();

            if(doctype == 31) {
                self._check_ident(event);
                self._check_ident_num(event);

                var dv = self._check_dv(xidentification);
                console.log(dv);
            }
        });
    },

    _check_dv: function(nit) {
        if($('.client-doctype').val() != 31) {
            return nit.toString();
        }

        while (nit.length < 15) nit = "0" + nit;
        var vl = nit.split("");
        var result = (
            vl[0]*71 +
            vl[1]*67 +
            vl[2]*59 +
            vl[3]*53 +
            vl[4]*47 +
            vl[5]*43 +
            vl[6]*41 +
            vl[7]*37 +
            vl[8]*29 +
            vl[9]*23 +
            vl[10]*19 +
            vl[11]*17 +
            vl[12]*13 +
            vl[13]*7 +
            vl[14]*3
        ) % 11;

        if($.inArray(result, [0,1])) {
            return result.toString();
        } else {
            result = 11 - result;
            return result.toString();
        }

    },

    _check_ident: function(event) {
        var xidentification = $(event.target).val();

        if(xidentification.length < 2 || xidentification.length > 12) {
            this.gui.show_popup('error', _t('La número de identificación debe ser no mayor a 12 dígitos ni menor a 2'));
            this.not_save = true;
        } else {
            this.not_save = false;
        }
    },

    _check_ident_num: function(event) {
        var doctype = $(".client-doctype").val();
        var xidentification = $(event.target).val();

        if(doctype != 1) {
            if(xidentification != false && doctype != 21 && doctype != 41) {
                if(xidentification.search(/^[\d]+$/) != 0) {
                    this.gui.show_popup('error', _t('¡Error! El número de identificación sólo permite números'));
                    this.not_save = true;
                } else {
                    this.not_save = false;
                }
            }
        }
    },

    formated_nit: function(event) {

    },

    doctype_event_handler: function(event) {
        var target = $(event.target);

        if(target.val() == 1 || target.val() == 43) {
            $('.identification-number').css("visibility", "hidden")
                                       .attr("disabled", "disabled")
                                       .val("");

        } else {
            $('.identification-number').css("visibility", "visible")
                                       .removeAttr("disabled", "disabled")
                                       .val("");
        }

        if(target.val() == 31) {
            var xidentification = $(".client-identification-number").val();
            var formatedNit = this.formated_nit(xidentification);
        }

    },

    display_client_details: function(visibility,partner,clickpos) {
        this._super(visibility,partner,clickpos);
        this.setup_res_partner_logic();
    },

    save_client_details: function(partner) {
        var self = this;
        var first_name = $(".client-first-name").val();
        var first_lastname = $(".client-first-lastname").val();
        var is_company = $(".client-is-company").is(":checked");

        if(!is_company) {
            if(!first_name && !first_lastname) {
                this.gui.show_popup('error',_t('El primer nombre y el primer apellido son requeridos'));
                return;
            }
        }

        if(this.not_save) {
            this.gui.show_popup('error', _t('Error! Tiene errores pendientes que corregir antes de porder guardar el cliente'));
            return;
        }

        this._super(partner);
    },

});

});
