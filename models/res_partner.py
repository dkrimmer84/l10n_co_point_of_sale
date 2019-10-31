from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def create_from_ui(self):
        if('doctype' in partner):
            doctype = int(partner['doctype'])
            del partner['doctype']
            partner['doctype'] = doctype

        if('personType' in partner):
            personType = int(partner['personType'])
            del partner['personType']
            partner['personType'] = personType

        return super(res_partner, self).create_from_ui()

