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
import ssl 
import sys
from tools import config
from tools.translate import _
from datetime import datetime, timedelta 
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare

class sale_order(osv.osv):
    _name = 'sale.order'
    _description = "Sale Order line Ingram"
    _inherit = 'sale.order'
    
    def _prepare_order_line_procurement(self, cr, uid, order, line, move_id, date_planned, context=None):
        return {
            'name': line.name.split('\n')[0],
            'origin': order.name,
            'date_planned': date_planned,
            'product_id': line.product_id.id,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                    or line.product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id)\
                    or line.product_uom.id,
            'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
            'procure_method': line.product_id.procure_method,
            'move_id': move_id,
            'company_id': order.company_id.id,
            'stockingr':line.stockingr,
            'note': line.name,
        }
        
    def _create_pickings_and_procurements(self, cr, uid, order, order_lines, picking_id=False, context=None):
        """Create the required procurements to supply sale order lines, also connecting
        the procurements to appropriate stock moves in order to bring the goods to the
        sale order's requested location.

        If ``picking_id`` is provided, the stock moves will be added to it, otherwise
        a standard outgoing picking will be created to wrap the stock moves, as returned
        by :meth:`~._prepare_order_picking`.

        Modules that wish to customize the procurements or partition the stock moves over
        multiple stock pickings may override this method and call ``super()`` with
        different subsets of ``order_lines`` and/or preset ``picking_id`` values.

        :param browse_record order: sale order to which the order lines belong
        :param list(browse_record) order_lines: sale order line records to procure
        :param int picking_id: optional ID of a stock picking to which the created stock moves
                               will be added. A new picking will be created if ommitted.
        :return: True
        """
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        procurement_obj = self.pool.get('procurement.order')
        proc_ids = []

        for line in order_lines:
            if line.state == 'done':
                continue

            date_planned = self._get_date_planned(cr, uid, order, line, order.date_order, context=context)

            if line.product_id:
                if line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    if not picking_id:
                        picking_id = picking_obj.create(cr, uid, self._prepare_order_picking(cr, uid, order, context=context))
                    move_id = move_obj.create(cr, uid, self._prepare_order_line_move(cr, uid, order, line, picking_id, date_planned, context=context))
                else:
                    move_id = False

                proc_id = procurement_obj.create(cr, uid, self._prepare_order_line_procurement(cr, uid, order, line, move_id, date_planned, context=context))
                proc_ids.append(proc_id)
                line.write({'procurement_id': proc_id})
                self.ship_recreate(cr, uid, order, line, move_id, proc_id)

        wf_service = netsvc.LocalService("workflow")
        if picking_id:
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

        for proc_id in proc_ids:
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)

        val = {}
        if order.state == 'shipping_except':
            val['state'] = 'progress'
            val['shipped'] = False

            if (order.order_policy == 'manual'):
                for line in order.order_line:
                    if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                        val['state'] = 'manual'
                        break
        order.write(val)
        return True


    def action_ship_create(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            self._create_pickings_and_procurements(cr, uid, order, order.order_line, None, context=context)
        return True
   
    def button_check(self,cr,uid,ids,context=None):
        print 'buttoncheck'
        boolprice=False
        boolquant=False
        txt="" 
        ordreid=self.pool.get('sale.order.line').search(cr,uid,[('order_id','=',ids[0]),])
        for i in ordreid:
            donne=self.pool.get('sale.order.line').browse(cr,uid,i)
            idprod = donne.product_id
            if idprod:
                donnee=self.pool.get('product.template').browse(cr,uid,idprod.id)
                idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
                config=self.pool.get('ingram_config').read(cr,uid,idsearch,['categorie_id','supplier_id'])
                if config:
                    supplier = config[0]['supplier_id'][0]
                prod_tmpl_id=self.pool.get('product.product').browse(cr,uid,idprod.id).product_tmpl_id.id
                valeur2=self.pool.get('product.template').browse(cr,uid,prod_tmpl_id)
                if valeur2.ingram:
                    donnee=self.pool.get('product.product').browse(cr,uid,idprod.id)
                    if donnee.default_code:
                        prix,quantite,bool=self.pool.get('sale.order.line').actualisationPrix(cr,uid,ids,donnee.default_code,idprod.id)
                        prodtemp=self.pool.get('product.template').browse(cr,uid,prod_tmpl_id)
                        if (prodtemp.standard_price!=float(prix))|(donne.stockingr != quantite):
                            if (prodtemp.standard_price!=float(prix)):
                                suppinfo_id=self.pool.get('product.template').browse(cr,uid,prod_tmpl_id).seller_ids
                                for b in suppinfo_id:
                                    if b.name.id == supplier:
                                        for c in b.pricelist_ids:
                                            if c.name=='INGRAM' and c.min_quantity==1:
                                                self.pool.get('pricelist.partnerinfo').write(cr,uid,c.id,{'price':prix})
                                boolprice=True
                                if (donne.stockingr > quantite):
                                    boolquant=True
                                    self.pool.get('sale.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'1'})
                                    self.pool.get('product.template').write(cr,uid,prod_tmpl_id,{'standard_price':prix})
                                elif  (prodtemp.standard_price>float(prix)):
                                    self.pool.get('sale.order.line').write(cr,uid,[i],{'verif':'2'})
                                    self.pool.get('product.template').write(cr,uid,prod_tmpl_id,{'standard_price':prix})
                                else:
                                    self.pool.get('sale.order.line').write(cr,uid,[i],{'verif':'3'})
                                    self.pool.get('product.template').write(cr,uid,prod_tmpl_id,{'standard_price':prix})
                            else:
                                if (donne.stockingr > quantite):
                                    boolquant=True
                                    self.pool.get('sale.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'1'})
                                else:
                                    self.pool.get('sale.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'0'})
                        else:
                            self.pool.get('sale.order.line').write(cr,uid,[i],{'verif':'0'})
                    
        return True
sale_order()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _description = 'Sale Order line'
    _columns = {
      'stockingr': fields.char('Stock Ingram', size=10, select=True,help="Legend of the function price and avalability\nBlue = stock decreases\nRed = price of the supplier increases\nGreen =prix of the supplier decreases" ),
      'verif': fields.char('Check',size=25),
               
    }

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,uom=False, qty_uos=0, uos=False, name='', partner_id=False,lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        context = context or {}
        lang = lang or context.get('lang',False)
        partner_obj = self.pool.get('res.partner')
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty=qty,
            uom=uom, qty_uos=qty_uos, uos=uos, name=name, partner_id=partner_id,
            lang=lang, update_tax=update_tax, date_order=date_order, packaging=packaging, fiscal_position=fiscal_position, flag=flag, context=context)
        
        context = {'lang': lang, 'partner_id': partner_id}
        if partner_id:
            lang = partner_obj.browse(cr, uid, partner_id).lang
        valid=True
        quantite=''
        result['value']['stockingr']=quantite
        if product:
            donnee=self.pool.get('product.product').browse(cr,uid,product)
            if donnee.manufacturer:
                if donnee.description_sale:
                    result['value']['name'] = donnee.manufacturer +' - ' + donnee.description_sale
                elif donnee.name:
                    result['value']['name'] = donnee.manufacturer +' - ' + donnee.name
            elif donnee.description_sale:
                result['value']['name'] = donnee.description_sale
            elif donnee.name:
                result['value']['name'] = donnee.name
            result['value']['type']= donnee.procure_method
            idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
            config=self.pool.get('ingram_config').read(cr,uid,idsearch,['categorie_id','supplier_id'])
            if config:
                supplier = config[0]['supplier_id'][0] 
            if config:
                categorie = config[0]['categorie_id'][0]
                codecateg=self.pool.get('product.category').browse(cr,uid,donnee.categ_id.id)
                if(codecateg.code_categ_ingram):
                    donnee=self.pool.get('product.product').browse(cr,uid,product)
                    if donnee.default_code:
                        prix,quantite,valid=self.actualisationPrix(cr,uid,ids,donnee.default_code,product)
                        prod=self.pool.get('product.product').browse(cr,uid,product)
                        suppinfo_id=prod.product_tmpl_id.seller_ids
                        for b in suppinfo_id:
                            if b.name.id == supplier:
                                for c in b.pricelist_ids:
                                    if c.name=='INGRAM' and c.min_quantity==1:
                                        self.pool.get('pricelist.partnerinfo').write(cr,uid,c.id,{'price':prix})
                        self.pool.get('product.template').write(cr,uid,prod.product_tmpl_id.id,{'standard_price':prix})
                        result['value']['stockingr']=quantite
                    else:
                        result['value']['stockingr']="N/A"
                else:
                    result['value']['stockingr']="N/A"
        if quantite:
            result['value']['stockingr']=quantite
        else:
            result['value']['stockingr']="N/A"
        return result

    def actualisationPrix(self,cr,uid,ids,id_prod,product): 
        return self.checkPrice(cr,uid,ids,id_prod,product)
    
    def checkPrice(self,cr,uid,ids,codeSku,product):
        requete=self.requeteCode(cr,uid,codeSku)
        idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
        config=self.pool.get('ingram_config').read(cr,uid,idsearch,['xml_address'])#
        ip=str(config[0]['xml_address'])
        if ip :
            ip=ip.split('/')
            chm=""
            for i in range(len(ip)):
                if i>0:
                    chm+="/"+ip[i]
            conn = httplib.HTTPSConnection(ip[0],443)
            if sys.version >= '2.7':
                sock = socket.create_connection((conn.host, conn.port), conn.timeout, conn.source_address)
            else:
                sock = socket.create_connection((conn.host, conn.port), conn.timeout)
            conn.sock = ssl.wrap_socket(sock, conn.key_file, conn.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)
            conn.request("POST",chm,requete,) 
            response = conn.getresponse()
            data = response.read()  
            _logger.info(data) 
            conn.close()
            return  self.traitement(cr,uid,ids,data,product)# 
        else :
            return False
    
    def requeteCode(self,cr,uid,code):
            idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
            if idsearch:
                config=self.pool.get('ingram_config').browse(cr,uid,idsearch[0])#
                requete = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" 
                requete += "<BusinessTransactionRequest xmlns=\"http://www.ingrammicro.com/pcg/in/PriceAndAvailibilityRequest\">"
                requete += "<RequestPreamble>"
                requete += "<TransactionClassifier>1.0</TransactionClassifier> "
                requete += "<TransactionID>PnA</TransactionID> "
                requete += "<UserName>"+str(config.xml_login)+"</UserName>" 
                requete += "<UserPassword>"+str(config.xml_passwd)+"</UserPassword> "
                requete += "<CountryCode>"+str(config.country_id.code)+"</CountryCode> "
                requete += "</RequestPreamble>"
                requete += "<PriceAndAvailabilityRequest>"
                requete += "<PriceAndAvailabilityPreference>3</PriceAndAvailabilityPreference>" 
                requete += "<Item>"
                requete += "<IngramPartNumber>"+str(code)+"</IngramPartNumber>" 
                requete += "<RequestedQuantity UnitOfMeasure=\"EA\">3</RequestedQuantity>" 
                requete += "</Item>"
                requete += "</PriceAndAvailabilityRequest>"
                requete += "</BusinessTransactionRequest>"
                return requete
            else:
                raise osv.except_osv(_('ERROR: '),_('Xml request inactive!'))

    def traitement(self,cr,uid,ids,reponse,product):
        dom = xml.dom.minidom.parseString(reponse)            
        return self.handleSlideshow(cr,uid,ids,dom,product)

    def handleSlideshow(self,cr,uid,ids,ResponsePreamble,product):     
           if(self.verifConexion(cr,uid,ids,ResponsePreamble.getElementsByTagName("ResponsePreamble")[0])):
               return self.handleSlideshowItemDetails(cr,uid,ids,ResponsePreamble.getElementsByTagName("ItemDetails")[0],product)
           else: 
               return 0.0,0,False
           
    def getText(self,nodelist):
            rc = []
            for node in nodelist:
                if node.nodeType == node.TEXT_NODE:
                    rc.append(node.data)
            return ''.join(rc)

    def handleSlideshowTitle(self,title):
            return True

    def handleSlideshowItemDetails(self,cr,uid,ids,noeud,product):
            elements=noeud.getElementsByTagName("SKUAttributes")[0]
            if (noeud.getElementsByTagName("AvailabilityDetails")):
                infoprod=noeud.getElementsByTagName("AvailabilityDetails")[0]
                quantite=self.getText((infoprod.getElementsByTagName("AvailableQuantity")[0]).childNodes)
                infoid=infoprod.getElementsByTagName("PlantID")[0]
                descr=infoid.getAttribute("PlantDescription")
                id=self.getText((infoprod.getElementsByTagName("PlantID")[0]).childNodes)
                available=self.getText((elements.getElementsByTagName("IsAvailable")[0]).childNodes)
                unite=infoprod.getElementsByTagName("AvailableQuantity")[0]
                unite=unite.getAttribute("UnitOfMeasure")
            else:
                quantite="N/A"
            prix = noeud.getElementsByTagName("PricingDetails")[0]
            prix=self.getText((prix.getElementsByTagName("UnitNetPrice")[0]).childNodes)
            prix=prix.replace(',','.')
            return prix,quantite,True
        
    def verifConexion(self,cr,uid,ids,noeud):
        returncode=self.getText((noeud.getElementsByTagName("ReturnCode")[0]).childNodes)
        returnMessage=self.getText((noeud.getElementsByTagName("ReturnMessage")[0]).childNodes)
        if int(returncode)<20000:
            return True
        elif int(returncode)==20000:
            raise osv.except_osv(_('ERROR: '),_('No results were found for given search criteria'))
        elif int(returncode)==20001:
            raise osv.except_osv(_('ERROR: '),_('IngramSalesOrderType cannot have value ZRE or ZCR'))
        elif int(returncode)==20002:
            raise osv.except_osv(_('ERROR: '),_(' Authentication or Authorization has failed; please re-submit your document with correct login credentials.'))
        elif int(returncode)==20003:
            raise osv.except_osv(_('ERROR: '),_('Unable to process the document; please try to re-submit your document after sometime. If error persist contact technical support'))
        elif int(returncode)==20004:
            raise osv.except_osv(_('ERROR: '),_(' Transaction Failed : Data issue'))
        elif int(returncode)==20005:
            raise osv.except_osv(_('ERROR: '),_('Real-Time transactions are currently unavailable'))
sale_order_line()