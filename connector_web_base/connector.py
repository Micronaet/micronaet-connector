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

# TODO log operations!!
class ConnectorServer(orm.Model):
    ''' Model name: Connector Server
    '''    
    _name = 'connector.server'
    _description = 'Connector Server'
    
    def clean_as_ascii(self, value):
        ''' Procedure for clean not ascii char in string
        '''
        res = ''
        for c in value:
            if ord(c) <127:
                res += c
            else:
                res += '#'           
        return res
        
    _columns = {
        'name': fields.char('Web server', size=64, required=True),
        'host': fields.char('Input filename', size=100, required=True),
        'port': fields.integer('Port', required=True),
        'database': fields.char('Database', size=100, required=True),
        'username': fields.char('Username', size=100, required=True),
        'password': fields.char('Password', size=100, required=True),

        'company_id': fields.many2one('res.company', 'Company', required=True),         
        'note': fields.text('Note'),
        'album_id': fields.many2one(
            'product.image.album', 'Album', required=True),
        }

    _defaults = {
        'host': lambda *x: 'localhost',
        'port': lambda *x: 8069,
        #'company_id': lambda s, cr, uid, ctx: s.get_default_company(
        #    cr, uid, ctx),
        }    
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
