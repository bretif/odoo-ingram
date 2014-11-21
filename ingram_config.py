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
from osv import fields, osv
import time
import ftplib
import os
import time
import mx.DateTime
import os.path
import os
import csv, math
import datetime
import thread
import netsvc
import tools
import smtplib
import sys
from tools.translate import _
import logging
from datetime import date,datetime, timedelta
from dateutil.relativedelta import relativedelta

class ingram_rel_tax(osv.osv):
    _name = "ingram_rel_tax"
    _description = "Tax relation with configuration"    
    _columns={
               'id_tax' : fields.integer("id taxe"),
               'id_conf' : fields.integer("id conf"),
    }

class ingram_rel_tax_purchase(osv.osv):
    _name = "ingram_rel_tax_purchase"
    _description = "Tax relation with configuration"
    _columns={
               'id_tax' : fields.integer("id taxe"),
               'id_conf' : fields.integer("id conf"),
    }

class ingram_config(osv.osv):
    _name = "ingram_config"
    _description = "Configuration Management Produces Ingram"    
    _columns={'name' : fields.char("Name",255,help="Name associated with the configuration", required=True),
              'xml_address' : fields.char('Server Xml address',255,help="server Xml address"),
              'xml_login' : fields.char('Login',255,help="Login for Xml request "),
              'xml_passwd' : fields.char('Password',255,help="Password for Xml Request"),
              'xml_active' : fields.boolean('XMl Request',help="Active the Xml Request"),
              'server_address' : fields.char('Server address',255,help="server ip address",required=True),
              'file_cat' : fields.char('Products Categories file name',255,help="Name of the file for the products categories",required=True),
              'file_prod' : fields.char('Products File name',255,help="Name of the file for the products. Must be based on this header: 'Ingram Part Number,Vendor Part Number,EANUPC Code,Plant,Vendor Number,Vendor Name,Weight,Category ID,Customer Price,Retail Price,Availability Flag,BOM Flag,Warranty Flag,Material Long Description,Material Creation Reason code,Material Language Code,Music Copyright Fees,Recycling Fees,Document Copyright Fees,Battery Fees,Availability (Local Stock),Availability (Central Stock),Creation Reason Type,Creation Reason Value,Local Stock Backlog Quantity,Local Stock Backlog ETA,Central Stock Backlog Quantity,Central Stock Backlog ETA'",required=True),
              'server_login' : fields.char('Login',255,help="Login database"),
              'server_passwd' : fields.char('Password',255,help="Password database"),
              'date_synchro' : fields.datetime('Date of last manually synchronization',readonly=True),
              'date_import' : fields.datetime('Date of last manually importation',readonly=True),
              'date_cron' : fields.datetime('Date of last cronjob synchronization',readonly=True),
              'chemin' : fields.char("Path",255,help="Path where the files is stored", required=True),
              'mailto' : fields.char("Warning Mail",255,help="Encode the adresses e-mail separated by ';'.\nThose e-mail will receive the warnings", required=True),
              'synchro_active' : fields.boolean('Synchro active'),
              'taxes_iden' : fields.integer('taxe id'),
              'id_synchro' : fields.many2one('ir.cron','Cronjob',  required=True,help="Cronjob in OpenERP for automatic synchronization. To bind the Cronjob with the configuration, click the button"),
              'categorie_name' : fields.char('Category',255,help="Name of the product categorie"),
              'location_id': fields.many2one('stock.location', 'Location', required=True, domain="[('usage', '=', 'internal')]",help=" Location of new product"),
              'country_id': fields.many2one('res.country', 'Country', required=True,help=" Country of Ingram supplier"),
              'categorie_id':fields.many2one('product.category','Category', required=True, change_default=True, domain="[('type','=','normal')]" ,help="Select category for the current product"),
              'supplier_id' : fields.many2one('res.partner', 'Supplier', required=True,domain = [('supplier','=',True)], ondelete='cascade', help="Supplier of this product"),
              'taxes_id': fields.many2many('account.tax', 'product_taxes_rel',
                                    'prod_id', 'tax_id', 'Customer Taxes',
                                    domain=[('parent_id','=',False),('type_tax_use','in',['sale','all'])]),
              'supplier_taxes_id': fields.many2many('account.tax',
                                    'product_supplier_taxes_rel', 'prod_id', 'tax_id',
                                    'Supplier Taxes', domain=[('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),
              'taxes_ventes': fields.many2many('account.tax',
                                    'ingram_rel_tax', 'id_tax', 'id_conf',
                                    'ingram_config',domain=[('parent_id', '=', False),('type_tax_use','in',['sale','all'])]),
              'taxes_achats': fields.many2many('account.tax',
                                    'ingram_rel_tax_purchase', 'id_tax', 'id_conf',
                                    'ingram_config',domain=[('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),
    }
    _defaults = {
        'file_cat':'PCAT_GENERIC.TXT',
        'file_prod':'Price2.txt',
    }
    
    def onchange_supplier_id(self, cr, uid, ids, supp, context=None):
        if supp:
            idss=self.pool.get('res.partner').browse(cr,uid,supp)
            return {'value': {'country_id':idss.country_id.id}}
        return {'value': {'country_id': False}}
    
    def check_ftp(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        ingrams = self.browse(cr, uid, ids)
        config = self.read(cr,uid,ids,['server_address','server_login','server_passwd','chemin'])
        ip = config[0]['server_address']
        login = config[0]['server_login']
        passwd = config[0]['server_passwd']
        chm=str(config[0]['chemin'])
        try:
            ftp=ftplib.FTP()
        except:
            raise osv.except_osv(_('Error!'), _("FTP was not started!"))
            return False
        ip=ip.split('/')
        txt=""
        for i in range(len(ip)):
           if i>0:
                txt+="/"+ip[i]
        try:
            ftp.connect(ip[0])
            if login:
                ftp.login(login,passwd)
            else:
                ftp.login()
        except:
            raise osv.except_osv(_('Error!'), _("Username/password FTP connection was not successfully!"))
            return False
        ftp.close()
        raise osv.except_osv(_('Ok!'), _("FTP connection was successfully!")) 
        return True
    
    def create(self, cr, uid, vals, context=None):
        ids=self.search(cr,uid,[])
        if len(ids)>0:
            raise osv.except_osv(_('Error !'), _('You can have only one configuration'))
        return super(ingram_config, self).create(cr, uid, vals, context)
    
    def sendTextMail(self,cr,uid,ids,title,mess):
        _from = 'Ingram Error <Ingram@bhc.be>'
        to=self.browse(cr,uid,ids[0]).mailto
        to=to.replace(';',',')
        txt=''
        if mess:
            txt += "\r\n"
            txt += mess
            txt += "\r\n"
        mail_obj=self.pool.get('mail.mail')
        res=mail_obj.create(cr,uid,{'subject':title,
                                'email_from':'ingram@openerp.com',
                                'email_to':to,
                                'body_html':txt})

    def write(self, cr, uid, ids, values, context=None):
        idtaxevente=self.pool.get('ingram_config').browse(cr,uid,1).taxes_ventes
        idtaxeAchat=self.pool.get('ingram_config').browse(cr,uid,1).taxes_achats
        result = super(ingram_config, self).write(cr, uid, ids, values, context=context)
        if ('taxes_ventes' in values ):
                tab=[]
                tab2=[]
                tab3=[]
                for i in idtaxevente:
                    tab.append(i.id)
                for j in values['taxes_ventes'][0][2]:
                    if not ( j in tab ):
                        tab2.append(j)
                for i in idtaxevente:
                    if not ( i.id in values['taxes_ventes'][0][2] ):
                        tab3.append(i.id)
                if tab2:
                    idProd=self.pool.get('product.template').search(cr,uid,[('ingram','=',True),])
                    for j in idProd:
                        empl = self.pool.get('product.product').search(cr,uid,[('product_tmpl_id','=',j),])
                        for k in values['taxes_ventes'][0][2]:
                            self.pool.get('product.product').write(cr,uid,empl,{'taxes_id': [(4,k)]})
                if tab3:
                    idProd=self.pool.get('product.template').search(cr,uid,[('ingram','=',True),])
                    for j in idProd:
                        empl = self.pool.get('product.product').search(cr,uid,[('product_tmpl_id','=',j),])
                        for i in tab3:
                            self.pool.get('product.product').write(cr,uid,empl,{'taxes_id': [(3,i)]})
        if ('taxes_achats' in values ):
                tab=[]
                tab2=[]
                tab3=[]
                for i in idtaxeAchat:
                    tab.append(i.id)
                for j in values['taxes_achats'][0][2]:
                    if not ( j in tab ):
                        tab2.append(j)
                for i in idtaxeAchat:
                    if not ( i.id in values['taxes_achats'][0][2] ):
                        tab3.append(i.id)
                if (tab2):
                    idProd=self.pool.get('product.template').search(cr,uid,[('ingram','=',True),])
                    for j in idProd:
                        empl = self.pool.get('product.product').search(cr,uid,[('product_tmpl_id','=',j),])
                        for i in values['taxes_achats'][0][2]:
                            self.pool.get('product.product').write(cr,uid,empl,{'supplier_taxes_id': [(4,i)]})
                if tab3:
                    idProd=self.pool.get('product.template').search(cr,uid,[('ingram','=',True),])
                    for j in idProd:
                        empl = self.pool.get('product.product').search(cr,uid,[('product_tmpl_id','=',j),])
                        for i in tab3:
                            self.pool.get('product.product').write(cr,uid,empl,{'taxes_id': [(3,i)]})
        return result 
    
    def cron_function(self,cr,uid,context=None):
        id_config = self.search(cr,uid,[('xml_active','=',True),])
        if not id_config:
            _logger.info('No config!')
            return False 
        config = self.read(cr,uid,id_config,['server_address','server_login','server_passwd','chemin'])
        chm=str(config[0]['chemin'])
        val=self.browse(cr,uid,id_config)[0].synchro_active
        if not val :
            _logger.info('Download started')
            result=self.import_data(cr,uid,id_config,context)
            if result==True:
                _logger.info('Download ended')
            else:
                _logger.info('Download error')
                return False
            _logger.info('Synchronization started')
            result2=self.synchro_categ(cr,uid,id_config,context)
            if result2==True:
                _logger.info('products categories synchronization ended')
            else:
                _logger.info('products categories synchronization error')
                return False
            _logger.info('products synchronization started')
            result3=self.synchronisation(cr,uid,id_config,context)
            _logger.info(result3)
            if result3==True:
                _logger.info('products synchronization ended')
            else:
                _logger.info('products synchronization error')
                return False
            _logger.info('clean product started')
            result4=self.clean_data(cr,uid,id_config,context)
            if result4==True:
                _logger.info('clean product ended')
            else:
                _logger.info('clean product error')
                return False
            self.clean_categ(cr,uid,id_config,context)
        _logger.info('end synchronization')
        try :
            self.write(cr,uid,id_config,{'date_cron' : time.strftime("%Y-%m-%d %H:%M:%S")})
        except:
            try :
                self.write(cr,1,id_config,{'date_cron' : time.strftime("%Y-%m-%d %H:%M:%S")})
            except:pass
        _logger.info('Done')
        return True
    
    def button_import_data(self,cr,uid,ids,context=None):
        view = self.browse(cr,uid,ids)
        name_config = view[0].name        
        val=self.browse(cr,uid,ids)[0].synchro_active
        if not val :
            id_config = self.search(cr,uid,[('name','=',name_config),])
            _logger.info('Download started')
            result=self.import_data(cr,uid,id_config,context)
            if result==True:
                _logger.info('Download ended')
                try :
                    self.write(cr,uid,id_config,{'date_import' : time.strftime("%Y-%m-%d %H:%M:%S")})
                except:
                    try :
                        self.write(cr,1,id_config,{'date_import' : time.strftime("%Y-%m-%d %H:%M:%S")})
                    except:pass
            else:
                _logger.info('Download error')
                return False
        
        return True
    
    def import_data(self,cr,uid,id_config,context=None):
        config = self.read(cr,uid,id_config,['server_address','server_login','server_passwd','chemin'])
        ip = config[0]['server_address']
        login = config[0]['server_login']
        passwd = config[0]['server_passwd']
        chm=str(config[0]['chemin'])
        try:
            ftp=ftplib.FTP()
        except:
            _logger.error('connection error')
            self.sendTextMail(cr,uid,id_config,"Connecion error","An error occured during the connection to the server.\n\nDetails: \n\t %s" %(sys.exc_info()[0]))
            return False
        ip=ip.split('/')
        txt=""
        for i in range(len(ip)):
            if i>0:
                txt+="/"+ip[i]
        try:
            ftp.connect(ip[0])
            if login:
                ftp.login(login,passwd)
            else:
                ftp.login()
            ftp.retrlines('LIST')
            ftp.cwd(txt)
            ftp.retrlines('LIST')
            self.download(cr,uid,id_config,'.',chm,ftp)
            ftp.close()
                
            return True
        except:
           _logger.error('Download error')
           self.sendTextMail(cr,uid,id_config,"Import error","An error occured during the importation.\n\nDetails: \n\t %s" %(sys.exc_info()[0]))
           return False
#

    def clean_data(self,cr,uid,ids,context=None):
        _logger.info("Clean_data")
        try:
            aujourdhui = datetime.today()
            semaine=timedelta(weeks=1)
            date=aujourdhui - semaine
            idProd=self.pool.get('product.product').search(cr,uid,['|',('active','=',True),('active','=',False),('product_tmpl_id.ingram','=',True),('product_tmpl_id.last_synchro_ingram','<',date)],order='id')
            delete=0
            undelete=0
            use=0
            for i in idProd:
                ids1=self.pool.get('sale.order.line').search(cr,uid,[('product_id','=',i)])
                ids2=self.pool.get('purchase.order.line').search(cr,uid,[('product_id','=',i)])
                ids3=self.pool.get('procurement.order').search(cr,uid,[('product_id','=',i)])
                ids4=self.pool.get('stock.move').search(cr,uid,[('product_id','=',i)])
                ids5=self.pool.get('account.invoice.line').search(cr,uid,[('product_id','=',i)])
                if not ids1 and not ids2 and not ids3 and not ids4 and not ids5:
                    try:
                        self.pool.get('product.product').unlink(cr,uid,[i])
                        delete+=1
                    except:
                        _logger.info('Delete impossible')
                        undelete+=1
                else:
                    self.pool.get('product.product').write(cr,uid,i,{'active':False})
                    use+=1
            _logger.info('Products deleted : %s'%(delete))
            _logger.info('Products non deleted : %s'%(use))
            _logger.info('product cleaned')
            return True
        except:
            _logger.error("Erreur Clean_data")
            self.sendTextMail(cr,uid,ids,"Error products cleaning","An error occured during the cleaning.\n\nDetails: \n\t %s" %(sys.exc_info()[0]))
            return False
    
    def delete_data(self,cr,uid,ids,context=None):
            idProd=self.pool.get('product.product').search(cr,uid,['|',('active','=',True),('active','=',False),('product_tmpl_id.ingram','=',True)],order='id')
            delete=0
            undelete=0
            use=0
            for i in idProd:
                ids1=self.pool.get('sale.order.line').search(cr,uid,[('product_id','=',i)])
                ids2=self.pool.get('purchase.order.line').search(cr,uid,[('product_id','=',i)])
                ids3=self.pool.get('procurement.order').search(cr,uid,[('product_id','=',i)])
                ids4=self.pool.get('stock.move').search(cr,uid,[('product_id','=',i)])
                ids5=self.pool.get('account.invoice.line').search(cr,uid,[('product_id','=',i)])
                if not ids1 and not ids2 and not ids3 and not ids4 and not ids5:
                    try:
                        self.pool.get('product.product').unlink(cr,uid,[i])
                        delete+=1
                    except:
                        _logger.error('Delete impossible')
                        undelete+=1
                else:
                    self.pool.get('product.product').write(cr,uid,i,{'active':False})
                    use+=1
            _logger.info('Products deleted : %s'%(delete))
            _logger.info('Products non deleted : %s'%(use))
            _logger.info('product cleaned')
            return True
   
    def clean_categ(self,cr,uid,ids,context=None):
        _logger.info("Clean_categ")
        product_categ=self.pool.get('product.category')
        tab=[]
        idss_cat=product_categ.search(cr,uid,[('code_categ_ingram','=','-1')])
        idss_cat.sort(reverse=True)
        for i in idss_cat:
            id_child=product_categ.search(cr,uid,[('parent_id','=',i)])
            for j in id_child :
                if j in idss_cat and j not in tab:
                    id_child2=product_categ.search(cr,uid,[('parent_id','=',j)])
                    for z in id_child2:
                        if z in idss_cat and z not in tab:
                            tab.append(z)
                    tab.append(j)
            tab.append(i)
        if 1==1:
            for j in tab:
                id_prod=self.pool.get('product.template').search(cr,uid,[('categ_id','=',j)])
                id_cat=product_categ.search(cr,uid,[('id','in',tab),('parent_id','=',j)])
                if not id_prod and not id_cat:
                    try:
                        product_categ.unlink(cr,uid,[j])
                    except:pass
        _logger.info("End Clean Categ")
        return True
   
    def synchro_data(self,cr,uid,ids,context=None):
        view = self.browse(cr,uid,ids)
        name_config = view[0].name        
        id_config = self.search(cr,uid,[('name','=',name_config),])
        config = self.read(cr,uid,id_config,['server_address','server_login','server_passwd','chemin'])
        val=self.browse(cr,uid,ids)[0].synchro_active
        product_categ=self.pool.get('product.category')
        if not val :
            _logger.info('Products categories synchronization started')
            result=self.synchro_categ(cr,uid,id_config,context)
            if result==True:
                _logger.info('products categories synchronization ended')
            else:
                _logger.info('products categories synchronization error')
                return False
            _logger.info('products synchronization started')
            result3=self.synchronisation(cr,uid,id_config,context)
            _logger.info(result3)
            if result3==True:
                _logger.info('products synchronization ended')
            else:
                _logger.info('products synchronization error')
                return False
            self.clean_categ(cr,uid,id_config,context)
        try :
            self.write(cr,uid,id_config,{'date_synchro' : time.strftime("%Y-%m-%d %H:%M:%S")})
        except:
            try :
                self.write(cr,1,id_config,{'date_synchro' : time.strftime("%Y-%m-%d %H:%M:%S")})
            except:pass
        return True

        
    def synchronisation(self,cr,uid,id_config,context=None):  
        config = self.read(cr,uid,id_config,['server_address','server_login','server_passwd','location_id','categorie_id','supplier_id','chemin','taxes_achats','taxes_ventes','file_prod'])
        location = config[0]['location_id']
        categ = config[0]['categorie_id']
        supplier= config[0]['supplier_id']
        chm=str(config[0]['chemin'])
        file_prod=config[0]['file_prod']
        listefich = os.listdir(chm+'/')
        date=datetime.now()
        product_product=self.pool.get('product.product')
        product_categ=self.pool.get('product.category')
        product_tmpl=self.pool.get('product.template')
        if config[0]['taxes_achats']:
            taxes_a=config[0]['taxes_achats']
        else:
            taxes_a=[]
        if config[0]['taxes_ventes']:
            taxes_v=config[0]['taxes_ventes']
        else:
            taxes_v=[]   
        try:
            compteur=0
            for i in listefich:
                if str(i)==str(file_prod):
                    fichier = open(chm+'/'+i,'rb')
                    fichiercsv = csv.reader(fichier, delimiter=',')
                    for ligne in fichiercsv:
                        if ligne[0] != "Ingram Part Number":
                            i=0
                            nom=ligne[13]
                            name=''
                            lgt=len(nom)
                            
                            while (i < lgt):
                                try:
                                    nom[i].decode('latin-1')
                                    name +=nom[i]
                                    i+=1
                                except:
                                    i+=1
                            nom=name[0:127]
                            desc=name
                            _logger.info(compteur)
                            empl = product_product.search(cr,uid,[('default_code','=',ligne[0]),])
                            if empl:
                                resultas =product_product.read(cr,uid,empl,['product_tmp'])
                                idprod = resultas[0]['product_tmpl_id']
                                categ_ingram=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[7])])
                                if not categ_ingram:
                                    categ_ingram=categ
                                if ligne[8]=='X' or not ligne[8]:
                                    ligne[8]='0.0'
                                product_tmpl.write(cr,uid,[idprod],{'name':nom,'standard_price':float(ligne[8]),'weight_net':float(ligne[6]),'description':desc,
                                                                    'categ_id':categ_ingram[0],'last_synchro_ingram':time.strftime("%Y-%m-%d %H:%M:%S")})
                                suppinfo_id=product_tmpl.browse(cr,uid,idprod).seller_ids
                                exist_line=False
                                for b in suppinfo_id:
                                    if b.name.id == supplier[0]:
                                        exist=b.id
                                        if not b.product_name or not b.product_code:
                                            self.pool.get('product.supplierinfo').write(cr,uid,b.id,{'product_name':nom,'product_code':ligne[0]})
                                        for c in b.pricelist_ids:
                                            exist_line=True
                                            if c.name=='INGRAM' and c.min_quantity==1:
                                                self.pool.get('pricelist.partnerinfo').write(cr,uid,c.id,{'price':float(ligne[8])})
                                if exist and exist_line==False:
                                    self.pool.get('pricelist.partnerinfo').create(cr,uid,{'min_quantity':'1','price':float(ligne[8]),'suppinfo_id':exist,'name':'INGRAM'})
                                if (len(ligne[2])==12):
                                    ligne[2]="0"+ligne[2]
                                if len(ligne[2]) == 13 :
                                    product_product.write(cr,uid,empl,{'name_template':nom,'active':'TRUE','ean13':ligne[2],'vpn':ligne[1],'manufacturer':ligne[5],'active':True})
                                else:
                                    product_product.write(cr,uid,empl,{'name_template':nom,'active':'TRUE','vpn':ligne[1],'manufacturer':ligne[5],'active':True})
                            else:
                                    categ_ingram=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[7])])
                                    if not categ_ingram:
                                        categ_ingram=categ
                                    if ligne[8]=='X' or not ligne[8]:
                                        ligne[8]='0.0'
                                    id=product_tmpl.create(cr,uid,{'name':nom,'standard_price':float(ligne[8]),'weight_net':float(ligne[6]),'description':desc,
                                        'categ_id':categ_ingram[0],'procure_method':'make_to_order','ingram':True,'type':'product','last_synchro_ingram':time.strftime("%Y-%m-%d %H:%M:%S")})
                                    if (len(ligne[2])==12):
                                        ligne[2]="0"+ligne[2]
                                    if len(ligne[2]) == 13 :
                                        id_prod=product_product.create(cr,uid,{'default_code':ligne[0],'name_template':nom,'taxes_id': [(6,0,taxes_v)],'supplier_taxes_id': [(6,0,taxes_a)],
                                                    'price_extra':0.00,'active':'TRUE','product_tmpl_id':id,'ean13':ligne[2],'vpn':ligne[1],'manufacturer':ligne[5]})
                                    else:
                                        id_prod=product_product.create(cr,uid,{'default_code':ligne[0],'name_template':nom,'taxes_id': [(6,0,taxes_v)],'supplier_taxes_id': [(6,0,taxes_a)],
                                                    'price_extra':0.00,'active':'TRUE','product_tmpl_id':id,'vpn':ligne[1],'manufacturer':ligne[5]})
                                        
                                    r=self.pool.get('product.supplierinfo').create(cr,uid,{'name':supplier[0],'min_qty':0,'product_id':id_prod,'product_name':nom,'product_code':ligne[0],})
                                    self.pool.get('pricelist.partnerinfo').create(cr,uid,{'min_quantity':'1','price':float(ligne[8]),'suppinfo_id':r,'name':'INGRAM'})
                        compteur+=1
                    fichier.close()
            return True       
        except:
            _logger.error("Erreur Synchro_produit")
            self.sendTextMail(cr,uid,id_config,"Error Synchronization","An error occured during the synchronization.\n \nDetails: \n\t %s" %(sys.exc_info()[0]))
            return False                
        
    def download(self,cr,uid,id_config,pathsrc, pathdst,ftp):
        idss=self.browse(cr,uid,id_config[0])
        try:
            lenpathsrc = len(pathsrc)
            l = ftp.nlst(pathsrc)
            for i in l:
                tailleinit=ftp.size(i)
                if ((str(i)==str(idss.file_cat)) or str(i)==str(idss.file_prod)):
                    try:
                        ftp.size(i)
                        ftp.retrbinary('RETR '+i, open(pathdst+os.sep+i, 'wb').write)                   
                    except:
                        try: os.makedirs(pathdst+os.sep+os.path.dirname(i[lenpathsrc:]))
                        except: pass
                        return False
                    if os.path.isfile(pathdst+'/'+i) :
                        taille=os.path.getsize(pathdst+'/'+i)
                        if (tailleinit!=taille):
                            os.remove(pathdst+'/'+i)
            return True
        except:
            return False    
   
    def product_qty(self, cr, uid, ids,qty,prod_id,location,context=None):
        date = time.strftime("%Y-%m-%d %H:%M:%S")
        listid = self.pool.get('stock.inventory').search(cr,uid,[('name','=','INV Ingram'+str(time.strftime("%Y-%m-%d")))])
        if (listid):
            id_Inv=listid[0]
        else:            
            id_Inv=self.pool.get('stock.inventory').create(cr,uid,{'state':'draft','name':'INV Ingram'+str(time.strftime("%Y-%m-%d")),'date_done':date,'write_date':date})
        self.pool.get('stock.inventory.line').create(cr,uid,{'compagny_id':1,'inventory_id':int(id_Inv),'product_qty':qty,'location_id':location,'product_id': int(prod_id),'product_uom' : 1})
        return True
    
    def synchro_categ(self,cr,uid,id_config,context=None):
        config = self.read(cr,uid,id_config,['server_address','server_login','server_passwd','location_id','categorie_id','supplier_id','chemin','file_cat'])
        categ = config[0]['categorie_id']
        categ = categ[0]
        file_cat=config[0]['file_cat']
        chm=str(config[0]['chemin'])
        listefich = os.listdir(chm+'/')
        product_categ=self.pool.get('product.category')
        compteur=0
        for i in listefich:
                if str(i)==str(file_cat) :
                    fichier = open(chm+'/'+i,'rb')
                    fichiercsv = csv.reader(fichier, delimiter=';')
                    cat=[]
                    for ligne in fichiercsv:
                        ligne_un=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[1]),('name','=',ligne[2])])
                        if ligne_un:
                            ligne_trois=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[3]),('name','=',ligne[4]),('parent_id','=',ligne_un[0])])
                        else:
                            ligne_trois=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[3]),('name','=',ligne[4])])
                        if ligne_trois:
                            ligne_cinq=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[5]),('name','=',ligne[6]),('parent_id','=',ligne_trois[0])])
                        else:
                            ligne_cinq=product_categ.search(cr,uid,[('code_categ_ingram','=',ligne[5]),('name','=',ligne[6])])
                        _logger.info(compteur)
                        if not ligne_un:
                            ligne_un=product_categ.create(cr,uid,{'name':ligne[2],'parent_id':categ,'code_categ_ingram':ligne[1],'type':'view'})
                            if ligne_un not in cat:
                                cat.append(ligne_un)
                        else:
                            ligne_un=ligne_un[0]
                            product_categ.write(cr,uid,ligne_un,{'code_categ_ingram':ligne[1]})
                            if ligne_un not in cat:
                                cat.append(ligne_un)
                        if not ligne_trois :
                            ligne_trois=product_categ.create(cr,uid,{'name':ligne[4],'parent_id':ligne_un,'code_categ_ingram':ligne[3],'type':'view'})
                            if ligne_trois not in cat:
                                cat.append(ligne_trois)
                        else:
                            if product_categ.browse(cr,uid,ligne_trois[0]).parent_id.id != ligne_un:
                                product_categ.write(cr,uid,ligne_trois[0],{'parent_id':ligne_un,'code_categ_ingram':ligne[3]})
                            else:
                                product_categ.write(cr,uid,ligne_trois[0],{'code_categ_ingram':ligne[3]})
                            ligne_trois=ligne_trois[0]
                            if ligne_trois not in cat:
                                cat.append(ligne_trois)
                        if not ligne_cinq :
                            ligne_cinq = product_categ.create(cr,uid,{'name':ligne[6],'parent_id':ligne_trois,'code_categ_ingram':ligne[5]})
                            if ligne_cinq not in cat:
                                cat.append(ligne_cinq)
                        else:
                            if product_categ.browse(cr,uid,ligne_cinq[0]).parent_id.id != ligne_trois:
                                product_categ.write(cr,uid,ligne_cinq[0],{'parent_id':ligne_trois,'code_categ_ingram':ligne[5]})
                            else:
                                product_categ.write(cr,uid,ligne_cinq[0],{'code_categ_ingram':ligne[5]})
                            if ligne_cinq not in cat:
                                cat.append(ligne_cinq[0])
                        compteur+=1
                    fichier.close()
                    idss=product_categ.search(cr,uid,[('code_categ_ingram','!=',False)])
                    tab=[]
                    for i in idss:
                        if i not in cat:
                            tab.append(i)
                            product_categ.write(cr,uid,i,{'code_categ_ingram':'-1'})
        return True
ingram_config()