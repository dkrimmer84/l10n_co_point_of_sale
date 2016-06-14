{
    'name': 'Colombia - Punto de venta',
    'category': 'Localization',
    'version': '0.1',
    'author': 'Luis Alfredo da Silva, Plastinorte S.A.S',
    'license': 'AGPL-3',
    'maintainer': 'luis.adasilvaf@gmail.com',
    'website': 'https://www.plastinorte.com',
    'summary': 'Colombia Terceros: Extending Partner / Contact Point of Sale Module - Odoo 9.0',
    'images': ['images/main_screenshot.png'],
    'description': """
Colombia Punto de Venta:
======================

    * Include into point_of_sale the fields from partner/contact from module l10n_co_res_partner 

    """,
    'depends': [
        'point_of_sale',
        'l10n_co_res_partner'
    ],
    'data': [
        'views/pos.xml',
    ],
    'installable': True,
}
