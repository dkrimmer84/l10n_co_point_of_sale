{
    'name': 'Colombia - Punto de venta (Terceros)',
    'category': 'Localization',
    'version': '0.9',
    'author': 'Luis Alfredo da Silva, Plastinorte S.A.S',
    'license': 'AGPL-3',
    'maintainer': 'luis.adasilvaf@gmail.com',
    'website': 'https://www.plastinorte.com',
    'summary': 'Colombia Punto de Venta: Extending the Contact Module in the Point of Sales Module - Odoo 9.0',
    'images': ['images/main_screenshot.png'],
    'description': """
Colombia Punto de Venta:
======================

    * This Module extends the Partner / Contact form in the Point of Sales Module.
    * It includes all the fields from the Colombian Partner / Contact Module

    """,
    'depends': [
        'point_of_sale',
        'l10n_co_res_partner'
    ],
    'data': [
        'views/pos_view.xml',
        'views/point_of_sale_view.xml',
        'report/report_sessionsummary.xml',
        'security/ir.model.access.csv',
        'views/report_receipt.xml'
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
}
