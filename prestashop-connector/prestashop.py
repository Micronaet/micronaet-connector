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

'''class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    _inherit = 'product.product'
    
    _columns = {
        'prestashop_categ_id': fields.many2many(
            'product.public.category', string='Public Category', 
            help='Master cagegory for prestashop'),
        }    
'''
class ProductProductWebServer(orm.Model):
    """ Model name: ProductProductWebServer
    """
    _inherit = 'product.product.web.server'

    def clean_metatags(self, value):
        ''' Clean meta tags for problems with some char
        '''
        replace_list = {
            '\'', '\'\'',
            ',', '',
            }
        for from_char, to_char in replace_list.iteritems(): 
            value = value.replace(from_char, to_char)
        return value

    def publish_now_prestashop(self, cr, uid, ids, context=None):
        ''' Publish procedure for prestashop element
        '''
        langs = ['it_IT', 'en_US']
        vat_included = 1.0 #.22
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
        connector = first_proxy.connector_id
        sock = connector_pool.get_prestashop_connector(
            cr, uid, [connector.id], context=context)

        album = first_proxy.connector_id.album_id
        album_id = album.id
        #context['album_id'] = first_proxy.connector_id.album_id.id
        
        rpc_default_code = {}
        path_image_in = os.path.expanduser(album.path)
        for item in self.browse(cr, uid, ids, context=db_context):
            # Readability:
            product = item.product_id

            # TODO publish all!!
            
            default_code = product.default_code
            image_in = '%s.%s' % (
                product.default_code.replace(' ', '_'),
                'jpg',
                )
            # Enable log:
            sock.execute('system', 'log', True)
            
            # Rsync data image file: XXX choose if needed
            rsync_command = \
                'rsync --chown %s --chmod %s -avh -e \'ssh -p %s\' \'%s\' %s@%s:%s' % (
                    connector.rsync_chown,
                    connector.rsync_chmod,
                    connector.rsync_port,
                    os.path.join(path_image_in, image_in), 
                    connector.rsync_user, 
                    connector.host,
                    connector.rsync_path,
                    )
            os.system(rsync_command)
            _logger.info('Launched: %s' % rsync_command)

            price = item.force_price or product.lst_price # XXX correct?
            price *= vat_included # VAT price included
            #image = product.product_image_context # from album_id
            #public_categ_ids = [self.odoo_web_db.get(
            #    c.id) for c in product.public_categ_ids]
            
            # -----------------------------------------------------------------
            # Standard record data:    
            # -----------------------------------------------------------------
            record = {
                'reference': default_code or '', 
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
                }
            try:    
                campaign = product.mx_campaign_out
            except:
                campaign = 0    
                
            availability = product.mx_net_qty - product.mx_oc_out - campaign
            # TODO product.mx_net_mrp_qty (for materials)?
            # -----------------------------------------------------------------
            # Lang record: 
            # -----------------------------------------------------------------
            record_lang = {}
            context_lang = context.copy()            
            for lang in langs:
                context_lang['lang'] = lang
                item_lang = self.browse(
                    cr, uid, item.id, context=context_lang)
                    
                # Read data:    
                name = self.clean_metatags(item_lang.force_name or \
                    item_lang.product_id.name or '')
                meta_title = self.clean_metatags(item_lang.force_name or \
                    item_lang.product_id.name or '')
                meta_description = self.clean_metatags(
                    item_lang.force_description or \
                    item_lang.product_id.large_description or '')
                    
                # Generate record:    
                record_lang[lang] = {
                    # Title:
                    'name': name.replace('\'', '\'\''),
                    'meta_title': meta_title.replace('\'', '\'\''),
                    'meta_description': meta_description.replace('\'', '\'\''),
                    #'fabric': product.fabric,
                    #'type_of_material': product.type_of_material,
                    }

            # -----------------------------------------------------------------
            # Category record
            # -----------------------------------------------------------------
            category = {
                # id_product
                'id_category': product.public_categ_ids[0].website_id if \
                    product.public_categ_ids else 0, # TODO Stock-Sottocosto 62
                'position': 1000,
                'price': price,        
                }
                
            id_product = sock.execute(
                # List parameters:
                'product', 'create', # Operation
                record, record_lang, category, # Dict data
                True, # update_image
                availability, # availability
                )

        _logger.info('Update other product lang:')
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

    def prestashop_rsync_photo(self, cr, uid, ids, context=None):
        ''' Read folder image and publich
        '''
        return True
        
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
