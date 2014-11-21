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
{
    "name": "Ingram XML integration",
    "version": "2.1.1",
    "depends": ["base","sale","product","stock","purchase","procurement"],
    "author": "BHC",
    "category": "Generic Modules/Others",
    "description": """
    This module provides an XML integration between OpenERP and Ingram Micro Servers. 
    It allows to maintain the Ingram product catalog and price list up to date automatically. 
    It also provides a real-time integration for quotation, sales, purchases and deliveries. 
    Actions in OpenERP generate requests toward Ingram to get informations, or to place an order directly, 
    without using any external tool or website. 
    
    2.0: Add the name of file to import for products categories and products in the configuration. Supplier informations are now synchronized in the o2m fields to add other supplier on a product. 
    2.1 : Improve products categories synchronization
    """,
    'images': ['images/Sale_Order.png','images/Ingram_Category.png','images/Purchase_Order.png','images/Delivery.png',],
    'website': 'http://www.bhc.be/en/application/ingram-micro',
    "data": ["product_view.xml",
    "purchase_view.xml",
    "sale_view.xml",
    "stock_picking_view.xml",
    "ingram_config_view.xml",
    "security/ir.model.access.csv",
    'workflow.xml',
    'scheduler.xml'],
    'demo_xml': [],
    'installable': True,
    'active': False,
}