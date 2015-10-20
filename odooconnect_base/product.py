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
import logging
from openerp import models, fields
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper,
                                                  )
from .unit.backend_adapter import GenericAdapter
from .unit.mapper import normalize_datetime
from .unit.import_synchronizer import (DelayedBatchImporter,
                                       OdooImporter,
                                       AddCheckpoint,
                                       )
from .backend import odoo
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


def chunks(items, length):
    for index in xrange(0, len(items), length):
        yield items[index:index + length]


class OdooProductProduct(models.Model):
    _name = 'odoo.product.product'
    _inherit = 'odoo.binding'
    _inherits = {'product.product': 'openerp_id'}
    _description = 'External Odoo Product'

    openerp_id = fields.Many2one(comodel_name='product.product',
                                 string='Product',
                                 required=True,
                                 ondelete='restrict')
    created_at = fields.Date('Created At (on external Odoo)')
    updated_at = fields.Date('Updated At (on external Odoo)')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    magento_bind_ids = fields.One2many(
        comodel_name='odoo.product.product',
        inverse_name='openerp_id',
        string='External Odoo Bindings',
    )


@odoo
class ProductProductAdapter(GenericAdapter):
    _model_name = 'odoo.product.product'
    _odoo_model = 'product.product'

    def search(self, from_date=None, to_date=None, **kwargs):
        """ Search records according to some criteria
        and returns a list of ids

        :rtype: list
        """
        domain = []

        dt_fmt = DEFAULT_SERVER_DATETIME_FORMAT
        if from_date is not None:
            domain.append(('write_date', '>=', from_date.strftime(dt_fmt)))
        if to_date is not None:
            domain.append(('write_date', '<=', to_date.strftime(dt_fmt)))
        return self._call(
            self._odoo_model, 'search', domain, **kwargs)

    def read(self, ids, **kwargs):
        """ Returns the information of a record

        :rtype: dict
        """
        return self._call(self._odoo_model, 'read', ids, **kwargs)

    def write(self, ids, values, **kwargs):
        """ Update records on the external system """
        return self._call(self._odoo_model, 'write', ids, values, **kwargs)


@odoo
class ProductBatchImporter(DelayedBatchImporter):
    """ Import the External Odoo Products.

    For every product category in the list, a delayed job is created.
    Import from a date
    """
    _model_name = ['odoo.product.product']

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(from_date=from_date,
                                                 to_date=to_date)
        _logger.info('search for external odoo products returned %s',
                     record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


@odoo
class ProductImportMapper(ImportMapper):
    _model_name = 'odoo.product.product'
    direct = [('name', 'name'),
              ('description', 'description'),
              ('weight', 'weight'),
              ('lst_price', 'lst_price'),
              ('active', 'active'),
              ('short_description', 'description_sale'),
              ('default_code', 'default_code'),
              (normalize_datetime('write_date'), 'write_date'),
              (normalize_datetime('write_date'), 'write_date'),
              ]

    @mapping
    def categories(self, record):
        binder = self.binder_for('odoo.product.category')
        main_cat_id = binder.to_openerp(record['categ_id'][0], unwrap=True)

        if main_cat_id is None:
            default_categ = self.backend_record.default_category_id
            if default_categ:
                main_cat_id = default_categ.id

        result = {'categ_id': main_cat_id}
        return result

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@odoo
class ProductImporter(OdooImporter):
    _model_name = ['odoo.product.product']

    _base_mapper = ProductImportMapper

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.odoo_record
        self._import_dependency(record['categ_id'][0],
                                'odoo.product.category')

    def _create(self, data):
        openerp_binding = super(ProductImporter, self)._create(data)
        checkpoint = self.unit_for(AddCheckpoint)
        checkpoint.run(openerp_binding.id)
        return openerp_binding
