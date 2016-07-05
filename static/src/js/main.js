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
                      'xidentification',
                      'formatedNit',
                      'xcity',
                      'state_id'];
models.push(
    {
        model:  'res.country.state',
        fields: ['name', 'country_id'],
        loaded: function(self, departments) {
            self.departments = departments;
            console.log(departments);
        }
    },
    {
        model:  'res.country.state.city',
        fields: ['name', 'state_id'],
        loaded: function(self, cities) {
            self.cities = cities;
            console.log(cities);
        }
    },
    {
        loaded: function(self) {
            $.when(new Model('res.partner').call('get_doctype').then(function(doctypes){
                self.doctypes = doctypes;
            }));
            $.when(new Model('res.partner').call('get_persontype').then(function(persontypes){
                self.persontypes = persontypes;
            }));
        }
    }
);

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

        if(name.val() === "" && is_company) {
            name.attr("placeholder", _t("Nombre de la compañía"));
        } else {
            name.attr("placeholder", _t("Nombre"));
        }

        if(is_company) {
            name.removeAttr("disabled");
            name.change(function(event) {
                $(".client-companyname").val($(event.target).val());
            });
            $('.partner-names').hide();
            $(".client-persontype").removeAttr("disabled").val('2');
            $(".client-first-name").val("");
            $(".client-second-name").val("");
            $(".client-first-lastname").val("");
            $(".client-second-lastname").val("");
        } else {
            name.attr("disabled", "disabled");
            name.unbind("change");
            $(".client-persontype").attr("disabled", "disabled").val('1');
            $(".client-companyname").val("");
            $('.partner-names').show();
        }

    },

    _concat_names: function($el) {
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

        $(names.join(", ")).keyup(function() {
              self._concat_names($(".client-details"));
        });
        this.$('.client-is-company').click(function(event){
            self.is_company_click_handler($(this));
        });

        $('.client-doctype').on('change', function(event) {
            self.doctype_event_handler(event);
        });

        $('.identification-number').css("visibility", "hidden")
                                   .attr("disabled", "disabled");

       $('.formated-nit').css("visibility", "hidden")
                         .attr("disabled", "disabled");

        $('.client-identification-number').on('change', function(event) {
            var xidentification = $(event.target).val();
            var doctype = $('.client-doctype').val();
            var nit_field = $('.client-formatednit');

            if(doctype == 31) {
                var have_min = self._check_ident(event);
                var have_letter = self._check_ident_num(event);

                if(!have_letter && have_min) {
                    var dv = self._check_dv(xidentification);
                    var formatedNit = self.formated_nit(xidentification);
                    nit_field.val(formatedNit + "-" + dv);
                } else {
                    nit_field.val("");
                }
            }
        });

        // Asignando a Colombia como país por defecto
        var country_select = $('.client-address-country');
        var state_select = $('.client-address-state');
        var city_select = $('.client-address-city');

        country_select.val("50")
        country_select.change(function(event) {
            $.each(opciones, function() {
                if($(this).attr("country_id") !== country_select.val())
                {
                    $(this).hide();
                }
            });
            if(country_select.val()) {
                state_select.removeAttr("disabled");

            } else {
                state_select.attr("disabled", "disabled");
                city_select.attr("disabled", "disabled");
                state_select.val("");
                city_select.val("");
            }

        }).trigger("change");

        state_select.change(function(event) {
            var opciones = state_select.find('option');

        });

        city_select.attr("disabled", "disabled");
        city_select.change(function(event) {

        });
    },

    formated_nit: function(nit) {
        nit = nit.toString();
        var pattern = /(-?\d+)(\d{3})/;
        while (pattern.test(nit))
          nit = nit.replace(pattern, "$1.$2");
        return nit;
    },

    _check_dv: function(nit) {
        while (nit.length < 15) nit = "0" + nit;
        var vl = nit.split("");
        var result = (
            parseInt(vl[0])*71 +
            parseInt(vl[1])*67 +
            parseInt(vl[2])*59 +
            parseInt(vl[3])*53 +
            parseInt(vl[4])*47 +
            parseInt(vl[5])*43 +
            parseInt(vl[6])*41 +
            parseInt(vl[7])*37 +
            parseInt(vl[8])*29 +
            parseInt(vl[9])*23 +
            parseInt(vl[10])*19 +
            parseInt(vl[11])*17 +
            parseInt(vl[12])*13 +
            parseInt(vl[13])*7 +
            parseInt(vl[14])*3
        ) % 11;

        if($.inArray(result, [0,1]) !== -1) {
            return result;
        } else {
            return (11 - result);
        }
    },

    _check_ident: function(event) {
        var xidentification = $(event.target).val();

        if(xidentification.length < 2 || xidentification.length > 12) {
            this.gui.show_popup('error', _t('La número de identificación debe ser no mayor a 12 dígitos ni menor a 2'));
            this.not_save = true;
            return false;
        }
        this.not_save = false;
        return true;
    },

    _check_ident_num: function(event) {
        var doctype = $(".client-doctype").val();
        var xidentification = $(event.target).val();

        if(doctype != 1) {
            if(xidentification != false && doctype != 21 && doctype != 41) {
                if(xidentification.search(/^[\d]+$/) != 0) {
                    this.gui.show_popup('error', _t('¡Error! El número de identificación sólo permite números'));
                    this.not_save = true;
                    return true;
                } else {
                    this.not_save = false;
                }
            }
        }
        return false;
    },

    doctype_event_handler: function(event) {
        var target = $(event.target);
        var id_field = $('.identification-number');
        var nit_field = $('.formated-nit');

        if(target.val() == 1 || target.val() == 43) {
            id_field.css("visibility", "hidden")
                    .attr("disabled", "disabled");
        } else {
            id_field.css("visibility", "visible")
                    .removeAttr("disabled", "disabled");
        }

        if(target.val() == 31) {
            nit_field.css("visibility", "visible")
                     .removeAttr("disabled", "disabled");
        } else {
            nit_field.css("visibility", "hidden")
                     .removeAttr("disabled", "disabled");
        }
        id_field.val("");
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
            $(".client-is-company").remove();
        }

        if(this.not_save) {
            this.gui.show_popup('error', _t('Error! Tiene errores pendientes que corregir antes de porder guardar el cliente'));
            return;
        }

        this._super(partner);
    },

});

});
