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
import time
import netsvc
import sys
from osv import fields, osv
from tools import config
from tools.translate import _
from datetime import datetime, timedelta 
import ssl 

class history_command(osv.osv):
    _name = "history.command"
    _description = "History of the status of the commands"
    _columns = {
        'name': fields.char('Name', size=64),
        'date': fields.date("Expected Date",help="Expected Date"),
        'datemaj': fields.date("Updated date",help="Updated date"),
        'idmani': fields.many2one("stock.picking","idLabel"),
        'description':fields.char('Description',size=256),
        }

    def miseAjour(self,cr,uid,ids,date,description,statut,skuliste):
        for id in ids:
            cpt=0
            for i in date:
                date2=i.split("-")
                date[cpt]=date2[0]+"/"+date2[1]+"/"+date2[2]
                cpt+=1
            dateMax=["00","00","00"]
            for i in date:
                k=i.split("/")
                if (k[0]> dateMax[0]):
                    for j in range(len(dateMax)) :
                        dateMax[j]=k[j]
                elif ( int(k[0]) == int(dateMax[0])and  int(k[1])>int(dateMax[1])):
                        for j in range(len(dateMax)) :
                            dateMax[j]=k[j]
                elif(int(k[0]) == int(dateMax[0])and  int(k[1])==int(dateMax[1]) and int(k[2])>int(dateMax[2])):
                        for j in range(len(dateMax)) :
                            dateMax[j]=k[j]
            dateExp=dateMax[0]+"/"+dateMax[1]+"/"+dateMax[2]
            datejour=time.strftime('%Y-%m-%d')
            idtrouver=self.search(cr,uid,[('idmani','=',id),('description','=',description)])
            idstock=self.pool.get('stock.move').search(cr,uid,[('picking_id','=',ids[0])])
            compt=0
            for i in idstock:
                brw=self.pool.get('stock.move').browse(cr,uid,i)
                for k in skuliste:
                    if (int(brw.product_id.default_code) == int(k)):
                        self.pool.get('stock.move').write(cr,uid,i,{'date_expected':date[compt],})
                        compt+=1       
            self.pool.get('stock.picking').write(cr,uid,id,{'date_ingr':dateExp})
            if not idtrouver:
                idt=self.create(cr,uid,{'idmani':id,'description':description,'date':dateExp,'datemaj':datejour})
                idtrouver=[idt]
            return idtrouver
        
history_command()

