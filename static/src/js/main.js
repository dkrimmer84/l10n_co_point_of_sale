 odoo.define('l10n_co_point_of_sale', function(require) {
    "use strict";

    var module = require('point_of_sale.models');
    var models = module.PosModel.prototype.models;

    for(var i = 0; i < models.length; i++) {
        if(models[i].model == 'res.partner') {
            models[i].fields.push('x_name1');
            models[i].fields.push('x_name2');
            models[i].fields.push('x_lastname1');
            models[i].fields.push('x_lastname2');
            models[i].fields.push('is_company');
        }
    }

    console.log("se registró el módulo");
 });
