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
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImporter,
                                       OdooImporter,
                                       )
from .unit.mapper import normalize_datetime
from openerp.addons.connector.exception import MappingError
from .backend import odoo
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    odoo_bind_ids = fields.One2many(
        comodel_name='odoo.res.partner',
        inverse_name='openerp_id',
        string="External Odoo Bindings",
    )


class OdooResPartner(models.Model):
    _name = 'odoo.res.partner'
    _inherit = 'odoo.binding'
    _inherits = {'res.partner': 'openerp_id'}
    _description = 'External Odoo Partner'

    _rec_name = 'name'

    openerp_id = fields.Many2one(comodel_name='res.partner',
                                 string='Partner',
                                 required=True,
                                 ondelete='cascade')
    created_at = fields.Datetime(string='Created At (on External Odoo)',
                                 readonly=True)
    updated_at = fields.Datetime(string='Updated At (on External Odoo)',
                                 readonly=True)


@odoo
class PartnerAdapter(GenericAdapter):
    _model_name = 'odoo.res.partner'
    _odoo_model = 'res.partner'

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
        domain.extend(['|', ('customer', '=', True), ('supplier', '=', True)])

        _logger.debug(
            "domain %s use to filter %s records".format(
                domain, self._odoo_model))
        return self._call(self._odoo_model, 'search', domain)


@odoo
class PartnerBatchImporter(DelayedBatchImporter):
    """ Import the external Odoo Partners.

    For every partner in the list, a delayed job is created.
    """
    _model_name = ['odoo.res.partner']

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            from_date=from_date,
            to_date=to_date
        )
        _logger.info('search for external odoo partners %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


@odoo
class PartnerImportMapper(ImportMapper):
    _model_name = 'odoo.res.partner'

    direct = [
        ('name', 'name'),
        ('customer', 'customer'),
        ('is_company', 'is_company'),
        ('supplier', 'supplier'),
        ('website', 'website'),
        ('phone', 'phone'),
        ('mobile', 'mobile'),
        ('fax', 'fax'),
        ('email', 'email'),
        ('title', 'title'),
        ('comment', 'comment'),
        (normalize_datetime('create_date'), 'created_at'),
        (normalize_datetime('write_date'), 'updated_at'),
    ]

    @mapping
    def customer_group_id(self, record):
        # import customer groups
        binder = self.binder_for(model='odoo.res.partner.category')
        category_ids = []
        for cate_id in record['category_id']:
            category_id = binder.to_openerp(cate_id, unwrap=True)

            if category_id is None:
                raise MappingError("The partner category with "
                                   "external Odoo id %s does not exist" %
                                   cate_id)
            category_ids.append(category_id)

        return {'category_id': [(6, 0, category_ids)]}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@odoo
class PartnerImporter(OdooImporter):
    _model_name = ['odoo.res.partner']

    _base_mapper = PartnerImportMapper

    def _import_dependencies(self):
        """ Import the dependencies fro the record"""
        record = self.odoo_record
        for category_id in record['category_id']:
            self._import_dependency(
                category_id, 'odoo.res.partner.category')
