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
    
    # XXX Parematers:
    _langs = ['it_IT', 'en_US']


    # Utility:
    def publish_category(self, cr, uid, rpc, context=None):
        ''' Publish category (usually before publish product)
        '''
        _logger.info('Start publish category on web')
        
        categ_db = [] # public ID for category
        rpc_categ = rpc.model('product.public.category')

        # Read category from web site:
        for categ in rpc_categ.browse([]):
            categ_db.append(categ.id)
        # TODO keep in mind list for remove

        # Read backoffice category:                
        categ_pool = self.pool.get('product.public.category')        
        categ_ids = categ_pool.search(cr, uid, [], context=context)

        for item in categ_pool.browse(cr, uid, categ_ids, context=context):
            # -----------------------------------------------------------------
            #                        Parent analysis:
            # -----------------------------------------------------------------
            if item.parent_id:
                parent = item.parent_id
                data = {
                    'name': parent.name, 
                    #'parent_id': False,
                    #'image': 
                    'sequence': parent.sequence,
                    }
                    
                if parent.website_id in categ_db:
                    # Web: update parent category:
                    rpc_categ.write(parent.website_id, data)
                    
                    parent_website_id = parent.website_id
                else:
                    # Web: create parent element:
                    parent_website_id = rpc_categ.create(data).id
                    
                    # Save ID web in backoffice
                    categ_pool.write(cr, uid, parent.id, {
                        'website_id': parent_website_id}, context=context)
                        
                    # Update database:    
                    categ_db.append(parent_website_id)
            else:
                parent_website_id = False
                                
            # -----------------------------------------------------------------
            #                        Category analysis:
            # -----------------------------------------------------------------
            data = {
                'name': item.name,
                'parent_id': parent_website_id,
                'sequence': item.sequence,
                }
                
            if item.website_id in categ_db:
                rpc_categ.write(item.website_id, data)
                website_id = item.website_id
            else:
                # Web: create category
                website_id = rpc_categ.create(data).id           
                
                # Save new category in backoffice
                categ_pool.write(cr, uid, item.id, {
                    'website_id': website_id}, context=context)
                
                # Updata database:    
                categ_db.append(website_id)
        _logger.info('End publish category on web')
        return True
        
    def publish_now(self, cr, uid, ids, context=None):
        ''' Publish now button
            Used also for more than one elements (not only button click)
            Note all product must be published on the same web server!
            
        '''    
        if context is None:    
            context = {}

        # Read first element only for setup parameters:        
        first_proxy = self.browse(cr, uid, ids, context=context)[0]
        parameter = first_proxy.connector_id
        context['album_id'] = first_proxy.connector_id.album_id.id

        # Database access:
        rpc_server = 'http://%s:%s' % (parameter.host, parameter.port)
        rpc_database = parameter.database
        rpc_username = parameter.username
        rpc_password = parameter.password
        
        # Connect to web server:
        rpc = erppeek.Client(
            rpc_server, rpc_database, rpc_username, rpc_password)
        rpc_product = rpc.model('product.product')

        # Publish category before (only once):
        self.publish_category(cr, uid, rpc, context=context)
                
        for item in self.browse(cr, uid, ids, context=context):
            # Readability:
            product = item.product_id

            default_code = product.default_code
            price = item.force_price or product.lst_price # XXX correct?
            image = product.product_image_context # from album_id
            description = \
                item.force_description or product.large_description
            public_categ_ids = [c.website_id for c in product.public_categ_ids]
            
            # Open socket:
            rpc_product_proxy = rpc_product.browse(
                [('default_code', '=', default_code)])

            # Language data:
            # TODO manage language:
            product_lang_data = {
                'name': item.force_name or product.name,
                'description_sale': description,
                'fabric': product.fabric,
                'type_of_material': product.type_of_material,
                }
            
            # Standard data:    
            product_data = {
                # TODO remove when manage language:
                'name': item.force_name or product.name,
                'description_sale': description,
                'fabric': product.fabric,
                'type_of_material': product.type_of_material,

                'default_code': default_code,
                'website_published': item.published,
                'image': image,
                'lst_price': price,

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
                'vat_price': price * 1.22,      
                'public_categ_ids': [(6, 0, public_categ_ids)],
                }

            # Check Web presence for product:
            if rpc_product_proxy:
                product_ids = [p.id for p in rpc_product_proxy]
                product_ids = rpc_product.write(
                    product_ids, product_data)
                _logger.info('Update web %s product %s' % (
                    rpc_database, default_code))
            else:
                product_ids = rpc_product.create(product_data)
                _logger.info('Create web %s product %s' % (
                    rpc_database, default_code))
                    
            # Language update loop data:
            # TODO for lang in self._langs:                    
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