class stock_picking_in(osv.osv):
    _inherit = 'stock.picking.in'
    _columns = {
           'history_lineb': fields.one2many('history.command', 'idmani',"idLabel"),
    }

    def button_status(self,cr,uid,ids,context=None):
        date=time.strftime("%Y-%m-%d %H:%M:%S")
        return self.statusCommande(cr,uid,ids,context)
    
    def statusCommande(self,cr,uid,ids,context):        
        return self.checkCom(cr,uid,ids)
    
    def checkCom(self,cr,uid,ids):
        po=self.read(cr,uid,ids,['origin'])
        if po[0]['origin']:
            numpo=po[0]['origin'].split(':')
            requete=self.requeteCode(cr,uid,numpo[0])
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
                    conn = httplib.HTTPSConnection(ip[0],443)
                    if sys.version >= '2.7':
                        sock = socket.create_connection((conn.host, conn.port), conn.timeout, conn.source_address)
                    else:
                        sock = socket.create_connection((conn.host, conn.port), conn.timeout)
                    conn.sock = ssl.wrap_socket(sock, conn.key_file, conn.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)
                    conn.request("POST",chm,requete ) 
            except:
                raise osv.except_osv(_('Warning!'),_('Connection failed'))
            response = conn.getresponse()
            data = response.read()
            _logger.info(data) 
            conn.close()
            return  self.traitement(cr,uid,ids,data)
        else:
            
            raise osv.except_osv(_('Warning!'),_('Incomming isn\'t link to a order'))
    
    def requeteCode(self,cr,uid,numIngram):
            idsearch=self.pool.get('ingram_config').search(cr,uid,[('xml_active','=','True'),])
            if idsearch:
                config=self.pool.get('ingram_config').browse(cr,uid,idsearch[0])#
                requete = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" 
                requete += "<BusinessTransactionRequest xmlns=\"http://www.ingrammicro.com/pcg/in/OrderInquiryRequest\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.ingrammicro.com/pcg/in/OrderInquiryRequest ../../13th%20Nov/EGT%20Transactions%20Design/IMXML%20Transactions/Done/Finalized/Inbound%20Order%20Inquiry%20-%20ODE%20-%20OST%20-%20OTR%20-%20OSE%20Merged/IMXML%205.0%20Schema/Request/OrderInquiryRequestSchema.xsd\">"
                requete += "<RequestPreamble>"
                requete += "<TransactionClassifier>1.0</TransactionClassifier> "
                requete += "<TransactionID>Status</TransactionID> "
                requete += "<TimeStamp>2010-04-07T18:39:09</TimeStamp> "
                requete += "<UserName>"+str(config.xml_login)+"</UserName>" 
                requete += "<UserPassword>"+str(config.xml_passwd)+"</UserPassword> "
                requete += "<CountryCode>"+str(config.country_id.code)+"</CountryCode> "
                requete += "</RequestPreamble>"
                requete +=" <OrderStatusRequest IncludeOrderDetails=\"Y\">"
                requete +="<CustomerPurchaseOrderNumber>"+str(numIngram)+"</CustomerPurchaseOrderNumber>"
                requete +="</OrderStatusRequest>"
                """
                requete +="<OrderSearchRequest>"
                requete +="<IngramSalesOrderDateRange FromDate = \"2011-03-25\" ToDate = \""+time.strftime('%Y-%m-%d')+"\"/>"
                requete +="</OrderSearchRequest>"
                """
                requete +="</BusinessTransactionRequest>"  
                
                return requete
            else:
                raise osv.except_osv(_('ERROR: '),_('Xml request inactive!'))

    def traitement(self,cr,uid,ids,reponse):
            dom = xml.dom.minidom.parseString(reponse)            
            return self.handleSlideshow(cr,uid,ids,dom)

    def handleSlideshow(self,cr,uid,ids,ResponsePreamble):     
        if(self.verifConexion(cr,uid,ids,ResponsePreamble.getElementsByTagName("ResponsePreamble")[0])):
               return self.handleSlideshowItemDetails(cr,uid,ids,ResponsePreamble.getElementsByTagName("OrderStatusResponse")[0])
        else:
            return False

    def getText(self,nodelist):
            rc = []
            for node in nodelist:
                if node.nodeType == node.TEXT_NODE:
                    rc.append(node.data)
            return ''.join(rc)

    def handleSlideshowItemDetails(self,cr,uid,ids,noeud):
            elements=noeud.getElementsByTagName("StatusDetails")[0]
            date =[]
            skuliste=[]
            for i in elements.getElementsByTagName("DeliveryDate"):
                date.append(self.getText(i.childNodes))
            for j in elements.getElementsByTagName("LineDetails"):
                sku=False
                for i in elements.getElementsByTagName("IngramPartNumber"):
                    if sku==False:
                        skuliste.append(self.getText(i.childNodes))
                        sku=True          
            statut=[]
            for i in elements.getElementsByTagName("LineStatus"):
                statut.append(i.getAttribute("StatusCode"))
            status=elements.getElementsByTagName("OrderStatus")[0]
            statusstr=status.getAttribute("StatusDescription")
            id=self.pool.get('history.command').miseAjour(cr,uid,ids,date,statusstr,statut,skuliste)
            print id
            self.write(cr,uid,ids[0],{'history_lineb':[(4,id[0])]})
            return True
            
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
    
stock_picking_in()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def get_min_max_date(self, cr, uid, ids, field_name, arg, context=None):
        """ Finds minimum and maximum dates for picking.
        @return: Dictionary of values
        """
        res = {}
        for id in ids:
            res[id] = {'min_date': False, 'max_date': False}
        if not ids:
            return res
        cr.execute("""select
                picking_id,
                min(date_expected),
                max(date_expected)
            from
                stock_move
            where
                picking_id IN %s
            group by
                picking_id""",(tuple(ids),))
        for pick, dt1, dt2 in cr.fetchall():
            if len(ids) == 1:
                val=self.pool.get('history.command').search(cr,uid,[('idmani','=',ids[0]),])#             
                if len(val):
                    if len(val)>0:
                        indice=len(val)-1
                    else:
                        indice=0
                    result=self.pool.get('history.command').read(cr,uid,[val[indice]],['date'])#
                    if (result):
                        res[pick]['min_date'] = result[0]['date'] #time.strftime('%Y-%m-%d %H:%M:%S')#
                    else:
                        res[pick]['min_date'] = dt1
                else:
                    res[pick]['min_date'] = dt1
            
            else:
                res[pick]['min_date'] = dt1
            res[pick]['max_date'] = dt2
        return res

    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
        """ Calculates planned date if it is less than 'value'.
        @param name: Name of field
        @param value: Value of field
        @param arg: User defined argument
        @return: True or False
        """
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.browse(cr, uid, ids, context=context):
            dateExp=time.strftime('%Y-%m-%d %H:%M:%S')
            sql_str = """update stock_move set
                    date='%s'
                where
                    picking_id=%s """ % (value, pick.id)
            if pick.min_date:
                sql_str += " and (date='" + pick.min_date + "' or date<'" + value + "')" 
            cr.execute(sql_str)
        return True


    _columns = {
           'date_ingr': fields.date("Delivry date",help="Delivry date"),
           'history_lineb' : fields.one2many('history.command','idmani',"idLabel"),
           'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                 method=True,store=True, type='datetime', string='Expected Date', select=1, help="Expected date for the picking to be processed"),
    }
stock_picking()