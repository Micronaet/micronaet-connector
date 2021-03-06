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
import xlsxwriter
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

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    _inherit = 'product.product'
    
    _columns = {
        'website_always_present': fields.boolean('Always present',
            help='Always present in web site selection'),
        }    

class ProductProductWebServer(orm.Model):
    """ Model name: ProductProductWebServer
    """
    _inherit = 'product.product.web.server'

    def get_prestashop_dimension(self, product):
        ''' Use a function for override in particular case
        '''
        return (
            product.height,
            product.width,
            product.length,
            )
        
    def clean_metatags(self, value):
        ''' Clean meta tags for problems with some char
        '''
        replace_list = {
            '\'': '\'\'', # SQL problem with '
            '"': '', # Link replace problem
            #',': ' ', # XXX
            #'.': ' ',# XXX
            '  ': ' ',
            }
        for from_char, to_char in replace_list.iteritems(): 
            value = value.replace(from_char, to_char)
        return value

    def auto_select_product(self, cr, uid, connector_id, context=None):
        ''' Auto select product with son particular case
            Overrided depend on company rules
        '''        
        # Procedure that create connector product elements:
        # XXX overrided!
        return True

    def schedule_publish_prestashop_now_all(self, cr, uid, only_selected=True,
            without_image=True, context=None):
        ''' Search web server and publish 
            context: force_one is used for publish a connector via button
        '''
        if context is None:
            context = {}
        
        # ---------------------------------------------------------------------
        # Parameter from schedule operation:
        # ---------------------------------------------------------------------
        # Setup context (write)
        if only_selected:
            context['only_selected'] = only_selected
        if without_image:
            context['without_image'] = without_image

        # Get from context (read):    
        force_one = context.get('force_one', False)
        
        # TODO move in connector
        # Force only manual selection withuot recalc:
        server_pool = self.pool.get('connector.server')
        if force_one:
            server_ids = force_one
        else:
            server_ids = server_pool.search(cr, uid, [
                ('scheduled', '=', True),
                ], context=context)
               
        for connector_id in server_ids:
            # Force selection when scheduled:            
            if not force_one:
                self.auto_select_product(
                    cr, uid, connector_id, context=context)
           
            product_ids = self.search(cr, uid, [
                ('connector_id', '=', connector_id),
                ], context=context)
            if not product_ids:
                _logger.error(
                    'No product tu publish, check scheduled in server!')
                return False
        return self.publish_now_prestashop(
            cr, uid, product_ids, context=context)        
        
    def publish_now_prestashop(self, cr, uid, ids, context=None):
        ''' Publish procedure for prestashop element
        '''
        def clean_partner_name(name):
            ''' Clean partner name for log file
            '''
            if not name:
                return ''
            replace_list = (
                ('.', ''),
                (' ', '_'),
                ('/', ''),             
                ('\\', ''),
                )
            for old, new in replace_list:
                name = name.replace(old, new)
            return name    
        
        langs = ['it_IT', 'en_US']

        # No category publish (get from Prestashop not created here!)
        _logger.info('Start publish prestashop product')
        connector_pool = self.pool.get('connector.server')
        if context is None:    
            context = {}
        without_image = context.get('without_image', False)   

        # Context used here:    
        db_context = context.copy()
        db_context['lang'] = self._lang_db
        
        # Read first element only for setup parameters:        
        first_proxy = self.browse(cr, uid, ids, context=context)[0]
        connector = first_proxy.connector_id
        sock = connector_pool.get_prestashop_connector(
            cr, uid, [connector.id], context=context)

        connector = first_proxy.connector_id 
        album = connector.album_id
        
        if connector.add_vat:
            vat_included = 1 + connector.add_vat
        else:    
            vat_included = 1            
        min_price = connector.min_price # Publish only >=
        discount = 1.0 - connector.discount

        album_id = album.id
        #context['album_id'] = first_proxy.connector_id.album_id.id
        
        rpc_default_code = {}
        path_image_in = os.path.expanduser(album.path)

        # ---------------------------------------------------------------------
        # Log file:
        # ---------------------------------------------------------------------
        filename = '/home/administrator/photo/xls/connector/log_%s.xlsx' % (
            clean_partner_name(connector.company_id.partner_id.name),
            )
        
        # Open file and write header
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Prodotti')
        WS.write(0, 0, 'Codice')
        WS.write(0, 1, 'Prezzo')
        WS.write(0, 2, 'Categoria')
        WS.write(0, 3, 'Disponibilita')
        WS.write(0, 4, 'Errore')

        i = 0
        # XXX LOG: 
        # f_log_image = open('/tmp/prestashop_log_no_image', 'w')
        for item in self.browse(cr, uid, ids, context=db_context):
            i += 1

            # Readability:
            product = item.product_id

            WS.write(i, 0, product.default_code or '?')

            # TODO publish all!!
            
            default_code = product.default_code
            image_in = '%s.%s' % (
                product.default_code.replace(' ', '_'),
                'jpg',
                )
            image_in_fullname = os.path.join(path_image_in, image_in)
            image_found = True
            if not os.path.isfile(image_in_fullname):
                image_found = False                
                error = 'Image not found: %s%s' % (
                    image_in_fullname,
                    ' (not necessary)' if without_image else '',
                    )
                _logger.error(error)                
                WS.write(i, 4, error)
                # XXX Changed for unpublish article
                #if not without_image: # publish without image:
                #    continue 
            
            if not item.product_id.large_description:    
                error = 'Web description not found: %s' % default_code
                _logger.error(error)                
                WS.write(i, 4, error)
                continue
            
            if not item.public_categ_id:
                error = 'No category: %s' % default_code
                _logger.error(error)                
                WS.write(i, 4, error)
                continue               
                
            # Enable log:
            _logger.info('Start publish: %s' % product.default_code)     
            sock.execute('system', 'log', True)

            # -----------------------------------------------------------------
            # Publish image (test):
            # -----------------------------------------------------------------
            if without_image:
                _logger.info('No image mode: %s' % product.default_code)                
            else:
                # Rsync data image file: XXX choose if needed
                chown = ' --chown %s' % connector.rsync_chown if \
                    connector.rsync_chown else ''
                chmod = ' --chmod %s' % connector.rsync_chmod if \
                    connector.rsync_chmod else ''
                rsync_command = \
                    'rsync%s%s -avh -e \'ssh -p %s\' \'%s\' %s@%s:%s' % (
                        chown,
                        chmod,
                        connector.rsync_port,
                        image_in_fullname, 
                        connector.rsync_user, 
                        connector.host,
                        connector.rsync_path,
                        )
                os.system(rsync_command)
                _logger.info('Launched: %s' % rsync_command)

            # -----------------------------------------------------------------
            # Price evaulation:
            # -----------------------------------------------------------------
            # Price forced or pricelist:
            price = item.force_price or (product.lst_price * discount)

            # Vat add or not:
            price *= vat_included
            price = round(price, connector.approx)

            # Vat min price check:
            if price <= min_price:
                WS.write(
                    i, 4, 'Price %s is under minimal, jump product: %s' % (
                    price,
                    default_code, 
                    ))
                continue # jump                
            WS.write(i, 1, price)
            
            # -----------------------------------------------------------------
            # Standard record data:    
            # -----------------------------------------------------------------
            h, w, l = self.get_prestashop_dimension(product) # TODO pack!

            # -----------------------------------------------------------------
            # Weight evaulation:
            # -----------------------------------------------------------------
            q_x_pack = product.q_x_pack or 1
            if connector.volume_weight and h and w and l:
                weight = h * w * l / connector.volume_weight / q_x_pack
            else:
                weight = product.weight                
            
            # XXX Only product with image will be published!
            if image_found:
                active = item.published
            else:
                _logger.error('Deactivated for image: %s' % default_code)
                #f_log_image.write('Rimosso: %s' % default_code)
                active = False
            record = {
                'reference': default_code or '', 
                'ean13': product.ean13 or '',
                'weight': weight,
                'height': h,
                'width': w,
                'depth': l,
                'active': active, # item.published,
                # Extra:
                #'q_x_pack': product.q_x_pack,
                #'vat_price': price,
                #'public_categ_ids': [(6, 0, public_categ_ids)],
                }

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
                meta_title = name
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
            if not item.public_categ_id:
                WS.write(i, 4, 'No category')
                continue
                
            category = {
                # id_product
                #'id_category': product.public_categ_ids[0].website_id if \
                #    product.public_categ_ids else 0,
                'id_category': item.public_categ_id.website_id if \
                    item.public_categ_id else 0,
                'position': 1000,
                'price': price, # TODO here?!?!   
                }

            WS.write(i, 2, item.public_categ_id.name)

            # Generate availability:                
            try:    
                campaign = product.mx_campaign_out
            except:
                campaign = 0    

            availability = product.mx_net_qty - product.mx_oc_out - campaign
            if connector.availability_extra:
                availability -= round(
                    availability * connector.availability_extra / 100.0, 
                    0,
                    )
                    
            # Check if min stock is present:        
            if item.force_min_stock and availability < item.force_min_stock:
                availability = item.force_min_stock
                        
            # TODO product.mx_net_mrp_qty (for materials)?
            WS.write(i, 3, availability)
            id_product = sock.execute(
                # List parameters:
                'product', 'create', # Operation
                record, record_lang, category, # Dict data
                not without_image, # update_image
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

    def auto_select_product_button(self, cr, uid, ids, context=None):
        ''' Auto select product with son particular case
        '''        
        return self.pool.get('product.product.web.server').auto_select_product(
            cr, uid, ids[0], context=context)
    
    # Override original function for check if is a prestashop connections:
    def publish_all_connector(self, cr, uid, ids, context=None):
        ''' Force publish all this elements
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        if current_proxy.prestashop:
            _logger.info('Force all Prestashop web publish:')
            if context is None:
                context = {}
                
            context_force = context.copy()
            context_force['force_one'] = ids
            
            product_pool = self.pool.get('product.product.web.server')
            return product_pool.schedule_publish_prestashop_now_all(
                cr, uid, context=context_force)
            _logger.info('End all Prestashop web publish:')
        else:
            _logger.info('Redirect to ODOO web publish:')
            return super(ConnectorServer, self).publish_all_connector(
                cr, uid, ids, context=context)
    
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
        ''' Read folder image and publish
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

    # -------------------------------------------------------------------------
    # Scheduled action:
    # -------------------------------------------------------------------------
    def prestashop_order_import_scheduled(self, cr, uid, ids, days=7, 
            context=None):
        ''' Prestashop import category
        '''
        # Parameter:
        if type(ids) in (long, int):
            ids = (ids, )
        sock = self.get_prestashop_connector(cr, uid, ids, context=context)

        from_date = (datetime.now() - timedelta(days=days)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        
        try:
            order_list = sock.execute(
                'order', 'list', 
                [('date_add', '>=', from_date)], # parameter
                )
            _logger.info('Order list from: %s' % from_date)
        except:
            raise osv.except_osv(
                _('XMRLPC'), 
                _('Error connecting server, check xmlrpc listner!'),
                )
                
        # Send email:        
        partner_pool = self.pool.get('res.partner') # non necessary
        action_pool = self.pool.get('ir.actions.report.xml')

        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 'prestashop-connector', 'group_prestashop_order_admin')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
    
        # Create body:
        order_body = ''
        header = _('''
            <th>Rif.</th>
            <th>Delivery date</th>
            <th>Invoice date</th>
            <th># Delivery</th>
            <th>ID Customer</th>
            <th>State</th>
            <th>Payment</th>
            <th>Total paid</th>
            <th>Net total</th>
            
            <th>Product</th>
            <th>Code</th>
            <th>Q.</th>
            <th>Price</th>
            ''')

        for order in order_list:
            order = dict(order)
            order_body += '''
                <tr>
                    <td>%(reference)s</td>
                    <td>%(delivery_date)s</td>
                    <td>%(invoice_date)s</td>
                    <td>%(delivery_number)s</td>
                    <td>%(id_customer)s</td>
                    <td>%(current_state)s</td>
                    <td>%(payment)s</td>
                    <td>%(total_paid)s</td>
                    <td>%(total_price_tax_excl)s</td>
                    
                    <td>%(product_name)s</td>
                    <td>%(product_reference)s</td>
                    <td>%(product_quantity)s</td>
                    <td>%(product_price)s</td>
                </tr>    
                ''' % order
                    
        body = '<table>%s%s</table>' % (header, order_body)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body=body, 
            subject=_('Prestashop order from %s') % from_date,
            partner_ids=[(6, 0, partner_ids)],
            context=context,
            )
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
