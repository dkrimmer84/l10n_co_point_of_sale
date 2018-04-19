odoo.define('l10n_co_point_of_sale.screens', function(require){
"use strict";

	// var PosBaseWidget = require('point_of_sale.BaseWidget');
	// var gui = require('point_of_sale.gui');
	// var models = require('point_of_sale.models');
	var core = require('web.core');
	// var Model = require('web.DataModel');
	// var utils = require('web.utils');
	// var formats = require('web.formats');

	var QWeb = core.qweb;
	// var _t = core._t;

	// var round_pr = utils.round_precision;

	var screens = require('point_of_sale.screens');

	// Metodo 2 (funciona )
	var CustomScreen = screens.ReceiptScreenWidget.include({
		print_web: function(){
	        console.log("soy el print_web de custom");
	        window.print();
    	    this.pos.get_order()._printed = true;
		},
		print_xml: function(){
	        console.log("soy el print_xml de custom");

	        var xhr = new XMLHttpRequest();
	        var site = window.location.origin+ "/web?rand" + Math.round(Math.random() * 10000);
	        xhr.open('HEAD', site, true);
	        xhr.onerror = function(){ return false; };
	        xhr.onload = function(){ return true; };
	        xhr.send();
	        var is_online = xhr.onload()

	        var env = {
	            widget:  this,
	            pos:     this.pos,
	            order:   this.pos.get_order(),
	            receipt: this.pos.get_order().export_for_printing(),
	            paymentlines: this.pos.get_order().get_paymentlines()
	        };
	        var receipt = QWeb.render('XmlReceipt',env);


	        if (is_online){
	        	this.pos.proxy.print_receipt(receipt);
		        this.pos.get_order()._printed = true;
	        }
	        else{        	
		        this.pos.proxy.print_receipt(receipt);
		        this.pos.proxy.print_receipt(receipt);
		        this.pos.get_order()._printed = true;
	        }
		},
	    print: function() {
	        var self = this;
	        console.log("Imprimir");

	        if (!this.pos.config.iface_print_via_proxy) { // browser (html) printing
	            this.lock_screen(true);

	            setTimeout(function(){
	                self.lock_screen(false);
	            }, 1000);

	            this.print_web();
	        } else {    // proxy (xml) printing
	            this.print_xml();
	            this.lock_screen(false);
	        }
	    }
	});

	// var ScreenWidget = PosBaseWidget;
	
	// var ReceiptScreenWidget = screens.extend({
	// 	print_web: function() {
	//         window.print();
	//         console.log("Soy el print web");
	//         this.pos.get_order()._printed = true;
	// 	},
	// 	print_xml: function() {
	//         var env = {
	//             widget:  this,
	//             pos:     this.pos,
	//             order:   this.pos.get_order(),
	//             receipt: this.pos.get_order().export_for_printing(),
	//             paymentlines: this.pos.get_order().get_paymentlines()
	//         };
	//         console.log("Soy el print xml" + env);
	//         var receipt = QWeb.render('XmlReceipt',env);

	//         this.pos.proxy.print_receipt(receipt);
	//         this.pos.get_order()._printed = true;			
	// 	}
	// });
	// gui.define_screen({name:'receipt', widget: ReceiptScreenWidget});

	// return {
	// 	ReceiptScreenWidget: CustomScreen
	// }
});