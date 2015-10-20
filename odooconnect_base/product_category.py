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
                                                  ImportMapper
                                                  )
from openerp.addons.connector.exception import (MappingError,
                                                )
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImporter,
                                       OdooImporter,
                                       AddCheckpoint,
                                       )
from .backend import odoo
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class OdooProductCategory(models.Model):
    _name = 'odoo.product.category'
    _inherit = 'odoo.binding'
    _inherits = {'product.category': 'openerp_id'}
    _description = 'External Odoo Product Category'

    openerp_id = fields.Many2one(comodel_name='product.category',
                                 string='Product Category',
                                 required=True,
                                 ondelete='cascade')
    odoo_parent_id = fields.Many2one(
        comodel_name='odoo.product.category',
        string='External Odoo Parent Category',
        ondelete='cascade',
    )
    odoo_child_ids = fields.One2many(
        comodel_name='odoo.product.category',
        inverse_name='odoo_parent_id',
        string='External Odoo Child Categories',
    )


class ProductCategory(models.Model):
    _inherit = 'product.category'

    magento_bind_ids = fields.One2many(
        comodel_name='odoo.product.category',
        inverse_name='openerp_id',
        string="External Odoo Bindings",
    )


@odoo
class ProductCategoryAdapter(GenericAdapter):
    _model_name = 'odoo.product.category'
    _odoo_model = 'product.category'

    def search(self, from_date=None, to_date=None, **kwargs):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        domain = kwargs.get('domain', [])

        dt_fmt = DEFAULT_SERVER_DATETIME_FORMAT
        if from_date is not None:
            domain.append(('write_date', '>=', from_date.strftime(dt_fmt)))
        if to_date is not None:
            domain.append(('write_date', '<=', to_date.strftime(dt_fmt)))

        _logger.debug(
            "domain %s use to filter %s records".format(
                domain, self._odoo_model))
        return self._call(self._odoo_model, 'search', domain)

    def read(self, ids, **kwargs):
        return self._call(self._odoo_model, 'read', ids, **kwargs)


@odoo
class ProductCategoryBatchImporter(DelayedBatchImporter):
    """ Import the External Odoo Product Categories.

    For every product category in the list, a delayed job is created.
    A priority is set on the jobs according to their level to rise the
    chance to have the top level categories imported first.
    """
    _model_name = ['odoo.product.category']

    def _import_record(self, odoo_id, priority=None):
        """ Delay a job for the import """
        super(ProductCategoryBatchImporter, self)._import_record(
            odoo_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)

        updated_ids = self.backend_adapter.search(from_date, to_date)

        trees = self.backend_adapter.search(domain=[('parent_id', '=', False)])

        base_priority = 10

        def import_nodes(tree, level=0):
            node = self.backend_adapter.read(tree, fields=['child_id'])
            child_ids = node.values()[0]
            node_id = node.values()[1]
            if updated_ids and node_id in updated_ids:
                self._import_record(
                    node_id, priority=base_priority + level)
            for child_id in child_ids:
                import_nodes(child_id, level=level + 1)
        for tree in trees:
            import_nodes(tree)


@odoo
class ProductCategoryImporter(OdooImporter):
    _model_name = ['odoo.product.category']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.odoo_record
        # import parent category
        # the root category has a 0 parent_id
        if record.get('parent_id'):
            parent_id = record['parent_id'][0]
            if self.binder.to_openerp(parent_id) is None:
                importer = self.unit_for(OdooImporter)
                importer.run(parent_id)

    def _create(self, data):
        openerp_binding = super(ProductCategoryImporter, self)._create(data)
        checkpoint = self.unit_for(AddCheckpoint)
        checkpoint.run(openerp_binding.id)
        return openerp_binding


@odoo
class ProductCategoryImportMapper(ImportMapper):
    _model_name = 'odoo.product.category'

    direct = [
        ('name', 'name'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        if not record.get('parent_id'):
            return
        binder = self.binder_for()
        category_id = binder.to_openerp(record['parent_id'][0], unwrap=True)
        odoo_cat_id = record['parent_id'][0]

        if category_id is None:
            raise MappingError("The product category with "
                               "external odoo id %s is not imported." %
                               record['parent_id'])
        return {'parent_id': category_id, 'odoo_parent_id': odoo_cat_id}
