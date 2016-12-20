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
import xmlrpclib # TODO remove
import erppeek
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

class ProductProductWebServer(orm.Model):
    """ Model name: ProductProductWebServer
    """
    
    _name = 'product.product.web.server'
    _description = 'Product web'
    _rec_name = 'connector_id'
    
    def publish_now(self, cr, uid, ids, context=None):
        ''' Publish now button
        '''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        product = current_proxy.product_id
        parameter = current_proxy.connector_id

        default_code = product.default_code
                
        # Database access:        
        server = 'http://%s:%s' % (parameter.host, parameter.port)
        database = parameter.database
        username = parameter.username
        password = parameter.password

        client = erppeek.Client(server, database, username, password)
        product_rpc = client.model('product.product')
        
        # Open socket:
        product_proxy = product_rpc.browse([('default_code', '=', default_code)])

        product_data = {
            'default_code': default_code,
            'website_published': current_proxy.published,
            'name': current_proxy.force_name or product.name,
            'image': product.image,
            'lst_price': current_proxy.force_price,
            
            # Update with product data:
            # Dimension:
            'height': product.height,
            'width': product.width,
            'length': product.length,
            # Pack dimension:
            'pack_h': product.pack_h,
            'pack_l': product.pack_l,
            'pack_p': product.pack_p,
            # Extra:
            'q_x_pack': product.q_x_pack,            
            }
            
        if product_proxy:     
            product_ids = [item.id for item in product_proxy]       
            product_ids = product_rpc.write(
                product_ids, product_data)
            _logger.info('Update in database %s product %s' % (
                database, default_code))        
        else:
            product_ids = product_rpc.create(product_data)
            _logger.info('Create in database %s product %s' % (
                database, default_code))        
        return True
        
    _columns = {
        'published': fields.boolean('Published'),
        
        'connector_id': fields.many2one(
            'connector.server', 'Web Server', required=True),
        'product_id': fields.many2one('product.product', 'Product'),
            
        # Force field    
        'force_name': fields.char('Force Name', size=64),
        'force_description': fields.text('Force Description'),
        'force_price': fields.float('Force price', digits=(16, 2)),
        # TODO
        }
    
    _defaults = {
       'published': lambda *a: True,
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'web_server_ids': fields.one2many(
            'product.product.web.server', 'product_id', 'Web server'),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
