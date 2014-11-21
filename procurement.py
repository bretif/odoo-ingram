# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import logging
_logger = logging.getLogger(__name__)
import urllib
import urllib2
from xml.dom.minidom import Node
from xml.dom.minidom import parse, parseString
import xml.dom.minidom
import socket
import httplib
from dateutil.relativedelta import relativedelta
import time
import netsvc
from osv import fields, osv
from tools import config
from tools.translate import _
from datetime import datetime, timedelta 
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare

class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'sendorder':fields.boolean('Sendorder'),
        'stockingr': fields.char('Stock Ingram', size=256, select=True,help="Stock Ingram from the SO." ),
        'message': fields.text('Latest error',  help="Exception occurred while computing procurement orders."),
    }
    
    def make_po(self, cr, uid, ids, context=None):
        """ Make purchase order from procurement
        @return: New created Purchase Orders procurement wise
        """
        print "make_po"
        purchase_id = False
        res = {}
        if context is None:
            context = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        partner_obj = self.pool.get('res.partner')
        uom_obj = self.pool.get('product.uom')
        pricelist_obj = self.pool.get('product.pricelist')
        prod_obj = self.pool.get('product.product')
        acc_pos_obj = self.pool.get('account.fiscal.position')
        seq_obj = self.pool.get('ir.sequence')
        warehouse_obj = self.pool.get('stock.warehouse')
        for procurement in self.browse(cr, uid, ids):
            res_id = procurement.move_id.id
            partner = procurement.product_id.seller_id # Taken Main Supplier of Product of Procurement.
            seller_qty = procurement.product_id.seller_qty
            partner_id = partner.id
            address_id = partner_obj.address_get(cr, uid, [partner_id], ['delivery'])['delivery']
            pricelist_id = partner.property_product_pricelist_purchase.id
            warehouse_id = warehouse_obj.search(cr, uid, [('company_id', '=', procurement.company_id.id or company.id)], context=context)
            uom_id = procurement.product_id.uom_po_id.id

            qty = uom_obj._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if seller_qty:
                qty = max(qty,seller_qty)

            price = pricelist_obj.price_get(cr, uid, [pricelist_id], procurement.product_id.id, qty, partner_id, {'uom': uom_id})[pricelist_id]

            schedule_date = self._get_purchase_schedule_date(cr, uid, procurement, company, context=context)
            purchase_date = self._get_purchase_order_date(cr, uid, procurement, company, schedule_date, context=context)

            new_context = context.copy()
            new_context.update({'lang': partner.lang, 'partner_id': partner_id})

            product = prod_obj.browse(cr, uid, procurement.product_id.id, context=new_context)
            taxes_ids = procurement.product_id.product_tmpl_id.supplier_taxes_id
            taxes = acc_pos_obj.map_tax(cr, uid, partner.property_account_position, taxes_ids)

            name = product.partner_ref
            if product.description_purchase:
                name += '\n'+ product.description_purchase
            line_vals = {
                'name': name,
                'product_qty': qty,
                'product_id': procurement.product_id.id,
                'product_uom': uom_id,
                'price_unit': price or 0.0,
                'date_planned': schedule_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'move_dest_id': res_id,
                'taxes_id': [(6,0,taxes)],
                'notes':product.description_purchase,
                'stockingr':procurement.stockingr,
            }

            po_exist = self.pool.get('purchase.order').search(cr, uid, [ ('partner_id', '=', partner_id), ('state', '=', 'draft'), ]) #, ('origin', '=',procurement.origin)
            if po_exist:
               if procurement.origin!="SCHEDULER":
                   self.pool.get('purchase.order').write(cr, uid, po_exist[0], {'order_line': [(0,0,line_vals)],}) 
                   origin=self.pool.get('purchase.order').read(cr,uid,po_exist[0],['origin'])
                   if not origin['origin']:
                      origin=procurement.origin
                      self.pool.get('purchase.order').write(cr, uid, po_exist[0], {'origin': origin,})  
                   else:
                       if not procurement.origin in origin['origin']:
                           origin=origin['origin']+":"+procurement.origin
                           self.pool.get('purchase.order').write(cr, uid, po_exist[0], {'origin': origin,}) 
               self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': po_exist[0]})
               res[procurement.id] = po_exist[0]
            else:
                name = seq_obj.get(cr, uid, 'purchase.order') or _('PO: %s') % procurement.name
                po_vals = {
                    'name': name,
                    'origin': procurement.origin,
                    'partner_id': partner_id,
                    'partner_address_id': address_id,
                    'location_id': procurement.location_id.id,
                    'warehouse_id':  warehouse_id and warehouse_id[0] or False,
                    'pricelist_id': pricelist_id,
                    'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'company_id': procurement.company_id.id,
                    'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                    'payment_term_id': partner.property_supplier_payment_term.id or False,
                }
                res[procurement.id] = self.create_procurement_purchase_order(cr, uid, procurement, po_vals, line_vals, context=new_context)
                self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': res[procurement.id]})
        self.message_post(cr, uid, ids, body=_("Draft Purchase Order created"), context=context)
        return res
    
procurement_order()