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

class ConnectorServer(orm.Model):
    ''' Model name: Connector Server
    '''    
    _inherit = 'connector.server'

    def auto_set_category_connector(self, cr, uid, ids, context=None):
        ''' Set category automatic for this connector
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        _logger.info('Force auto assign of category depend on code')

        category_pool = self.pool.get('product.public.category')
        connector_pool = self.pool.get('product.product.web.server')

        # Get category database
        category_db = category_pool.load_product_category(
            cr, uid, ids[0], context=context)
        category_start = sorted(category_db, reverse=True)
        line_ids = connector_pool.search(cr, uid, [
            ('connector_id', '=', ids[0]),
            ], context=context)
        update = {}    
        
        # Search category depend on start code:
        for line in connector_pool.browse(cr, uid, line_ids, context=context):
            product = line.product_id
            
            # Assign category if present:    
            default_code = product.default_code
            if default_code and category_db:
                public_categ_id = False
                for start in category_start:
                    if default_code.startswith(start):
                        public_categ_id = category_db[start]
                        break
                if public_categ_id:
                    update[line.id] = public_categ_id
        
        # Update operations:
        for item_id, public_categ_id in update.iteritems():
            connector_pool.write(cr, uid, item_id, {
                'public_categ_id': public_categ_id,
                }, context=context)    
        _logger.info('End auto assign of category depend on code')
        return True
        
    def publish_all_connector(self, cr, uid, ids, context=None):
        ''' Override publish operations base elements 
        '''
        _logger.info('Force all ODOO web publish:')
        
        item_pool = self.pool.get('product.product.web.server')
        item_ids = item_pool.search(cr, uid, [
            ('connector_id', '=', ids[0]),
            ], context=context)
        
        if not item_ids:            
            _logger.error('Nothing to publish!')
            return False
            
        # Call button event for publish all elements:
        _logger.error('Publishing %s elements' % len(item_ids))
        item_pool.publish_now(cr, uid, item_ids, context=context)
        _logger.info('End all ODOO web publish:')
        return True

class ProductProductWebServer(orm.Model):
    """ Model name: ProductProductWebServer
    """

    _name = 'product.product.web.server'
    _description = 'Product web'
    _rec_name = 'connector_id'
    
    # XXX Parematers:
    _langs = ['it_IT', 'en_US']
    _lang_db = 'en_US'

    # Utility:
    def publish_category(self, cr, uid, rpc, connector_id, context=None):
        ''' Publish category (usually before publish product)
        '''
        if context is None:
            context = {}
        
        _logger.info('Start publish category on web')        

        # Context used here:    
        db_context = context.copy()

        # Pool web and rpc:
        rpc_categ = rpc.model('product.public.category')
        categ_pool = self.pool.get('product.public.category')        

        # Database used (every connector reset this database), default lang!:
        self.odoo_web_db = {} # odoo ID VS web ID (update instance DB)
        rpc_categ_db = {} # web: name = ID > in default DB lang
        
        # ---------------------------------------------------------------------
        # Read category from web site:
        # ---------------------------------------------------------------------
        # Set lang db for website:
        # TODO 
        #rpc.context = db_context
        for categ in rpc_categ.browse([]):
            rpc_categ_db[categ.name] = categ.id
            
        # TODO keep in mind list for remove

        # ---------------------------------------------------------------------
        # Create backoffice category on RPC web:
        # ---------------------------------------------------------------------
        db_context['lang'] = self._lang_db # set default lang for read
        
        # --------------------------
        # Language default lang: it:
        # --------------------------
        _logger.info('Create category elements:')
        categ_ids = categ_pool.search(cr, uid, [
            ('connector_id', '=', connector_id),
            ], context=db_context)        
        for item in categ_pool.browse(cr, uid, categ_ids, context=db_context):
            data = {
                'name': item.name, 
                'parent_id': False,
                #'image': 
                'sequence': item.sequence,
                }
                
            if item.name in rpc_categ_db:
                self.odoo_web_db[item.id] = rpc_categ_db[item.name]
            else:
                self.odoo_web_db[item.id] = rpc_categ.create(data).id
                rpc_categ_db[item.name] = self.odoo_web_db[item.id] # update DB
        _logger.info('Publish %s category!' % len(categ_ids))
        
        
        # -----------------------
        # Update other languages:
        # -----------------------
        _logger.info('Update other category lang:')
        for lang in self._langs:            
            if lang == self._lang_db:
                continue # no default lang, that create object!
            db_context['lang'] = lang
            rpc.context = db_context #{'lang': lang}
            for item in categ_pool.browse(
                    cr, uid, categ_ids, context=db_context):
                rpc_categ.write(self.odoo_web_db[item.id], {
                    'name': item.name,
                    })

        # ---------------------------------------------------------------------
        # Update hieratic parent on RPC web:
        # ---------------------------------------------------------------------
        _logger.info('Update category parent information:')

        # Note: No need lang in this operations:
        rpc.context = False
        categ_ids = categ_pool.search(cr, uid, [
            ('parent_id', '!=', False)], context=context)        
        for item in categ_pool.browse(cr, uid, categ_ids, context=context):
            try: 
                rpc_categ.write(self.odoo_web_db[item.id], {
                    'parent_id': self.odoo_web_db[item.parent_id.id],
                    })
            except:
                _logger.error('No parent web ID for category %s' % item.name)
                continue
                
        _logger.info('End publish category on web')
        return True
        
    def publish_now(self, cr, uid, ids, context=None):
        ''' Publish now button
            Used also for more than one elements (not only button click)
            Note all product must be published on the same web server!            
        '''    
        if context is None:    
            context = {}
            
        # Context used here:
        db_context = context.copy()
        db_context['lang'] = self._lang_db

        # Read first element only for setup parameters:        
        first_proxy = self.browse(cr, uid, ids, context=context)[0]
        connector = first_proxy.connector_id
        db_context['album_id'] = first_proxy.connector_id.album_id.id
        context['album_id'] = first_proxy.connector_id.album_id.id

        # Database access:
        rpc_server = 'http://%s:%s' % (connector.host, connector.port)
        rpc_database = connector.database
        rpc_username = connector.username
        rpc_password = connector.password
        
        # Connect to web server:
        rpc = erppeek.Client(
            rpc_server, rpc_database, rpc_username, rpc_password)
        rpc_product = rpc.model('product.product')

        # Publish category before (only once):
        self.publish_category(cr, uid, rpc, connector.id, context=context)

        rpc_default_code = {}
        for item in self.browse(cr, uid, ids, context=db_context):
            # Readability:
            product = item.product_id

            default_code = product.default_code
            price = item.force_price or product.lst_price # XXX correct?
            image = product.product_image_context # from album_id
            public_categ_ids = [self.odoo_web_db.get(
                c.id) for c in product.public_categ_ids]
            if public_categ_ids:
                public_categ_ids = [(6, 0, public_categ_ids)]
            else:
                public_categ_ids = False
            if image:
                published = item.published
            else:
                published = False
                _logger.warning('No image for %s' % default_code)    
            
            # Open socket:
            rpc_product_proxy = rpc_product.browse(
                [('default_code', '=', default_code)])

            # Standard data:    
            product_data = {
                # Language data:
                'name': item.force_name or product.name,
                'description_sale': 
                    item.force_description or product.large_description,
                'fabric': product.fabric,
                'type_of_material': product.type_of_material,

                'default_code': default_code,
                'website_published': published,
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
                'public_categ_ids': public_categ_ids,
                }                

            # Check Web presence for product:
            import pdb; pdb.set_trace()
            if rpc_product_proxy:
                product_ids = [p.id for p in rpc_product_proxy]
                rpc_product.write(
                    product_ids, product_data)
                _logger.info('Update web %s product %s' % (
                    rpc_database, default_code))
            else:
                product_ids = rpc_product.create(product_data).id
                _logger.info('Create web %s product %s' % (
                    rpc_database, default_code))
            rpc_default_code[default_code] = product_ids
                    
            # Language update loop data:
            # TODO for lang in self._langs:                    
        _logger.info('Update other product lang:')

        for lang in self._langs:  
            if lang == self._lang_db:
                continue # no default lang, that create object!
                
            db_context['lang'] = lang
            rpc.context = db_context
            for item in self.browse(cr, uid, ids, context=db_context):
                product = item.product_id
                default_code = product.default_code
                # Get product ID from database:
                product_ids = rpc_default_code.get(default_code, [])
                
                # Update language:
                if not product_ids:
                    _logger.warning('No lang %s for %s' % (lang, default_code))
                    continue
                rpc_product.write(product_ids, {
                    'name': item.force_name or product.name,
                    'description_sale': 
                        item.force_description or product.large_description,
                    'fabric': product.fabric,
                    'type_of_material': product.type_of_material,
                    })
        return True

    _columns = {
        'published': fields.boolean('Published'),

        'connector_id': fields.many2one(
            'connector.server', 'Web Server', required=True),
        'product_id': fields.many2one('product.product', 'Product'),
        'public_categ_id': fields.many2one(
            'product.public.category', 'Category'),
        # TODO extra list of category?    
        
        # Force field
        'force_name': fields.char('Force Name', size=64),
        'force_description': fields.text('Force Description'),
        'force_price': fields.float('Force price', digits=(16, 2)),
        'force_min_stock': fields.float('Force min. stock', digits=(16, 2), 
            help='If product is always present set stock value when <=0'),
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
