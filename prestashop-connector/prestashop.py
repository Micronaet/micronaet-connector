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

class ConnectorServer(orm.Model):
    """ Model name: ConnectorServer
    """    
    _inherit = 'connector.server'
    
    def get_prestashop_connector(self, cr, uid, context=None):
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

    def prestashop_import_category(self, cr, iud, ids, context=None):
        ''' Prestashop import category
        '''
        sock = self.get_prestashop_connector(cr, uid, context=context)
        category_list = sock.execute('category', 'list')

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
