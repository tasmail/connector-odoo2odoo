# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2014 Elico Corp. All Rights Reserved.
#    Qing Wang <qing.wang@amt.com.cn>
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
from .unit.import_synchronizer import DelayedBatchImporter
from .backend import odoo


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    odoo_bind_ids = fields.One2many(
        comodel_name='odoo.res.partner.category',
        inverse_name='openerp_id',
        string='Odoo Bindings',
        readonly=True,
    )


class OdooResPartnerCategory(models.Model):
    _name = 'odoo.res.partner.category'
    _inherit = 'odoo.binding'
    _inherits = {'res.partner.category': 'openerp_id'}

    openerp_id = fields.Many2one(comodel_name='res.partner.category',
                                 string='Partner Category',
                                 required=True,
                                 ondelete='cascade')


@odoo
class PartnerCategoryAdapter(GenericAdapter):
    _model_name = 'odoo.res.partner.category'
    _odoo_model = 'res.partner.category'

    def search(self, domain, **kwargs):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call(self._odoo_model, 'search', domain, **kwargs)


@odoo
class PartnerCategoryBatchImporter(DelayedBatchImporter):
    """ Delay import of the records """
    _model_name = ['odoo.res.partner.category']


@odoo
class PartnerCategoryImportMapper(ImportMapper):
    _model_name = 'odoo.res.partner.category'

    direct = [
        ('name', 'name'),
        ('parent_id', 'parent_id'),
        ('active', 'active'),
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
