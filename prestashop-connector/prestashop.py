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
import xmlrpclib
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
    _inherit = 'product.product.web.server'

    def publish_now_prestashop(self, cr, uid, ids, context=None):
        ''' Publish procedure for prestashop element
        '''
        # No category publish (get from Prestashop not created here!)
        _logger.info('Start publish prestashop product')        
        connector_pool = self.pool.get('connector.server')

        if context is None:    
            context = {}
            
        # Context used here:    
        db_context = context.copy()
        db_context['lang'] = self._lang_db

        # Read first element only for setup parameters:        
        first_proxy = self.browse(cr, uid, ids, context=context)[0]
        rpc_server = connector_pool.get_prestashop_connector(
            cr, uid, [first_proxy.connector_id], context=context)

        album_id = first_proxy.connector_id.album_id.id
        #context['album_id'] = first_proxy.connector_id.album_id.id
        
        rpc_default_code = {}
        path_image_in = './' # TODO from album
        for item in self.browse(cr, uid, ids, context=db_context):
            # Readability:
            product = item.product_id

            # TODO publish all!!
            
            default_code = product.default_code
            image_in = product.default_code.replace(' ', '_')
            
            # Rsync data image file: XXX choose if needed
            rsync_command = \
                'rsync --chown %s --chmod %s -avh -e \'ssh -p %s\' %s%s %s:%s' % (
                    first_proxy.rsync_chown,
                    first_proxy.rsync_chmod,
                    first_proxy.host,
                    path_image_in, 
                    image_in, 
                    first_proxy.rsync_user, 
                    first_proxy.rsync_path,
                    )
            os.system(rsync_command)

            price = item.force_price or product.lst_price # XXX correct?
            #image = product.product_image_context # from album_id
            #public_categ_ids = [self.odoo_web_db.get(
            #    c.id) for c in product.public_categ_ids]
            
            # Standard data:    
            id_product = sock.execute(
                # List parameters:
                'product', 
                'create', 
                {
                    'reference': default_code, 
                    'ean13': product.ean13 or '',
                    'weight': product.weight,
                    'height': product.height,
                    'width': product.width,
                    'depth': product.height,
                    'active': item.published,
                    # Extra:
                    #'q_x_pack': product.q_x_pack,
                    #'vat_price': price * 1.22,      
                    #'public_categ_ids': [(6, 0, public_categ_ids)],
                    }, 
                {
                    'it_IT': {
                        'name': item.force_name or product.name, # title
                        'meta_title': item.force_name or product.name, # XXX
                        'meta_description': 
                            item.force_description or product.large_description,
                    #'fabric': product.fabric,
                    #'type_of_material': product.type_of_material,
                        }, 
                    # TODO lang:                        
                    'en_US': {
                        'name': 'ENCon immagine',
                        'meta_title': 'ENTitolo della sedia di prova con misure',
                        'meta_description': 'ENDescrizione della sedia di prova',
                        },
                    },
                {
                    # id_product
                    'id_category': product.public_categ_ids[0] if \
                        product.public_categ else 0, # TODO Stock-Sottocosto 62
                    'position': 1000,
                    'price': price,        
                    },
                    
                True, # update_image
                )

        _logger.info('Update other product lang:')

        '''for lang in self._langs:  
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
                    })'''
        return True
        
    # Override action for test if prestashop product
    def publish_now(self, cr, uid, ids, context=None):
        ''' Call original function for no prestashop product
        '''
        prestashop_ids = []
        odoo_ids = []
        for product in self.browse(cr, uid, ids, context=context):
            if product.connector_id.prestashop:
                prestashop_ids.append(product.id)
            else:
                odoo_ids.append(product.id)
        if odoo_ids:
            super(ProductProductWebServer, self).publish_now(
                cr, uid, odoo_ids, context=context)
        if prestashop_ids:
            self.publish_now_prestashop(
                cr, uid, prestashop_ids, context=context)
        return True

class ConnectorServer(orm.Model):
    """ Model name: ConnectorServer
    """    
    _inherit = 'connector.server'
    
    def get_prestashop_connector(self, cr, uid, ids, context=None):
        ''' Return XMLRPC connector with server
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]

        # XMLRPC connection for autentication (UID) and proxy 
        sock = xmlrpclib.ServerProxy(
            'http://%s:%s/RPC2' % (
                current_proxy.host,       
                current_proxy.port,
                ), 
            allow_none=True,
            )

        # Log enable:
        #res = sock.execute('system', 'log', True)        
        return sock

    def prestashop_import_category(self, cr, uid, ids, context=None):
        ''' Prestashop import category
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        # Pool used:
        category_pool = self.pool.get('product.public.category')
        
        # Load current in ODOO database:
        category_ids = category_pool.search(cr, uid, [
            ('connector_id', '=', ids[0]),
            ], context=context)
        website_ids = [item.website_id for item in category_pool.browse(
            cr, uid, category_ids, context=context)]
        
        sock = self.get_prestashop_connector(cr, uid, ids, context=context)
        
        try:
            category_list = sock.execute('category', 'list')
        except:
            raise osv.except_osv(
                _('XMRLPC'), 
                _('Error connecting server, check xmlrpc listner!'),
                )

        for website_id, name in category_list:
            if website_id in website_ids:
                website_ids.remove(website_id)
                continue
            category_pool.create(cr, uid, {
                'name': name,
                'website_id': website_id,
                'connector_id': ids[0],
                #'sequence': 
                }, context=context)
                
        # Remove no more present category
        if website_ids:
            category_pool.unlink(cr, uid, website_ids, context=context)
            
        return True

    _columns = {
        'prestashop': fields.boolean(
            'Prestashop', help='Prestashop web server'),
        'rsync_user': fields.char('Rsync user', size=64),
        'rsync_port': fields.integer('Rsync port'),
        'rsync_path': fields.char('Rsync path', size=180),
        'rsync_chown': fields.char('Rsync chown', size=30),
        'rsync_chmod': fields.char('Rsync chmod', size=10),
        }
        
    _defaults = {
        'rsync_port': lambda *x: 22,
        'rsync_chown': lambda *x: 'www-data:www-data',
        'rsync_chmod': lambda *x: '775',
        }

class ProductPublicCategory(orm.Model):
    """ Model name: ProductPublicCategory
    """
    
    _inherit = 'product.public.category'
    
    
    _columns = {
        #'prestashop': fields.boolean('Prestashop', help='Prestashop category'),
        # Use website_id!
        #'prestashop_id': fields.integer('ID prestashop'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
