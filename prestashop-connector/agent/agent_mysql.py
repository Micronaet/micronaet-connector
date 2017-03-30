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
import shutil
from PIL import Image

# -----------------------------------------------------------------------------
#                                MYSQL CLASS
# -----------------------------------------------------------------------------
class mysql_connector():
    ''' MySQL connector for MySQL database
    '''
    # -------------------------------------------------------------------------
    # Parameters for defaults:
    # -------------------------------------------------------------------------
    # TODO manage in other mode!
    id_shop = 1
    pack_stock_type = 3
    id_langs = {
        'it_IT': 1,
        'en_US': 2,
        }
    ext_in = 'jpg'
    ext_out = 'jpg'    

    id_image_type = {
        '': False, # empty default image no resize for now
        'cart_default': (80, 80),
        'small_default': (98, 98),
        'medium_default': (125, 125),
        'home_default': (250, 250),
        'large_default': (458, 458),
        'thickbox_default': (800, 800),
        'category_default': (870, 217),
        'scene_default': (870, 270),
        'm_scene_default': (161 ,58),
        }
    # -------------------------------------------------------------------------
    #                              Utility function:
    # -------------------------------------------------------------------------
    def resize_image(self, from_image, to_image, size):
        ''' Resize image as indicated in Mysql table
        '''
        if size: # else no resize
            origin = Image.open(from_image)
            resized = origin.resize(size, Image.ANTIALIAS)

            image_type = 'JPEG' if self.ext_out.upper() == 'JPG' else\
                self.ext_out.upper()
            
            resized.save(to_image, image_type)
        else:
            shutil.copyfile(from_image, to_image)
            
        return True
        
    def _search_table_key(self, table, key, extra_field=False):
        ''' Search table key for get insert/update mode
        '''
        if extra_field:
            query = 'select count(*), ' + extra_field + ' from %s where %s;'
        else:
            query = 'select count(*) from %s where %s;'
        
        where = ''
        table = '%s_%s' % (self._prefix, table)
        
        for field, value in key:
            if where:
                where += ' and '
            quote = '\'' if type(value) in (str, ) else ''
            where += '`%s` = %s%s%s' % (
                field, quote, value, quote)        
        query = query % (table, where)
        
        # Check if present
        if not self._connection:
            return False
        cr = self._connection.cursor()
        cr.execute(query)
        res = cr.fetchall()
        try: 
            if res[0]['count(*)'] > 0:
                if extra_field:
                    return where, res[0][extra_field]
                else:
                    return where
        except:
            pass
        if extra_field:
            return False, False
        else:
            return False
                
    def _prepare_mysql_query(
            self, update_where, record, table, field_quote=None):
        ''' Prepare insert query passing record and quoted field list
            update_where: if present means that is the key search filter so
                need to be updated not created
        '''
        if field_quote is None:
            field_quote = []
            
        if update_where: 
            # update
            table = '%s_%s' % (self._prefix, table)
            fields = ''
            for field, value in record.iteritems():
                if fields:
                    fields += ', '
                quote = '\'' if field in field_quote else ''

                fields += '`%s` = %s%s%s' % (field, quote, value, quote)
                
            query = 'UPDATE %s SET %s WHERE %s;' % (
                table,
                fields,
                update_where,
                )   
            if self._log:
                print '[INFO] UPDATE: ', query            
        else: 
            # insert
            table = '%s_%s' % (self._prefix, table)
            fields = values = ''
            for field, value in record.iteritems():
                if fields:
                    fields += ', '
                fields += '`%s`' % field

                quote = '\'' if field in field_quote else ''
                if values:
                    values += ', '
                values += '%s%s%s' % (quote, value, quote)
                
            query = 'INSERT INTO %s(%s) VALUES (%s);' % (
                table, fields, values)        
            if self._log:
                print '[INFO] INSERT: ', query
        return query
        
    def _expand_lang_data(self, data):
        ''' Generate extra data for SEO management
            mandatory: name, meta_title, meta_description            
        '''
        if not data:
            return {}
        
        name = data.get('name', '')
        meta_title = data.get('meta_title', '')
        data['description'] = '<p>%s</p>' % (meta_title or name)

        meta_description = data.get('meta_description', '')
        link_rewrite = meta_description.lower(
            ).replace(' ', '-').replace('\'', '')
        data['link_rewrite'] = link_rewrite
        data['meta_keywords'] = meta_description
        data['description_short'] = '<p>%s</p>' % (meta_description)
        return
        
    # -------------------------------------------------------------------------
    #                             Exported function:
    # -------------------------------------------------------------------------
    def update_image_file(self, reference, id_image):
        ''' Update image reference in rsync folder to prestashop path        
        '''
        root_path = '/var/www/html/2015.redesiderio.it/site/public/https' 

        path_in = os.path.join(root_path, 'img/odoo')        
        path_out = os.path.join(root_path, 'img/p',)
        
        # Create origin image:
        image_in = os.path.join(
            path_in, 
            '%s.%s' % (
                reference.replace(' ', '_'), 
                self.ext_in,
                ),
            )

        # Create destination folder:
        key_image = str(id_image)
        key_folder = [item for item in key_image]
        path_image_out = os.path.join(path_out, *key_folder)

        os.system('mkdir -p %s' % path_image_out) # Create all image folder if needed

        image_list = self.id_image_type.iteritems()

        for image_type, size in image_list:
            image_out = os.path.join(
                path_image_out,
                '%s%s%s.%s' % (
                    key_image, # ID image
                    '-' if image_type else '', # separator -
                    image_type or '', # name of image type
                    self.ext_out, # extension
                    ),
                )
            try:
                self.resize_image(image_in, image_out, size)
            except:
                 print '[ERROR] Cannot move image: %s' % image_in
                 continue
                
            if self._log:
                print '[INFO] Image %s > %s' % (image_in, image_out)
        os.system('chown -R www-data:www-data %s' % path_image_out)
        os.system('chmod -R 775 %s' % path_image_out)
            
        return True
        
    def write_image(self, record_data, reference, update_image=False):
        ''' Create image record for product and generate image in asked
        '''
        if not self._connection:
            return False

        id_product = record_data.get('id_product', False)
        
        # ---------------------------------------------------------------------
        # Create image record
        # ---------------------------------------------------------------------
        field_quote = ['legend', ] # unique for all
        record = { # Direct not updated:
            # id_image
            'id_product': 0,
            'position': 1,
            'cover': 1, # Show as default for list view
            }
        record.update(record_data)

        # Delete previous all product image?
        
        # Check if insert or update # TODO correct the filter?
        update_where, search_id = self._search_table_key(
            'image', 
            [('id_product', id_product),('cover', 1)], # cover is key
            'id_image', # extra field
            )
                
        query = self._prepare_mysql_query(
            update_where, record, 'image', field_quote)
        cr = self._connection.cursor()
        cr.execute(query)
        if update_where:
            id_image = search_id # from search query            
        else:
            id_image = self._connection.insert_id()
        
        self._connection.commit()        
        
        # ---------------------------------------------------------------------
        # Create image_lang (now X lang empty fields)
        # ---------------------------------------------------------------------
        for lang, id_lang in self.id_langs.iteritems():
            record = { # Direct not updated:
                'id_image': id_image,
                'id_lang': id_lang,
                'legend': '',
                }                

            # Check if insert or update
            update_where = self._search_table_key(
                'image_lang', [
                    ('id_image', id_image),
                    ('id_lang', id_lang),
                    ])
                
            #record.update(record_data)  
            query = self._prepare_mysql_query(
                update_where, record, 'image_lang', field_quote)
            cr = self._connection.cursor()
            cr.execute(query)
            self._connection.commit()        

        # ---------------------------------------------------------------------
        # Create image_shop
        # ---------------------------------------------------------------------
        record = { # Direct not updated:
            'id_image': id_image,
            'id_shop': self.id_shop,
            'cover': 1,
            'id_product': id_product,
            }           

        # Check if insert or update
        update_where = self._search_table_key(
            'image_shop', [
                ('id_image', id_image),
                ('id_shop', self.id_shop),
                ('id_product', id_product),
                ])
                 
        #record.update(record_data)  
        query = self._prepare_mysql_query(
            update_where, record, 'image_shop', field_quote)
        cr = self._connection.cursor()
        cr.execute(query)
        self._connection.commit()        

        # ---------------------------------------------------------------------
        # Redim image in correct folder:
        # ---------------------------------------------------------------------
        if update_image:
            self.update_image_file(reference, id_image)
        return id_image
        
    def write_availability(self, record_data):
        ''' Update stock available
            record_data has product and quantity elements
            search product_id with attribute 0
        ''' 
        table = 'ps_stock_available'
        # ---------------------------------------------------------------------
        # Generate record data
        # ---------------------------------------------------------------------
        record = {
            #'id_stock_available':,
            #'id_product':,
            #'quantity': 0,
            'id_product_attribute': 0,
            'id_shop': 1,
            'id_shop_group': 0,
            'depends_on_stock': 0,
            'out_of_stock': 2,
            }
        record.update(record_data)
        id_product = record.get('id_product', 0)
        # TODO test 0

        # ---------------------------------------------------------------------
        # Reset all product selected:
        # ---------------------------------------------------------------------
        if not self._connection:
            return False
        cr = self._connection.cursor()
        query = '''
            UPDATE %s
            SET `quantity` = 0 
            WHERE `product_id` = %s;
            ''' % (table, id_product)
        if self._log:
            print query
        cr.execute(query)
        self._connection.commit()        

        # ---------------------------------------------------------------------
        # Search default attribute
        # ---------------------------------------------------------------------
        query = '''
            SELECT id_stock_available
            FROM %s
            WHERE `id_product` = %s and `id_product_attribute` = 0;
            ''' % (table, id_product)
        if self._log:
            print query
        cr.execute(query)
        item_ids = [item['id_stock_available'] for item in cr.fetchall()]
        
        # ---------------------------------------------------------------------
        # Create or update
        # ---------------------------------------------------------------------
        update_where = ''
        if item_ids: # Update
            update_where = 'id_stock_available in (%s)' % (
                ('%s' % item_ids)[1:-1])

        query = self._prepare_mysql_query(
            update_where, record, table, field_quote=None)
        if self._log:
            print query
        cr.execute(query)
        self._connection.commit()        
        return True
            
    def write_category(self, record_data):
        ''' Update product - category link if present or create
            product_shop: id_product, id_category, position  
            category_product: price 
        '''
        if not self._connection:
            return False
            
        # TODO check mandatory fields
        # ---------------------------------------------------------------------
        # category_product
        # ---------------------------------------------------------------------
        id_product = record_data.get('id_product', False)
        id_category = record_data.get('id_category', False)
        position = record_data.get('position', False)
        price = record_data.get('price', False)

        if not any((id_product, id_category)):
            # Error mandatory parameters
            return False
            
        field_quote = [] # all numeric
        record = { # Direct not updated:
            'id_product': id_product,
            'id_category': id_category,
            'position': position,
            }
            
        # Check if insert or update        
        update_where = self._search_table_key(
            'category_product', [
                ('id_product', id_product),
                ('id_category', id_category),
                ])
                
        query = self._prepare_mysql_query(update_where,
            record, 'category_product', field_quote)

        cr = self._connection.cursor()
        cr.execute(query)
        self._connection.commit()
        
        # ---------------------------------------------------------------------
        # product_shop
        # ---------------------------------------------------------------------
        field_quote = [
            'unity', 'redirect_type', 'available_date', 'condition',
            'visibility', 'date_add', 'date_upd',
            ]
        # TODO write date     
        record = {
            'id_product': id_product,
            'id_shop': self.id_shop,
            'id_category_default': id_category,
            'id_tax_rules_group': 1,
            'on_sale': 0,
            'online_only': 0,
            'ecotax': 0.0,
            'minimal_quantity': 1,
            'price': price,
            'wholesale_price': 0.0,
            'unity': '',
            'unit_price_ratio': 0.0,
            'additional_shipping_cost': 0.0,
            'customizable': 0,
            'uploadable_files': 0,
            'text_fields': 0,
            'active': 1,
            'redirect_type': '404',
            'id_product_redirected': 0,
            'available_for_order': 1,
            'available_date': '2013-01-01',
            'condition': 'new',
            'show_price': 1,
            'indexed': 1,
            'visibility': 'both',
            'cache_default_attribute': 0,
            'advanced_stock_management': 0,
            'date_add': '2013-10-01 00:00:00',
            'date_upd': '2013-10-01 00:00:00',
            'pack_stock_type': self.pack_stock_type,
            }    

        # Check if insert or update
        update_where = self._search_table_key(
            'product_shop', [
                ('id_product', id_product),
                ('id_shop', self.id_shop),
                ])
        
        # Crete and execute query:
        query = self._prepare_mysql_query(update_where,
            record, 'product_shop', field_quote)
        cr = self._connection.cursor()
        cr.execute(query)
        self._connection.commit()
        return True

    def create(self, *parameter, **parameter_args):
        ''' Update record
            record: data of product
            lang_record: dict with ID lang: dict of valued
        '''
        # Parameter liste explode:
        record_data = parameter[0]
        lang_record_db = parameter[1] 
        record_category = parameter[2]
        update_image = parameter[3]
        availability = parameter[4]
        
        # Parameter name-value explode:
        #update_image = parameter_args.get('update_image', False)
        reference = record_data.get('reference', False) # For image name
        
        if not self._connection:
            return False

        # ---------------------------------------------------------------------
        # Fields validation:
        # ---------------------------------------------------------------------
        field_mandatory = ['reference', 'price'] # TODO manage check

        # Use quote (fields are for all tables used here:
        field_quote = [  
            # -----------          
            # product:
            # -----------          
            # String:
            'ean13', 'upc', 'redirect_type', 'visibility',
            'condition', 'reference', 'supplier_reference',
            'unity', 'location',
            # Date:
            'available_date', 'date_add', 'date_upd',
            
            # ----------------      
            # product_lang:
            # ----------------     
            # String
            'description', 'description_short', 'link_rewrite',
            'meta_description', 'meta_keywords', 'meta_title',
            'name',
            # Date: 
            'available_now', 'available_later',
            ]

        # ---------------------------------------------------------------------
        # Update numeric product
        # ---------------------------------------------------------------------
        record = {
            #'id_product':
            'id_supplier': 0,
            'id_manufacturer': 0,
            'id_category_default': 0, # TODO
            'id_shop_default': self.id_shop,
            'id_tax_rules_group': 1,
            'on_sale': 0,
            'online_only': 0,
            'ean13': '', # TODO
            'upc': '',
            'ecotax': 0.0,
            'quantity': 0,
            'minimal_quantity': 1,
            'price': 0.0, # TODO
            'wholesale_price': 0.0,
            'unity': '',
            'unit_price_ratio': 0.0,
            'additional_shipping_cost': 0.0,
            'reference': '', # TODO
            'supplier_reference': '', # TODO
            'location': '',
            'width': 0.0, # TODO
            'height': 0.0, # TODO
            'depth': 0.0, # TODO
            'weight': 0.0, # TODO
            'out_of_stock': 2, # TODO
            'quantity_discount': 0,
            'customizable': 0,
            'uploadable_files': 0,
            'text_fields': 0,
            'active': 1, # TODO
            'redirect_type': '404',
            'id_product_redirected': 0,
            'available_for_order': 1, # TODO
            'available_date': '2014-02-21', # TODO
            'condition': 'new',
            'show_price': 1,
            'indexed': 1,
            'visibility': 'both',
            'cache_is_pack': 0,
            'cache_has_attachments': 0,
            'is_virtual': 0,
            'cache_default_attribute': 0, # TODO
            'date_add': '2017-01-01 10:00:00',
            'date_upd': '2017-01-01 10:00:00',
            'advanced_stock_management': 0,
            'pack_stock_type': 3,
            }        
        record.update(record_data) # Add field passed from ODOO

        # Check if insert or update
        update_where, search_id = self._search_table_key(
            'product', 
            [('reference', reference)],
            'id_product',
            )
        
        query = self._prepare_mysql_query(
            update_where, record, 'product', field_quote)
        cr = self._connection.cursor()
        cr.execute(query)
        if update_where:
            id_product = search_id
        else:
            id_product = self._connection.insert_id()
        self._connection.commit()
        
        # ---------------------------------------------------------------------
        # Update lang product_lang:
        # ---------------------------------------------------------------------
        if not lang_record_db:
            # Record not created
            return False #id_product

        for lang, lang_data in lang_record_db.iteritems():
            id_lang = self.id_langs.get(lang)
            # TODO check if lang is correct

            # Default data:
            record_lang_data = {
                # Fixed key field:
                'id_product': id_product,
                'id_shop': self.id_shop,
                'id_lang': id_lang,
                
                # Field to populate from ODOO:
                'description': '',
                'description_short': '',
                'link_rewrite': '',
                'meta_description': '',
                'meta_keywords': '',
                'meta_title': '',
                'name': '',
                'available_now': '',
                'available_later': '',
                }
                
            # Generate extra data and integrate:
            self._expand_lang_data(lang_data)
            record_lang_data.update(lang_data)

            # Check if insert or update
            update_where = self._search_table_key(
                'product_lang', [
                    ('id_product', id_product),
                    ('id_shop', self.id_shop),
                    ('id_lang', id_lang),
                    ])
            
            # Prepare and run query:
            query = self._prepare_mysql_query(update_where,
                record_lang_data, 'product_lang', field_quote)                
            cr = self._connection.cursor()
            cr.execute(query)
            self._connection.commit()

        # ---------------------------------------------------------------------
        # Update product category block:
        # ---------------------------------------------------------------------
        record_category['id_product'] = id_product
        self.write_category(record_category)
        
        # ---------------------------------------------------------------------
        # Update product category block:
        # ---------------------------------------------------------------------
        id_image = self.write_image({
            'id_product': id_product,
            #'position': 1,
            #'cover': '',
            }, reference, update_image=update_image)
            
        # ---------------------------------------------------------------------
        # Update availability block:
        # ---------------------------------------------------------------------
        self.write_availability({
            'id_product': id_product,
            'quantity': availability,
            })    
        return id_product

    def write(self, **parameter):
        ''' Update record
        '''
        id_product = parameter['id_product']
        record = parameter['record']
        
        # Update numeric ps_product
        
        # Update lang ps_product_lang
        
        return True        
        
    def search(self, domain):
        ''' Search product
            parameter = [('field', 'operator', 'value')]
        '''
        
        if not self._connection:
            return False
        cr = self._connection.cursor()
        query = '''
            SELECT id_product
            FROM ps_product
            WHERE %s %s '%s';
            ''' % (
                domain[0],
                domain[1],
                domain[2],                
                )
        if self._log:
            print query
        cr.execute(query)
        return [item['id_product'] for item in cr.fetchall()]

    def category_list(self, ):
        ''' Return list of category present in Prestashop
        '''
        if not self._connection:
            return False
            
        cr = self._connection.cursor()
        query = '''
            SELECT id_category, name
            FROM ps_category_lang
            WHERE id_lang = %s;
            ''' % (self.id_langs.get('it_IT', 1), )
            
        if self._log:
            print query
        cr.execute(query)
        return [
            (item['id_category'], item['name']) for item in cr.fetchall()]
        
    # -------------------------------------------------------------------------
    # Constructor:
    # -------------------------------------------------------------------------
    def __init__(self, database, user, password, server='localhost', port=3306, 
            charset='utf8', prefix='ps'):
        ''' Init procedure        
        '''
        # Save parameters:
        self._database = database
        self._user = user
        self._password = password
        self._server = server or 'localhost'
        self._port = port or 3306
        self._charset = charset
        self._status = 'connected'
        self._connected = True
        self._prefix = prefix
        
        self._log = False # no log
        
        try:            
            error = 'Error no MySQLdb installed'
            import MySQLdb, MySQLdb.cursors

            error = 'Error connecting to database: %s:%s > %s [%s]' % (
                self._server,
                self._port,
                self._database,
                self._user,
                )
                
            self._connection = MySQLdb.connect(
                host=self._server,
                user=self._user,
                passwd=self._password,
                db=self._database,
                cursorclass=MySQLdb.cursors.DictCursor,
                charset=self._charset,
                )                        
        except:
            self._status = error
            self._connected = False
        return
    
# -----------------------------------------------------------------------------
#                                 MAIN PROCEDURE    
# -----------------------------------------------------------------------------
def main():
    ''' Main procedure
    '''
    # TODO read condig PHP file
    database = 'database'
    user = 'user'
    password = 'password'
    server = 'localhost'
    port = 3306
    
    mysql_ps = mysql_connector(database, user, password, server, port)
    if not mysql_ps._connected:
        print 'Not connected: %s' % mysql_ps._status
        sys.exit()
    else:    
        return 'Connected'

if __name__ == '__main__':
    main()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
