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
        
    def auto_select_product(self, cr, uid, connector_id, context=None):
        ''' Auto select product with son particular case
            Overrided depend on company rules
        '''
        product_pool = self.pool.get('product.product')

        # Procedure that create connector product elements:
        # XXX overrided!
        query = '''
            SELECT id 
            FROM product_product 
            WHERE 
                default_code  != '' AND 
                length(default_code) > 6 AND
                substring(default_code, 1,3) > '000' AND 
                substring(default_code, 1,3) < '999' OR
                substring(default_code, 1,2) in ('TL', 'PO', 'MT')
            ORDER BY default_code;
            '''
        cr.execute(query)
        product_ids = [item[0] for item in cr.fetchall()]
        _logger.info('All product: %s' % len(product_ids))

        # ---------------------------------------------------------------------
        # Check product esistence
        # ---------------------------------------------------------------------        
        negative_ids = []
        positive_ids = []
        i = 0
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):                
            # Log information:    
            i += 1
            if i % 50 == 0:
                _logger.info('Product read: %s' % i)

            product_id = product.id
            if product.website_always_present:
                positive_ids.append(product_id)
            else:
                # mx_net_qty
                stock_status = product.mx_net_mrp_qty - product.mx_oc_out
                # No campaign here
                if stock_status <= 0.0:
                    negative_ids.append(product_id)
                else: 
                    positive_ids.append(product_id)          
        _logger.info('Negative product: %s' % len(negative_ids))
        _logger.info('Positive product: %s' % len(positive_ids))
        
        # ---------------------------------------------------------------------
        # Unactivate negative product:        
        # ---------------------------------------------------------------------
        negative_connector_ids = self.search(cr, uid, [
            ('connector_id', '=', connector_id),
            ('product_id', 'in', negative_ids),
            ], context=context)
        self.write(cr, uid, negative_connector_ids, {
             'published': False, # XXX or force 0 quantity!!
             }, context=context)
        _logger.info(
            'Negative connector product: %s' % len(negative_connector_ids))

        # ---------------------------------------------------------------------
        # Activate positive product:        
        # ---------------------------------------------------------------------
        # Yet present:
        positive_connector_ids = self.search(cr, uid, [
            ('connector_id', '=', connector_id),
            ('product_id', 'in', positive_ids),
            ], context=context)
        self.write(cr, uid, positive_connector_ids, {
             'published': True, # XXX or force 0 quantity!!
             }, context=context)
        _logger.info(
            'Positive connector product: %s' % len(positive_connector_ids))

        # ---------------------------------------------------------------------
        # All product yet present:
        # ---------------------------------------------------------------------
        current_product_ids = []
        current_product_ids.extend(negative_connector_ids)
        current_product_ids.extend(positive_connector_ids)
        
        current_ids = [item.product_id.id for item in self.browse(
            cr, uid, current_product_ids, context=context)]
        _logger.info(
            'Current connector product line: %s' % len(current_product_ids))
        _logger.info(
            'Current product selected (must be equal): %s' % len(current_ids))
        
        # ---------------------------------------------------------------------
        # Create product not present:
        # ---------------------------------------------------------------------
        i = 0
        for item_id in positive_ids: # Create positive only
            if item_id in current_ids:
                continue # yet present
            i += 1    
            self.create(cr, uid, {
                'connector_id': connector_id,
                'product_id': item_id,
                'published': True,
                }, context=context)
        _logger.info('New connector product: %s' % i)        
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
