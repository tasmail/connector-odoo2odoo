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
import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.addons.connector.connector import ConnectorUnit
from openerp.addons.connector.exception import NothingToDoJob
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImporter,
                                       OdooImporter,
                                       )
from .unit.mapper import normalize_datetime
from .backend import odoo
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class OdooSaleOrder(models.Model):
    _name = 'odoo.sale.order'
    _inherit = 'odoo.binding'
    _description = 'External Odoo Sale Order'
    _inherits = {'sale.order': 'openerp_id'}

    openerp_id = fields.Many2one(comodel_name='sale.order',
                                 string='Sale Order',
                                 required=True,
                                 ondelete='cascade')
    odoo_order_line_ids = fields.One2many(
        comodel_name='odoo.sale.order.line',
        inverse_name='odoo_order_id',
        string='External Odoo Order Lines'
    )
    total_amount = fields.Float(
        string='Total amount',
        digits_compute=dp.get_precision('Account')
    )
    odoo_order_id = fields.Integer(
        string='External Odoo Order ID',
        help="'order_id' field in external Odoo")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    odoo_bind_ids = fields.One2many(
        comodel_name='odoo.sale.order',
        inverse_name='openerp_id',
        string="External Odoo Bindings",
    )


class OdooSaleOrderLine(models.Model):
    _name = 'odoo.sale.order.line'
    _inherit = 'odoo.binding'
    _description = 'External Odoo Sale Order Line'
    _inherits = {'sale.order.line': 'openerp_id'}

    odoo_order_id = fields.Many2one(
        comodel_name='odoo.sale.order',
        string='External Odoo Sale Order',
        required=True,
        ondelete='cascade',
        select=True)
    openerp_id = fields.Many2one(comodel_name='sale.order.line',
                                 string='Sale Order Line',
                                 required=True,
                                 ondelete='cascade')
    backend_id = fields.Many2one(
        related='odoo_order_id.backend_id',
        string='Odoo Backend',
        readonly=True,
        store=True,
        required=False,
    )
    tax_rate = fields.Float(string='Tax Rate',
                            digits_compute=dp.get_precision('Account'))
    notes = fields.Char()

    @api.model
    def create(self, vals):
        odoo_order_id = vals['odoo_order_id']
        binding = self.env['odoo.sale.order'].browse(odoo_order_id)
        vals['order_id'] = binding.openerp_id.id
        binding = super(OdooSaleOrderLine, self).create(vals)
        line = binding.openerp_id
        line.write({'price_unit': line.price_unit})
        return binding


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    magento_bind_ids = fields.One2many(
        comodel_name='odoo.sale.order.line',
        inverse_name='openerp_id',
        string="External Odoo Bindings",
    )


