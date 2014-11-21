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
import logging
import sys
_logger = logging.getLogger(__name__)
import time
import netsvc
from osv import fields, osv
import ssl 
from tools import config
from tools.translate import _
from datetime import datetime, timedelta 

class purchase_order(osv.osv):
    _inherit = 'purchase.order'
    _columns = {
                'ingramsalesordernumber': fields.char("Order number",255,help="Order number at Ingram"),
                'ingramsalesorderdate': fields.char("Date order",255,help="Date order at Ingram"),
                'sendorder': fields.boolean('order sended',255),
                'sendmanuel': fields.boolean('Send manually',255),
                'generate_po': fields.char("Order Generated",255,help="Purchase order generated from the Ingram Module if the PO have other product than the Ingram product.", readonly=True),
    }
       
    def check_po(self, cr, uid, ids):
        idsearch=self.pool.get('ingram_config').search(cr,uid,[])
        if idsearch:
            config=self.pool.get('ingram_config').read(cr,uid,idsearch,['supplier_id'])
            id=config[0]['supplier_id']
        for i in ids:
            if self.browse(cr,uid,i).partner_id.id == id[0]:
                if self.pool.get('ingram_config').browse(cr,uid,idsearch[0]).xml_active==1:
                    check=self.button_check(cr,uid,ids)
                    if check != True:
                        generate_po= self.browse(cr,uid,ids[0]).generate_po or ''
                        new_po=self.browse(cr,uid,check).name
                        if generate_po:
                            generate_po += '/' + new_po
                        else:
                            generate_po += new_po
                        self.write(cr,uid,ids[0],{'generate_po': generate_po })
                        return False
                else:
                    raise osv.except_osv(_('ERROR: '),_('Xml request inactive!'))
        return True
    
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        print 'confirm'
        todo = []
        wf_service = netsvc.LocalService("workflow")
        
        for po in self.browse(cr, uid, ids, context=context):
            if not po.order_line:
                raise osv.except_osv(_('Error !'),_('You can not confirm purchase order without Purchase Order Lines.'))
            for line in po.order_line:
                if line.state=='draft':
                    todo.append(line.id)
            message = _("Purchase order '%s' is confirmed.") % (po.name,)
            self.log(cr, uid, po.id, message)
        self.pool.get('purchase.order.line').action_confirm(cr, uid, todo, context)
        if self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),]):
            idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
            config=self.pool.get('ingram_config').read(cr,uid,idsearch,['supplier_id'])
            id=config[0]['supplier_id']
            if po.partner_id.id == id[0] :
                result= self.send_order(cr,uid,ids,context)
                for i in ids:
                    if result['warning']['message']=="Successful Order":
                        self.write(cr, uid, [i], {'state' : 'confirmed', 'validator' : uid})
                    elif result['warning']['message']=="Miss order":
                        self.write(cr, uid, [i], {'state' : 'draft', 'validator' : False, 'sendorder': False,})
                    else:
                        self.write(cr, uid, [i], {'state' : 'draft', 'validator' : False, 'sendorder': False,})
                        raise osv.except_osv(_('Error'),_(result))
            else:
                for id in ids:
                    self.write(cr, uid, [id], {'state' : 'confirmed', 'validator' : uid})
        return True
   
    def button_check(self,cr,uid,ids,context=None):
        booll=False
        check=False
        created=False
        txt="" 
        idss=[]
        ordreid=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0]),])
        for i in ordreid:
            if check==False:
                check=True
                for j in ordreid:
                    donne=self.pool.get('purchase.order.line').browse(cr,uid,j)
                    idprod = donne.product_id
                    if not idprod:
                        idss.append(donne.id)    
                        booll=True
                    else:
                        donnee=self.pool.get('product.product').browse(cr,uid,idprod.id)
                        valeur=self.pool.get('product.template').browse(cr,uid,donnee.product_tmpl_id.id)
                        if not valeur.ingram:
                            idss.append(donne.id)
                            booll=True
                        else:
                            continue
            if booll== False:
                donne=self.pool.get('purchase.order.line').browse(cr,uid,i)
                donnee=self.pool.get('product.product').browse(cr,uid,donne.product_id.id)
                valeur=self.pool.get('product.template').browse(cr,uid,donnee.product_tmpl_id.id)
                quantite,bool=self.pool.get('purchase.order.line').actualisationPrix(cr,uid,ids,donnee.default_code,donne.product_id.id)
                self.pool.get('purchase.order.line').write(cr,uid,[i],{'stockingr':quantite,}) 
            else:
                if len(idss)==len(ordreid):
                    raise osv.except_osv(_("Error"),_("All the purchases lines are invalid for the supplier"))
                po_id=self.browse(cr,uid,ids[0])              
                if created==False:  
                    id_create=self.pool.get('purchase.order').copy(cr,uid,ids[0],{'order_line': False, 'generate_po': ''} )
                    created=True
                for i in idss:
                    self.pool.get('purchase.order.line').copy(cr,uid,i,{'order_id':id_create})
                self.pool.get('purchase.order.line').unlink(cr,uid,idss)
                return id_create                 
        return True
        
    def send_order(self,cr,uid,ids,context=None):
        warning="blop"
        valeur=self.pool.get('purchase.order').read(cr,uid,[ids[0]],['sendorder'])
        if str(valeur[0]['sendorder'])== "True" :
             raise osv.except_osv(_('Information!'),_('Already send order'))
        create_id = self.envoieCommande(cr,uid,ids,context)
        if not create_id:
            warn_msg="Successful Order"
            warning = {
                    'title': 'Information',
                    'message':
                        "Successful Order"
                    }
            self.pool.get('purchase.order').write(cr,uid,ids,{'sendorder':True,})
            name=self.browse(cr,uid,create_id).name
            message = _("The Purchase order '%s' is created.") % (name)
            self.log(cr, uid, create_id, message)
        else:
            warn_msg="miss Order"
            warning = {
                    'title': 'Information',
                    'message':
                        "miss order"
                    }
            
        return {'warning': warning}
        
    def envoieCommande(self,cr,uid,ids,context):
        idPo=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0]),])
        requete=self.requeteCode(cr,uid,idPo,ids[0])
        try:
            idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
            config=self.pool.get('ingram_config').read(cr,uid,idsearch,['xml_address'])#
            ip=str(config[0]['xml_address'])
            if ip :
                ip=ip.split('/')
                chm=""
                for i in range(len(ip)):
                    if i>0:
                        chm+="/"+ip[i]
                conn = httplib.HTTPSConnection(ip[0],443)#environment prod
                if sys.version >= '2.7':
                    sock = socket.create_connection((conn.host, conn.port), conn.timeout, conn.source_address)
                else:
                    sock = socket.create_connection((conn.host, conn.port), conn.timeout)
                conn.sock = ssl.wrap_socket(sock, conn.key_file, conn.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)
                conn.request("POST",chm,requete ) 
        except:
            raise osv.except_osv(_('Warning!'),_('Connection failed'))
        response = conn.getresponse()
        if response.status == 200:
            data = response.read()
            _logger.info(data) 
            conn.close()

            return  self.traitement(cr,uid,ids,data)
        else:
            raise osv.except_osv(_('Information!'),_('Connection failed'))
        
        return  self.traitement(cr,uid,ids,data)

    def requeteCode(self,cr,uid,idprod,id):
        idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
        if idsearch:
                config=self.pool.get('ingram_config').browse(cr,uid,idsearch[0])#
                requete = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" 
                requete += "<BusinessTransactionRequest xmlns=\"http://www.ingrammicro.com/pcg/in/OrderCreateRequest\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
                requete += "<RequestPreamble>"
                requete += "<TransactionClassifier>1.0</TransactionClassifier> "
                result=self.pool.get('purchase.order').read(cr,uid,id,['name'])
                requete += "<TransactionID>Trans-"+result['name']+"</TransactionID> "
                requete += "<UserName>"+str(config.xml_login)+"</UserName> "
                requete += "<UserPassword>"+str(config.xml_passwd)+"</UserPassword> "
                requete += "<CountryCode>"+str(config.country_id.code)+"</CountryCode> "
                requete += "<TransactionMode>SYNC</TransactionMode> "
                requete += "</RequestPreamble>"
                requete += "<OrderCreateRequest>"
                requete += "<CustomerPurchaseOrderDetails>"
                requete += "<PurchaseOrderNumber>"+result['name']+"</PurchaseOrderNumber> "
                requete += "<PurchaseOrderDate>"+time.strftime('%Y-%m-%d')+"</PurchaseOrderDate> "
                requete += "</CustomerPurchaseOrderDetails>"
                requete += "<IngramSalesOrderType>ZOR</IngramSalesOrderType> "
                id_dest=self.browse(cr,uid,id).dest_address_id
                if id_dest:
                    dest=self.pool.get('res.partner.address').browse(cr,uid,id_dest.id)
                    requete += "<ShipToDetails>"
                    requete += "<Address>"
                    if dest.partner_id:
                        requete += "<Name1>"+dest.partner_id.name+"</Name1> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address must have a Pertner Name!'))
                    if dest.name:
                        requete += "<Name4>"+dest.name+"</Name4> "
                    if dest.street:
                        requete += "<Address1>"+(dest.street).decode('latin-1')+"</Address1> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address must have a Street!'))
                    if dest.street2:
                        requete += "<Address2>"+dest.street2+"</Address2> "
                    if dest.city:
                        requete += "<City>"+dest.city+"</City> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address must have a City!'))
                    if dest.zip:
                        requete += "<PostalCode>"+dest.zip+"</PostalCode> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address must have a zip!'))
                    if dest.country_id:
                        requete += "<CountryCode>"+dest.country_id.code+"</CountryCode> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address must have a Country!'))
                    if dest.email:
                        requete += "<Email>"+dest.email+"</Email> "
                    requete += "</Address>"
                    requete += "</ShipToDetails>"
                else:
                    id_dest=self.browse(cr,uid,id).warehouse_id.partner_id
                    if not id_dest:
                        raise osv.except_osv(_('Warning!'),_('You must have a delivery address in the warehouse!'))
                    dest=self.pool.get('res.partner').browse(cr,uid,id_dest.id)
                    requete += "<ShipToDetails>"
                    requete += "<Address>"
                    if dest.name:
                        requete += "<Name1>"+dest.name+"</Name1> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address in the warehouse must have a Pertner Name!'))
                    if dest.name:
                        requete += "<Name4>"+dest.name+"</Name4> "
                    if dest.street:
                        requete += "<Address1>"+dest.street+"</Address1> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address in the warehouse must have a Street!'))
                    if dest.street2:
                        requete += "<Address2>"+dest.street2+"</Address2> "
                    if dest.city:
                        requete += "<City>"+dest.city+"</City> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address in the warehouse must have a City!'))
                    if dest.zip:
                        requete += "<PostalCode>"+dest.zip+"</PostalCode> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address in the warehouse must have a zip!'))
                    if dest.country_id:
                        requete += "<CountryCode>"+dest.country_id.code+"</CountryCode> "
                    else:
                        raise osv.except_osv(_('Warning!'),_('the delivery address in the warehouse must have a Country!'))
                    if dest.email:
                        requete += "<Email>"+dest.email+"</Email> "
                    requete += "</Address>"
                    requete += "</ShipToDetails>"
                requete += "<ShippingDetails>"
                requete += "<RequestedDeliveryDate>"+time.strftime('%Y-%m-%d')+"</RequestedDeliveryDate> "
                requete += "</ShippingDetails>"
                requete += "<ProcessingFlags>"
                requete += "<BackOrderFlag>Y</BackOrderFlag> "
                requete += "<SplitShipmentFlag>Y</SplitShipmentFlag> "
                requete += "<ShipCompleteFlag>N</ShipCompleteFlag> "
                requete += "<HoldOrderFlag>N</HoldOrderFlag> "
                requete += "</ProcessingFlags>"
                compt=0
                for id in idprod:
                    compt+=1
                    requete += "<LineDetails>"
                    requete += "<CustomerLineNumber>"+str(compt)+"</CustomerLineNumber> "
                    prod=self.pool.get('purchase.order.line').read(cr,uid,id,['product_id'])
                    prod=prod['product_id'][0]
                    sku=self.pool.get('product.product').read(cr,uid,[prod],['default_code'])
                    sku=sku[0]['default_code']
                    requete += "<IngramPartNumber>"+str(sku)+"</IngramPartNumber> "
                    qty=self.pool.get('purchase.order.line').read(cr,uid,id,['product_qty'])
                    requete += "<RequestedQuantity UnitOfMeasure=\"EA\">"+str(int(qty['product_qty']))+"</RequestedQuantity> "
                    requete += "</LineDetails>"
                requete += "</OrderCreateRequest>"
                requete += "</BusinessTransactionRequest>"
                return requete
        else:
            raise osv.except_osv(_('ERROR: '),_('Xml request inactive!'))
            
    def traitement(self,cr,uid,ids,reponse):
            dom = xml.dom.minidom.parseString(reponse)            
            return self.handleSlideshow(cr,uid,ids,dom)
        
    def handleSlideshow(self,cr,uid,ids,ResponsePreamble):
           if(self.verifConexion(cr,uid,ids,ResponsePreamble.getElementsByTagName("ResponsePreamble")[0])):
               return self.handleSlideshowItemDetails(cr,uid,ids,ResponsePreamble.getElementsByTagName("OrderCreateResponse")[0])
           else: 
               return False
           
    def getText(self,nodelist):
            rc = []
            for node in nodelist:
                if node.nodeType == node.TEXT_NODE:
                    rc.append(node.data)
            return ''.join(rc)

    def handleSlideshowTitle(self,title):
            return True

    def handleSlideshowItemDetails(self,cr,uid,ids,noeud):
            dateCom=self.getText((noeud.getElementsByTagName("IngramSalesOrderDate")[0]).childNodes)
            numCom=self.getText((noeud.getElementsByTagName("PurchaseOrderNumber")[0]).childNodes)
            cpt=-1
            cpt2=0 
            linetext=False
            status=[]
            statut=[]
            id_create=''
            total=""
            for i in noeud.getElementsByTagName("OrderStatus"):
                status.append(i.getAttribute("StatusCode"))
                status.append(i.getAttribute("StatusDescription"))
                if status[0]=="OC":
                    continue
                if status[0]=="OR" or status[0]=="PR":
                    elements=noeud.getElementsByTagName("LineDetails")
                    for j in elements:
                        cpt+=1
                        for i in j.getElementsByTagName("LineText"):
                            linetext=True
                            for z in j.getElementsByTagName("LineStatus"):                            
                                statut=[]
                                statut.append(z.getAttribute("StatusCode"))
                                statut.append(z.getAttribute("StatusDescription"))
                                idss=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0])])
                                prod=self.pool.get('purchase.order.line').browse(cr,uid,idss[cpt]).product_id.name
                                total+=" "  + prod + " : " + statut[1] + ' \n'
                        if linetext==False:
                            for z in j.getElementsByTagName("LineStatus"):                            
                                statut=[]
                                statut.append(z.getAttribute("StatusCode"))
                                statut.append(z.getAttribute("StatusDescription"))
                                idss=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0])])
                                prod=self.pool.get('purchase.order.line').browse(cr,uid,idss[cpt]).product_id.name
                                total+=" "  + prod + " : " + statut[1] + ' \n'
                    raise osv.except_osv(_("Order Rejected"),_(status[1] + total  ))
                else:
                    created=False
                    tab=[]    
                    for i in noeud.getElementsByTagName("LineStatus"):
                        for j in noeud.getElementsByTagName("LineStatus"):
                            statut.append(j.getAttribute("StatusCode"))
                            if statut[0]=="LR":
                                cpt2+=1
                                continue
                        cpt+=1
                        statut.append(i.getAttribute("StatusCode"))
                        statut.append(i.getAttribute("StatusDescription"))
                        if statut[0]=="LR":
                            po_id=self.browse(cr,uid,ids[0])
                            idss=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0])])
                            if len(idss)==cpt2:
                                raise osv.except_osv(_("Error"),_("All the purchases lines are rejected by the supplier"))
                            prod=self.pool.get('purchase.order.line').browse(cr,uid,idss[cpt])
                            statut.append(i.getAttribute("StatusDescription")) 
                            if created==False:  
                                id_create=self.pool.get('purchase.order').copy(cr,uid,ids[0],{'order_line': False,'generate_po': ''} )
                                created=True
                            self.pool.get('purchase.order.line').copy(cr,uid,prod.id,{'order_id':id_create})
                            tab.append(prod.id)
                    self.pool.get('purchase.order.line').unlink(cr,uid,tab)
                
            self.pool.get('purchase.order').write(cr,uid,ids,{'ingramsalesorderdate':dateCom})
            return (id_create)   
    
    def button_check_AV(self,cr,uid,ids,context=None):
        boolprice=False
        boolquant=False
        txt="" 
        ordreid=self.pool.get('purchase.order.line').search(cr,uid,[('order_id','=',ids[0]),])
        for i in ordreid:
            donne=self.pool.get('purchase.order.line').browse(cr,uid,i)
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
                        print prix,quantite,bool
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
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'1'})
                                else:
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'stockingr':quantite})
                                if  (prodtemp.standard_price>float(prix)):
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'verif':'2'})
                                    self.pool.get('product.template').write(cr,uid,prod_tmpl_id,{'standard_price':prix})
                                else:
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'verif':'3'})
                                    self.pool.get('product.template').write(cr,uid,prod_tmpl_id,{'standard_price':prix})
                            else:
                                if (donne.stockingr > quantite):
                                    boolquant=True
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'1'})
                                else:
                                    self.pool.get('purchase.order.line').write(cr,uid,[i],{'stockingr':quantite,'verif':'0'})
                        else:
                            self.pool.get('purchase.order.line').write(cr,uid,[i],{'verif':'0'})
                                        
        return True
    
    def verifConexion(self,cr,uid,ids,noeud):
        returncode=self.getText((noeud.getElementsByTagName("ReturnCode")[0]).childNodes)
        returnMessage=self.getText((noeud.getElementsByTagName("ReturnMessage")[0]).childNodes)
        if int(returncode)<20000:
            return True
        elif int(returncode)==20000:
            raise osv.except_osv(_('ERROR: '),_('Transaction Failed - Preamble Level Failure'))
        elif int(returncode)==20004:
            raise osv.except_osv(_('ERROR: '),_(' Transaction Failed : Data issue'))
        elif int(returncode)==20005:
            raise osv.except_osv(_('ERROR: '),_(returnMessage))
        else:
            raise osv.except_osv(_('ERROR: '),_(returnMessage))

purchase_order()


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'
    _columns = {
        'stockingr': fields.char('Stock Ingram', size=256, select=True,help="Legend of the function price and avalability\nBlue = stock decreases\nRed = price of the supplier increases\nGreen =prix of the supplier decreases" ),
        'verif': fields.char('Check',size=25),    
    }
    
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
            conn.request("POST",chm,requete ) 
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
               return 0,False
           
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

            return quantite,True
        
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
    
purchase_order_line()