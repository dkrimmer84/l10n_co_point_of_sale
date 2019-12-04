{
    'name': 'Colombia - Punto de venta',
    'category': 'Localization',
    'version': '1.0',
    'author': 'Dominic Krimmer, Plastinorte S.A.S',
    'license': 'AGPL-3',
    'maintainer': 'dominic@plastinorte.com',
    'website': 'https://www.plastinorte.com',
    'summary': 'This module will extend the Point of Sale module by all required functionalities that the legal department of Colombia needs.',
    'images': ['images/main_screenshot.png'],
    'description': """
Colombia Point of Sale:
======================

    * This Module extends the Partner / Contact form in the Point of Sales Module.
    * It includes all the fields from the Colombian Partner / Contact Module
    * It considers all configured Taxes which were configured in l10n_co_tax_extension (depends on it)
    * Extended Pivot View: It's posible to see the exact margin of each sales made in the POS
    * Daily Report: You can print a daily report that divides your sales into the diferent payment methods. You will get an overall view of Taxes, Returns and Sales. This report is a legal requirement by the legal department of colombia (DIAN)
    * Re-Printing Report was modified to satisfy legal requirements.
    * Printing Receipt for POS Printer was modified as well
    * Full Support of colombian sequence number (Range, Number, Prefix, authorization date, validity). The interface will even give you a hint if your sequence will be invalid soon.
    * Please have in mind that you have to have a complete POS Configuration in order to run the module correctly

    """,
    'depends': [
        'point_of_sale',
        'l10n_co_res_partner',
        'l10n_co_tax_extension'
    ],
    'data': [
        'data/papel.xml',
        'views/pos_view.xml',
        'views/point_of_sale_view.xml',
        'report/report_sessionsummary.xml',
        'security/ir.model.access.csv',
        #'views/report_receipt.xml',
        'views/view_report_pos_order.xml'
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
}
