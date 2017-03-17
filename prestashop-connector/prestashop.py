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
        return True
        
    # Override action for test if prestashop product
    def publish_now(self, cr, uid, ids, context=None):
        ''' Call original function for no prestashop product
        '''
        prestashop_ids = []
        odoo_ids = []
        for product in self.browse(cr, uid, ids, context=context)
            if product.connector_id.prestashop:
                prestashop_ids.append(product.id)
            else:
                odoo_ids.append(product.id)
        super(ProductProductWebServer, self).publish_now(
            cr, uid, odoo_ids, context=context)
        

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
        import pdb; pdb.set_trace()
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
