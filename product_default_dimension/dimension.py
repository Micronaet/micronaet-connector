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
import xlrd
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

class ProductProductDefaultDimension(orm.Model):
    """ Model name: ProductProductDefaultDimension
    """    
    _name = 'product.product.default.dimension'
    _description = 'Default dimension'
    _rec_name = 'name'
    _order = 'name'
    
    def import_dimension_from_excel(self, cr, uid, ids, context=None):
        ''' Import form excel
        '''
        filename = '/home/administrator/photo/xls/dimension.xls'
        try:
            WB = xlrd.open_workbook(filename)
            _logger.info('Import Dimension from %s' % filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )
                
        # Import dimension:        
        WS = WB.sheet_by_index(0)

        for row in range(1, WS.nrows):
            # Parse row:
            parent = WS.cell(row, 0).value            
            seat = WS.cell(row, 1).value
            h = WS.cell(row, 2).value
            w = WS.cell(row, 3).value
            l = WS.cell(row, 4).value
            h_pack = WS.cell(row, 5).value
            w_pack = WS.cell(row, 6).value
            l_pack = WS.cell(row, 7).value
            single = WS.cell(row, 8).value == 'T'
            
            if type(parent) == float:
                parent = '%s' % int(parent)
            
            dimension_ids = self.search(cr, uid, [
                ('name', '=', parent),
                ], context=context)
            data = {
                'name': parent,
                'height': h,
                'width': w,
                'length': l,
                'height_pack': h_pack,
                'width_pack': w_pack,
                'length_pack': l_pack,
                'h_seat': seat,
                'single': single,            
                }
            if dimension_ids:                
                self.write(cr, uid, dimension_ids, data, context=context)
                _logger.info('Update: %s' % parent)
            else:    
                self.create(cr, uid, data, context=context)
                _logger.info('Create: %s' % parent)
                
        # Update product:
        return self.link_all_product(cr, uid, ids, context=context)
        
    def link_all_product(self, cr, uid, ids, context=None):
        ''' Linked all dimension to product
        '''        
        _logger.info('Start update all product dimension')        
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_all'] = True
        item_ids = self.search(cr, uid, [], context=context)
        return self.link_product_dimension(cr, uid, item_ids, context=ctx)

    def link_all_unassigned_product(self, cr, uid, ids, context=None):
        ''' Linked all dimension to product
        '''        
        _logger.info('Start update all unassigned product dimension')        
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_all'] = False
        item_ids = self.search(cr, uid, [], context=context)
        return self.link_product_dimension(cr, uid, ids, context=ctx)

    def link_product_dimension(self, cr, uid, ids, context=None):
        ''' Linked single product (no assert!)
        '''
        if context is None:
            context = {}
        force_all = context.get('force_all', True)    
        
        product_pool = self.pool.get('product.product')
        dimension_proxy = self.browse(cr, uid, ids, context=context)
        for dimension in sorted(dimension_proxy, key=lambda x: len(x.name)):
            # Search product start with
            if force_all:
                domain = []
            else:    
                domain = [('dimension_id', '=', False)]
            domain.append(('default_code', '=ilike', '%s%%' % dimension.name))
            product_ids = product_pool.search(cr, uid, domain, context=context)
                
            # Update with this element
            if product_ids: 
                _logger.info(
                    'Force product dimension start with: %s (tot. %s)' % (
                        dimension.name,
                        len(product_ids),
                        ))
                product_pool.write(cr, uid, product_ids, {
                    'dimension_id': dimension.id,
                    }, context=context)        
        return True
        
    _columns = {
        'name': fields.char('Start code', size=10, required=True),
        'height': fields.float('H. product', digits=(16, 2), required=True),
        'width': fields.float('W. product', digits=(16, 2), required=True),    
        'length': fields.float('L. product', digits=(16, 2), required=True),    
        'height_pack': fields.float('H. pack', digits=(16, 2)),
        'width_pack': fields.float('W. pack', digits=(16, 2)),
        'length_pack': fields.float('L. pack', digits=(16, 2)),
        'h_seat': fields.float('H. Seat', digits=(16, 2)),    
        'single': fields.boolean('Single'),
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name,single)', 'Duplicated code-single!'),        
        ]

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """    
    _inherit = 'product.product'
    
    _columns = {
        'dimension_id': fields.many2one(
            'product.product.default.dimension', 'Default dimension'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
