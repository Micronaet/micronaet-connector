# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)

class ProductPublishWebsiteWizard(orm.TransientModel):
    ''' Wizard for publish wizard 
    '''
    _name = 'product.publish.website.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_publish(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None:
            context = {}        
        
        # Pool:
        product_pool = self.pool.get('product.product')
        connector_pool = self.pool.get('product.product.web.server')
        category_pool = self.pool.get('product.public.category')
        
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        
        product_ids = context.get('active_ids')
        mode = wizard_browse.mode
        webserver_id = wizard_browse.webserver_id.id
        published = wizard_browse.published
        
        # Get category database
        import pdb; pdb.set_trace()
        category_db = category_pool.load_product_category(
            cr, uid, connector_id, context=context)
        
        # Create record if not present in product
        publish_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            if not product.default_code:
                raise osv.except_osv(
                    _('Product error'), 
                    _('No default code for product: %s' % product.name),
                    )
            
            for server in product.web_server_ids:
                if server.connector_id.id == webserver_id:
                    publish_ids.append(server.id)
                    break

            else: # only if not found:
                data = {
                    'connector_id': webserver_id,
                    'product_id': product.id,
                    }
                
                # Assign category if present:    
                default_code = product.default.code
                if default_code and category_db:
                    for start, category_id in category_db.iteritems():
                        if default_code.startswith(start):
                            data['public_categ_id'] = category_id
                            break
                        
                publish_ids.append(
                    connector_pool.create(cr, uid, data, context=context))
            
        if publish_ids:
            # Set all record for publish:                    
            connector_pool.write(cr, uid, publish_ids, {
                'published': published,                
                }, context=context)

            # TODO publish category only one time!
            # Update button:
            if mode == 'publish':
                 connector_pool.publish_now(
                    cr, uid, publish_ids, context=context)
                    
        return True #{'type': 'ir.actions.act_window_close'}

    _columns = {
        'mode': fields.selection([
            ('selection', 'Only selection'),
            ('publish', 'Publish'),
            ], 'Mode', required=True),
        'webserver_id': fields.many2one(
            'connector.server', 'Webserver', required=True),
        'published': fields.boolean('Published', 
            help='In not check remove article from web site'),            
        }
        
    _defaults = {
        'published': lambda *x: True,
        'mode': lambda *x: 'selection',
        }    
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
