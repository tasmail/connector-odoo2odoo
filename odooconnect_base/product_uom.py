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
from openerp import models, fields
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImporter, OdooImporter)
from .backend import odoo


class ProductUom(models.Model):
    _inherit = 'product.uom'

    odoo_bind_ids = fields.One2many(
        comodel_name='odoo.product.uom',
        inverse_name='openerp_id',
        string='Odoo Bindings',
        readonly=True,
    )


class OdooProductUom(models.Model):
    _name = 'odoo.product.uom'
    _inherit = 'odoo.binding'
    _inherits = {'product.uom': 'openerp_id'}

    openerp_id = fields.Many2one(comodel_name='product.uom',
                                 string='Product Uom',
                                 required=True,
                                 ondelete='cascade')


@odoo
class ProductUomAdapter(GenericAdapter):
    _model_name = 'odoo.product.uom'
    _odoo_model = 'product.uom'

    def search(self, domain, **kwargs):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call(self._odoo_model, 'search', domain, **kwargs)


@odoo
class ProductUomBatchImporter(DelayedBatchImporter):
    """ Delay import of the records """
    _model_name = ['odoo.product.uom']


@odoo
class ProductUomImportMapper(ImportMapper):
    _model_name = 'odoo.product.uom'

    direct = [
        ('name', 'name'),
        ('uom_type', 'uom_type'),
        ('factor_inv', 'factor_inv'),
        ('active', 'active'),
        ('rounding', 'rouding'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def category_id(self, record):
        binder = self.binder_for('odoo.product.uom.categ')
        cate_id = binder.to_openerp(
            record['category_id'][0], unwrap=True)
        return {'category_id': cate_id}


@odoo
class ProductUomImporter(OdooImporter):
    _model_name = ['odoo.product.product']

    _base_mapper = ProductUomImportMapper

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.odoo_record
        self._import_dependency(record['category_id'][0],
                                'odoo.product.uom.categ')
