# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2014. All Rights Reserved.
#    Qing Wang <snowkite@outlook.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Odoo Connector',
    'version': '0.1',
    'category': '',
    'depends': ['base', 'connector',
                'product', 'sale', 'stock'],
    'author': 'Qing Wang',
    'license': 'AGPL-3',
    'website': '',
    'description': """

    """,
    'external_dependencies': {
        'python': ['erppeek'],
    },
    'images': [],
    'demo': [],
    'data': [
        'odooconnect_data.xml',
        'odoo_models_view.xml',
        'odooconnectmenu.xml',
        'partner_view.xml',
    ],
    'installable': True,
    'application': False,
}
