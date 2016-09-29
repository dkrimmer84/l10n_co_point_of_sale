from openerp.osv import osv


class res_partner(osv.osv):
    _inherit = 'res.partner'

    def create_from_ui(self, cr, uid, partner, context=None):
        if('doctype' in partner):
            doctype = int(partner['doctype'])
            del partner['doctype']
            partner['doctype'] = doctype

        if('personType' in partner):
            personType = int(partner['personType'])
            del partner['personType']
            partner['personType'] = personType

        return super(res_partner, self).create_from_ui(cr, uid, partner,
                                                       context)
