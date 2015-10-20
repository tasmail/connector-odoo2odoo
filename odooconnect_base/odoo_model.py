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
from openerp import models, fields, api
from openerp.addons.connector.session import ConnectorSession
from datetime import datetime, timedelta
from .unit.import_synchronizer import import_batch
IMPORT_DELTA_BUFFER = 30  # seconds


class OdooBackend(models.Model):
    _name = 'odoo.backend'
    _description = 'Odoo Backend'
    _inherit = 'connector.backend'

    _backend_type = 'odoo'

    @api.model
    def select_versions(self):
        """ Available versions in the backend.

        Can be inherited to add custom versions.  Using this method
        to add a version from an ``_inherit`` does not constrain
        to redefine the ``version`` field in the ``_inherit`` model.
        """
        return [('8.0', '8.0')]

    version = fields.Selection(selection='select_versions', required=True)
    location = fields.Char(
        string='Location',
        required=True,
        help="Url to odoo application",
    )
    username = fields.Char(
        string='Username',
        help="Webservice user",
    )
    password = fields.Char(
        string='Password',
        help="Webservice password",
    )
    database = fields.Char(
        string="Database",
        help="External database name")
    default_lang_id = fields.Many2one(
        comodel_name='res.lang',
        string='Default Language',
        help="If a default language is selected, the records "
             "will be imported in the translation of this language.\n"
             "Note that a similar configuration exists "
             "for each storeview.",
    )
    default_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Default Product Category',
        help='If a default category is selected, products imported '
             'without a category will be linked to it.',
    )

    import_partners_from_date = fields.Datetime(
        string='Import customers and suppliers from date',
    )

    import_users_from_date = fields.Datetime(
        string='Import users from date')

    import_products_from_date = fields.Datetime(
        string='Import products from date',
    )

    import_categories_from_date = fields.Datetime(
        string='Import categories from date',
    )
    import_orders_from_date = fields.Datetime(
        string='Import sale orders from date',
        help='do not consider non-imported sale orders before this date. '
             'Leave empty to import all sale orders',
    )

    @api.multi
    def import_partners(self):
        self._import_from_date(
            'odoo.res.partner', 'import_partners_from_date')
        return True

    @api.multi
    def import_users(self):
        self._import_from_date(
            'odoo.res.users', 'import_users_from_date')
        return True

    @api.multi
    def import_product_categories(self):
        self._import_from_date('odoo.product.category',
                               'import_categories_from_date')
        return True

    @api.multi
    def import_product_product(self):
        self._import_from_date('odoo.product.product',
                               'import_products_from_date')
        return True

    @api.multi
    def import_sale_orders(self):
        self._import_from_date('odoo.sale.order', 'import_orders_from_date')

        return True

    @api.multi
    def _import_from_date(self, model, from_date_field):
        session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
        import_start_time = datetime.now()
        for backend in self:
            from_date = getattr(backend, from_date_field)
            if from_date:
                from_date = fields.Datetime.from_string(from_date)
            else:
                from_date = None
            import_batch.delay(session, model,
                               backend.id,
                               filters={'from_date': from_date,
                                        'to_date': import_start_time})
        next_time = import_start_time - timedelta(seconds=IMPORT_DELTA_BUFFER)
        next_time = fields.Datetime.to_string(next_time)
        self.write({from_date_field: next_time})
