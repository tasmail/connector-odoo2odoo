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
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImporter,
                                       OdooImporter,
                                       )
from .backend import odoo
from .connector import get_environment
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class ResUser(models.Model):
    _inherit = 'res.users'

    odoo_bind_ids = fields.One2many(
        comodel_name='odoo.res.users',
        inverse_name='openerp_id',
        string='Odoo Bindings',
        readonly=True,
    )


class OdooResUser(models.Model):
    _name = 'odoo.res.users'
    _inherit = 'odoo.binding'
    _inherits = {'res.users': 'openerp_id'}

    openerp_id = fields.Many2one(comodel_name='res.users',
                                 string='User',
                                 required=True,
                                 ondelete='cascade')


@odoo
class ResUserAdapter(GenericAdapter):
    _model_name = 'odoo.res.users'
    _odoo_model = 'res.users'

    def search(self, from_date, to_date, **kwargs):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        domain = [('login', '!=', 'admin')]

        dt_fmt = DEFAULT_SERVER_DATETIME_FORMAT
        if from_date is not None:
            domain.append(('write_date', '>=', from_date.strftime(dt_fmt)))
        if to_date is not None:
            domain.append(('write_date', '<=', to_date.strftime(dt_fmt)))

        _logger.debug(
            "domain %s use to filter %s records".format(
                domain, self._odoo_model))
        return self._call(
            self._odoo_model,
            'search',
            domain if domain else [])


@odoo
class ResUserBatchImporter(DelayedBatchImporter):
    """ Delay import of the records """
    _model_name = ['odoo.res.users']

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            from_date=from_date,
            to_date=to_date
        )
        _logger.info('search for external odoo users %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


@odoo
class ResUserImportMapper(ImportMapper):
    _model_name = 'odoo.res.users'

    direct = [
        ('name', 'name'),
        ('login', 'login'),
        ('active', 'active'),
        ('password', 'password')
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@odoo
class ResUserImporter(OdooImporter):
    _model_name = ['odoo.res.users']

    _base_mapper = ResUserImportMapper


@job(default_channel='root.odoo')
def user_import_batch(session, model_name, backend_id, filters=None):
    """ Prepare the import of users modified on external Odoo """
    if filters is None:
        filters = {}
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(ResUserBatchImporter)
    importer.run(filters=filters)
