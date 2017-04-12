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

class ProductPublicCategory(osv.osv):
    _name = 'product.public.category'
    _description = 'Public Category'
    _order = 'sequence, name'

    _constraints = [
        (osv.osv._check_recursion, 
        'Error ! You cannot create recursive categories.', 
        ['parent_id'])
        ]

    # Utility:
    def assign_product_category(
            self, cr, uid, default_code, connector_id, context=None):
        ''' Assign category to product selected
        '''
        #default_code = product.default_code
        if not default_code:
            return False
            
        category_ids = self.search(cr, uid, [
            ('connector_id', '=', connector_id),
            ('start_code', '!=', False)], context=context)
        for category in self.browse(
                cr, uid, category_ids, context=context):
            for start in category.start_code.split('|'):
                if default_code.startswith(start):
                    return category.id
        return False

    def load_product_category(self, cr, uid, connector_id, context=None):
        ''' Assign category to product selected
        '''
        res = {}
        category_ids = self.search(cr, uid, [
            ('connector_id', '=', connector_id),
            ('start_code', '!=', False),
            ], context=context)
        for category in self.browse(
                cr, uid, category_ids, context=context):
            for start in category.start_code.split('|'):
                res[start] = category.id
        return res
    
    def name_get(self, cr, uid, ids, context=None):
        res = []
        for cat in self.browse(cr, uid, ids, context=context):
            names = [cat.name]
            pcat = cat.parent_id
            while pcat:
                names.append(pcat.name)
                pcat = pcat.parent_id
            res.append((cat.id, ' / '.join(reversed(names))))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _get_image(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = tools.image_get_resized_images(obj.image)
        return result

    def _set_image(self, cr, uid, id, name, value, args, context=None):
        return self.write(cr, uid, [id], {
            'image': tools.image_resize_image_big(value)}, context=context)

    _columns = {
        'enabled': fields.boolean('Enabled'),
        'name': fields.char('Name', required=True, translate=True),
        'complete_name': fields.function(
            _name_get_fnc, type='char', string='Name'),
        'parent_id': fields.many2one(
            'product.public.category','Parent Category', select=True),
        'child_id': fields.one2many(
            'product.public.category', 'parent_id', 
            string='Children Categories'),
        'sequence': fields.integer(
            'Sequence', 
            help='Gives the sequence order when displaying a list of product categories.'),

        # NOTE: there is no 'default image', because by default we don't show thumbnails for categories. However if we have a thumbnail
        # for at least one category, then we display a default image on the other, so that the buttons have consistent styling.
        # In this case, the default image is set by the js code.
        # NOTE2: image: all image fields are base64 encoded and PIL-supported
        'image': fields.binary('Image',
            help='This field holds the image used as image for the category, limited to 1024x1024px.'),
        'image_medium': fields.function(_get_image, fnct_inv=_set_image,
            string='Medium-sized image', type='binary', multi='_get_image',
            store={
                'product.public.category': (
                    lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
                },
            help='Medium-sized image of the category. It is automatically '\
                 'resized as a 128x128px image, with aspect ratio preserved. '\
                 'Use this field in form views or some kanban views.'),
        'image_small': fields.function(_get_image, fnct_inv=_set_image,
            string='Smal-sized image', type='binary', multi='_get_image',
            store={
                'product.public.category': (
                    lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
                },
            help='Small-sized image of the category. It is automatically '\
                 'resized as a 64x64px image, with aspect ratio preserved. '\
                 'Use this field anywhere a small image is required.'),
        'website_id': fields.integer('Publish ID'), # XXX no more used!
        'connector_id': fields.many2one(
            'connector.server', 'Linked connector', 
            help='Connector linked where category was imported (no ODOO web)'),
        'start_code': fields.text('Start code', 
            help='Code start with...: separate with |, es: 127TX|027TX|029TX'),    
        }
    
class ProductTemplate(orm.Model):
    ''' Model name: Product template extra for website
    '''    
    _inherit = 'product.template'
    
    _columns = {
        'alternative_product_ids': fields.many2many(
            'product.product', 'product_alternative_rel', 'src_id', 'dest_id', 
            string='Alternative Products', help='Appear on the product page'),
        'accessory_product_ids': fields.many2many(
            'product.product', 'product_accessory_rel', 'src_id', 'dest_id', 
            string='Accessory Products', help='Appear on the shopping cart'),
        #'website_style_ids': fields.many2many(
        #    'product.style', string='Styles'),
        #'website_sequence': fields.integer(
        #    'Sequence', 
        #    help='Determine the display order in the Website E-commerce'),
        #'website_url': fields.function(
        #    _website_url, string='Website url', type='char'),
        'public_categ_ids': fields.many2many(
            'product.public.category', string='Public Category', 
            help='Those categories are used to group similar products for e-commerce.'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
