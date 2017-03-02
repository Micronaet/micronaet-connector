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
        
        # ---------------------------------------------------------------------
        # XLS file:
        # ---------------------------------------------------------------------
        xls_file = '/home/administrator/photo/xls/connector/product.xlsx'
        _logger.warning('Start connector export: %s' % xls_file)        

        WB = xlsxwriter.Workbook(xls_file)
        self.WS = WB.add_worksheet('Sito')
        self.counter = 0
        
        # Write header:
        self.write_xls_line([                
            # TODO image #WS.insert_image('B5', 'logo.png')
            'Web',
            'Codice',
            'Nome',
            'Nome forzato',
            'Prezzo ODOO',
            'Prezzo forzato',
            'Descrizione web',
            'Descrizione forzata',
            'Cat. stat.',
            'Fornitore',
            'Esist. netta',
            'Esist. lorda',
            'Categorie',
            ])
        
        # ---------------------------------------------------------------------
        # Start export product:
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')
        
        # Select only product in web server:
        ws_pool = self.pool.get('product.product.web.server')
        ws_ids = ws_pool.search(cr, uid, [
            ('server_id', '=', ids[0]),
            ], context=context)
        product_ids = [item.product_id.id for item in ws_pool.browse(
            cr, uid, ws_ids, context=context)]    
            
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            # Fields:    
            published = ''    
            force_name = ''
            force_description = ''
            force_price = ''
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
                break

            # TODO public_categ_ ids    
            public_categ_name = [
                item.name for item in product.public_categ_ids]
            self.write_xls_line([                
                published, 
                product.default_code,
                product.name,
                force_name,
                product.lst_price,
                force_price,
                product.large_description,
                force_description,
                product.statistic_category,
                product.first_supplier_id.name \
                    if product.first_supplier_id else '',
                product.mx_net_qty,
                product.mx_lord_qty,
                '%s' % (public_categ_name, ),
                ])

        WB.close()                
        return True  
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
