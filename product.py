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
import urllib
import urllib2
from xml.dom.minidom import Node
from xml.dom.minidom import parse, parseString
import xml.dom.minidom
import socket
import httplib
import time
import netsvc
from osv import fields, osv
from tools import config
from tools.translate import _
from datetime import datetime, timedelta 

class product_category(osv.osv):
    _name = 'product.category'
    _description = 'Product Category'
    _inherit = 'product.category'
    _columns = {
        'code_categ_ingram' : fields.char('Ingram code category',255),
    }
product_category()

class product_product(osv.osv):
    _name = "product.product"
    _description = "Product"
    _inherit = 'product.product'
    _columns = {
        'vpn': fields.char("VPN",255,help="VPN code"),
        'manufacturer' : fields.char("Manufacturer",255,help="Manufacturer"),
    }

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=80):
        if not args:
            args=[]
        if not context:
            context={}
        if name:
            ids = self.search(cr, user, [('default_code','like',name)]+ args, limit=limit, context=context)
            if not len(ids):
                ids = self.search(cr, user, [('ean13','=',name)]+ args, limit=limit, context=context)
                ids = self.search(cr, user, [('vpn','like',name)]+ args, limit=limit, context=context)
            if not len(ids):
                ids = self.search(cr, user, [('default_code',operator,name)]+ args, limit=limit, context=context)
                ids += self.search(cr, user, [('name',operator,name)]+ args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context)
        return result        
product_product()

class product_template(osv.osv):
    _name = "product.template"
    _description = "Product"
    _inherit = 'product.template'
    _columns = {
                'ingram': fields.boolean('Ingram Product'),
                'last_synchro_ingram': fields.date("Synchro Date",help="Synchro date"),
}
product_template()