@odoo
class SaleOrderAdapter(GenericAdapter):
    _model_name = 'odoo.sale.order'
    _odoo_model = 'sale.order'

    def search(self, from_date=None, to_date=None, **kwargs):
        """ Search records according to some criteria
        and returns a list of ids

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

    def read(self, id, fields=None):
        """ Returns the information of a record

        :rtype: dict
        """
        record = self._call(
            self._odoo_model, 'read', id, fields=fields)

        if record.get('order_line', []):
            lines = []
            for line_id in record.get('order_line', []):
                line_value = self.read_lines(line_id)
                lines.append(line_value)
        record.update({'lines': lines})
        return record

    def read_lines(self, line_id):
        return self._call('sale.order.line', 'read', line_id)


@odoo
class SaleOrderBatchImport(DelayedBatchImporter):
    _model_name = ['odoo.sale.order']

    def _import_record(self, record_id, **kwargs):
        """ Import the record directly """
        return super(SaleOrderBatchImport, self)._import_record(
            record_id, max_retries=0, priority=5)

    def run(self, filters=None):
        """ Run the synchronization """
        if filters is None:
            filters = {}
        from_date = filters.pop('from_date', None)
        to_date = filters.pop('to_date', None)
        record_ids = self.backend_adapter.search(
            from_date=from_date,
            to_date=to_date
        )
        _logger.info('search for odoo saleorders %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


@odoo
class SaleImportRule(ConnectorUnit):
    _model_name = ['odoo.sale.order']

    def _rule_always(self, record, method):
        """ Always import the order """
        return True

    def _rule_global(self, record):
        """ Rule always executed, whichever is the selected rule """
        # the order has been canceled since the job has been created
        order_name = record['name']
        if record['state'] == 'cancel':
            raise NothingToDoJob('Order %s canceled' % order_name)

    def check(self, record):
        """ Check whether the current sale order should be imported
        or not.

        :returns: True if the sale order should be imported
        :rtype: boolean
        """
        self._rule_global(record)


@odoo
class SaleOrderImportMapper(ImportMapper):
    _model_name = 'odoo.sale.order'

    direct = [
        ('name', 'name'),
        (normalize_datetime('date_order'), 'date_order'),
        ('client_order_ref', 'client_order_ref'),
        ('note', 'note'),
        ('origin', 'origin'),
        ('payment_term', 'payment_term'),
    ]

    children = [('lines', 'odoo_order_line_ids', 'odoo.sale.order.line')]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def partner_id(self, record):
        binder = self.binder_for('odoo.res.partner')
        partner_id = binder.to_openerp(
            record['partner_id'][0], unwrap=True)
        return {'partner_id': partner_id,
                'partner_invoice_id': partner_id,
                'partner_shipping_id': partner_id}

    @mapping
    def user_id(self, record):
        binder = self.binder_for('odoo.res.users')
        user_id = binder.to_openerp(record['user_id'][0], unwrap=True)
        return {'user_id': user_id}


@odoo
class SaleOrderImporter(OdooImporter):
    _model_name = ['odoo.sale.order']

    _base_mapper = SaleOrderImportMapper

    def _must_skip(self):
        """ Hook called right after we read the data from the backend.

        If the method returns a message giving a reason for the
        skipping, the import will be interrupted and the message
        recorded in the job (if the import is called directly by the
        job, not by dependencies).

        If it returns None, the import will continue normally.

        :returns: None | str | unicode
        """
        if self.binder.to_openerp(self.odoo_id):
            return _('Already imported')

    def _before_import(self):
        rules = self.unit_for(SaleImportRule)
        rules.check(self.odoo_record)

    def _import_customer(self):
        record = self.odoo_record
        # we always update the customer when importing an order
        importer = self.unit_for(
            OdooImporter,
            model='odoo.res.partner')
        importer.run(record['partner_id'][0])

    def _import_sale_person(self):
        record = self.odoo_record
        # we always update the sale person when importing an order
        importer = self.unit_for(OdooImporter, model='odoo.res.users')
        importer.run(record['user_id'][0])

    def _import_dependencies(self):
        record = self.odoo_record

        self._import_customer()

        # import sale person for order
        self._import_sale_person()

        for line in record.get('lines', []):
            _logger.debug('line: %s', line)
            if 'product_id' in line:
                self._import_dependency(line['product_id'][0],
                                        'odoo.product.product')


@odoo
class SaleOrderLineImportMapper(ImportMapper):
    _model_name = 'odoo.sale.order.line'

    direct = [
        ('product_uos_qty', 'product_uos_qty'),
        ('price_unit', 'price_unit'),
        ('id', 'odoo_id'),
    ]

    @mapping
    def product_id(self, record):
        binder = self.binder_for('odoo.product.product')
        product_id = binder.to_openerp(record['product_id'][0], unwrap=True)
        assert product_id is not None, (
            "product_id %s should have been imported in "
            "SaleOrderImporter._import_dependencies" % record['product_id'][0])
        return {'product_id': product_id}

    @mapping
    def product_uom_qty(self, record):
        product_uom_qty = record.get('product_uom_qty')
        if not product_uom_qty:
            return {'product_uom_qty': 1}
        return {'product_uom_qty': product_uom_qty}

    @mapping
    def product_uom(self, record):
        binder = self.binder_for('odoo.product.product')
        binding_product_id = binder.to_openerp(
            record['product_id'][0], unwrap=False)
        product = binder.unwrap_binding(binding_product_id, browse=True)
        return {'product_uom': product.uom_id.id}
