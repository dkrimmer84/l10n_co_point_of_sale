 odoo.define('l10n_co_point_of_sale', function(require) {
    "use strict";

    var module = require('point_of_sale.models');
    var models = module.PosModel.prototype.models;

    var partner_fields = ['x_name1',
                          'x_name2',
                          'x_lastname1',
                          'x_lastname2',
                          'is_company',
                          'personType',
                          'doctype',
                          'xidentification'];

    for(var i = 0; i < models.length; i++) {
        if(models[i].model == 'res.partner') {
            var model = models[i];
            for(var j = 0; j < partner_fields.length; j++){
                model.fields.push(partner_fields[j]);
            }
        }
    }

    console.log("se registró el módulo");
 });
