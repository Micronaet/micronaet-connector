# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import xlsxwriter
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class ConnectorServer(orm.Model):
    ''' Model name: Connector Server
    '''    
    _inherit = 'connector.server'
    
    def write_xls_line(self, line):  
        ''' Write on instance data line passed
        '''
        col = 0
        for item in line:
            self.WS.write(self.counter, col, item )
            col += 1            
        self.counter += 1
        return         
    
    def export_xls_file(self, cr, uid, ids, context=None):
        ''' Export excel information for site product
        '''        
        #current_proxy = self.browse(cr, uid, ids, context=context)[0]
        ws_product_pool = self.pool.get('product.product.web.server')
        
        # ---------------------------------------------------------------------
        # Start export product:
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')
        
        # Select only product in web server:
        ws_pool = self.pool.get('product.product.web.server')
        ws_ids = ws_pool.search(cr, uid, [
            ('connector_id', '=', ids[0]),
            ], context=context)
        ws_proxy = ws_pool.browse(cr, uid, ws_ids, context=context)
        product_ids = [item.product_id.id for item in ws_proxy]    

        # Read album on connector from first product
        if not product_ids:
            return False                    
        db_context = context.copy()
        server = ws_proxy[0].connector_id
        db_context['album_id'] = server.album_id.id        
        
        # Read parameter from connector:
        discount = 1.0 - ws_proxy[0].connector_id.discount
        vat_included = 1.0 + ws_proxy[0].connector_id.add_vat
        min_price = ws_proxy[0].connector_id.min_price
         
        # ---------------------------------------------------------------------
        # XLS file:
        # ---------------------------------------------------------------------
        company_name = server.company_id.partner_id.name
        xls_file = '/home/administrator/photo/xls/connector/stato.%s.xlsx' % (
            company_name)
        
        _logger.warning('Start connector export: %s' % xls_file)        

        WB = xlsxwriter.Workbook(xls_file)
        self.WS = WB.add_worksheet('Sito')
        self.counter = 0
        
        # Write header:
        self.write_xls_line([                
            # TODO image #WS.insert_image('B5', 'logo.png')
            'Web',
            'Immagine',
            'Sempre',
            'Codice',
            'Nome',
            'Nome forzato',
            'EAN',
            'Q. x imb.',
            'Peso',
            'Dimensioni',
            'Prezzo ODOO',
            'Prezzo forzato',
            'Prezzo pubblicato',
            'Descrizione web',
            'Descrizione forzata',
            'Cat. stat.',
            'Fornitore',
            'Magaz. - OC - camp',
            'Categoria principale',
            ])
         
        for product in product_pool.browse(
                cr, uid, product_ids, context=db_context):
            # Fields:    
            published = ''
            image = bool(product.product_image_context or '')
            force_name = ''
            force_description = ''
            force_price = ''
            public_categ_name = ''
            for connector in product.web_server_ids:
                if connector.connector_id.id != ids[0]:
                    continue
                if connector.published:
                    published = 'X'
                else:        
                    published = 'O'
                force_price = connector.force_price
                force_description = connector.force_description
                force_price = connector.force_price
                public_categ_name = connector.public_categ_id.name if \
                    connector.public_categ_id else ''
                break

            # TODO public_categ_ ids    
            #public_categ_name = [
            #    item.name for item in product.public_categ_ids]
            try:     
                campaign = product.mx_campaign_out 
            except:
                campaign = 0.0    
            availability = product.mx_net_qty - product.mx_oc_out - campaign
            
            # TODO correct calc:
            #if connector.availability_extra:
            #    availability -= round(
            #        availability * server.availability_extra / 100.0, 0)                    
            ## Check if min stock is present:        
            #if item.force_min_stock and availability < item.force_min_stock:
            #    availability = item.force_min_stock

            
            # Price:
            price = force_price or (product.lst_price * discount)
            price *= vat_included
            price = round(price, server.approx)
            if price <= min_price:
                price = 'MIN: %s' % price
            h, w, l = ws_product_pool.get_prestashop_dimension(product)

            # Weight:
            q_x_pack = product.q_x_pack or 1.0
            if server.volume_weight and h and w and l:
                weight = h * w *  l / server.volume_weight / q_x_pack
            else:
                weight = product.weight                
            
            self.write_xls_line([                
                published,
                image,
                'X' if product.website_always_present else 'O',
                product.default_code,
                product.name,
                force_name,
                product.ean13,
                q_x_pack,
                '%s %s' % (weight, 'vol/w' if server.volume_weight else ''),
                '%s x %s x %s' % (h, w, l),
                product.lst_price,
                force_price,
                price, # published
                
                product.large_description,
                force_description,
                product.statistic_category,
                product.first_supplier_id.name \
                    if product.first_supplier_id else '',
                availability,
                public_categ_name,
                ])

        WB.close()                
        return True  
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
