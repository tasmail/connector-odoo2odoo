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

"""

Importers for extrnal Odoo.

An import can be skipped if the last sync date is more recent than
the last update in extrnal Odoo.

They should call the ``bind`` method if the binder even if the records
are already bound, to update the last sync date.

"""

import logging
from openerp import fields, _
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.connector import ConnectorUnit
from openerp.addons.connector.unit.synchronizer import Importer
from openerp.addons.connector.exception import IDMissingInBackend
from ..backend import odoo
from ..connector import get_environment, add_checkpoint
from ..related_action import link

_logger = logging.getLogger(__name__)


class OdooImporter(Importer):
    """ Base importer for extrnal Odoo """

    def __init__(self, connector_env):
        """
        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(OdooImporter, self).__init__(connector_env)
        self.odoo_id = None
        self.odoo_record = None

    def _get_odoo_data(self):
        """ Return the raw extrnal Odoo data for ``self.odoo_id`` """
        return self.backend_adapter.read(self.odoo_id)

    def _before_import(self):
        """ Hook called before the import, when we have the extrnal Odoo
        data"""

    def _is_uptodate(self, binding):
        """Return True if the import should be skipped because
        it is already up-to-date in OpenERP"""
        assert self.odoo_record
        if not self.odoo_record.get('write_date'):
            return  # no update date on Odoo, always import it.
        if not binding:
            return  # it does not exist so it should not be skipped
        sync = binding.sync_date
        if not sync:
            return
        from_string = fields.Datetime.from_string
        sync_date = from_string(sync)
        odoo_date = from_string(self.odoo_record['write_date'])
        return odoo_date < sync_date

    def _import_dependency(self, odoo_id, binding_model,
                           importer_class=None, always=False):
        """ Import a dependency.

        The importer class is a class or subclass of
        :class:`OdooImporter`. A specific class can be defined.

        :param odoo_id: id of the related binding to import
        :param binding_model: name of the binding model for the relation
        :type binding_model: str | unicode
        :param importer_cls: :class:`openerp.addons.connector.\
                                     connector.ConnectorUnit`
                             class or parent class to use for the export.
                             By default: OdooImporter
        :type importer_cls: :class:`openerp.addons.connector.\
                                    connector.MetaConnectorUnit`
        :param always: if True, the record is updated even if it already
                       exists, note that it is still skipped if it has
                       not been modified on extrnal Odoo since the last
                       update. When False, it will import it only when
                       it does not yet exist.
        :type always: boolean
        """
        if not odoo_id:
            return
        if importer_class is None:
            importer_class = OdooImporter
        binder = self.binder_for(binding_model)
        if always or binder.to_openerp(odoo_id) is None:
            importer = self.unit_for(importer_class, model=binding_model)
            importer.run(odoo_id)

    def _import_dependencies(self):
        """ Import the dependencies for the record

        Import of dependencies can be done manually or by calling
        :meth:`_import_dependency` for each dependency.
        """
        return

    def _map_data(self):
        """ Returns an instance of
        :py:class:`~openerp.addons.connector.unit.mapper.MapRecord`

        """
        return self.mapper.map_record(self.odoo_record)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``_create`` or
        ``_update`` if some fields are missing or invalid.

        Raise `InvalidDataError`
        """
        return

    def _must_skip(self):
        """ Hook called right after we read the data from the backend.

        If the method returns a message giving a reason for the
        skipping, the import will be interrupted and the message
        recorded in the job (if the import is called directly by the
        job, not by dependencies).

        If it returns None, the import will continue normally.

        :returns: None | str | unicode
        """
        return

    def _get_binding(self):
        return self.binder.to_openerp(self.odoo_id, browse=True)

    def _create_data(self, map_record, **kwargs):
        return map_record.values(for_create=True, **kwargs)

    def _create(self, data):
        """ Create the OpenERP record """
        # special check on data before import
        self._validate_data(data)
        model = self.model.with_context(connector_no_export=True)
        binding = model.create(data)
        _logger.debug('%d created from extrnal Odoo %s', binding, self.odoo_id)
        return binding

    def _update_data(self, map_record, **kwargs):
        return map_record.values(**kwargs)

    def _update(self, binding, data):
        """ Update an OpenERP record """
        # special check on data before import
        self._validate_data(data)
        binding.with_context(connector_no_export=True).write(data)
        _logger.debug('%d updated from extrnal odoo %s', binding, self.odoo_id)
        return

    def _after_import(self, binding):
        """ Hook called at the end of the import """
        return

    def run(self, odoo_id, force=False):
        """ Run the synchronization

        :param odoo_id: identifier of the record on extrnal Odoo
        """
        self.odoo_id = odoo_id
        try:
            self.odoo_record = self._get_odoo_data()
        except IDMissingInBackend:
            return _('Record does no longer exist in extrnal Odoo')

        skip = self._must_skip()
        if skip:
            return skip

        binding = self._get_binding()

        if not force and self._is_uptodate(binding):
            return _('Already up-to-date.')
        self._before_import()

        # import the missing linked resources
        self._import_dependencies()

        map_record = self._map_data()

        if binding:
            record = self._update_data(map_record)
            self._update(binding, record)
        else:
            record = self._create_data(map_record)
            binding = self._create(record)

        self.binder.bind(self.odoo_id, binding)

        self._after_import(binding)


class BatchImporter(Importer):
    """ The role of a BatchImporter is to search for a list of
    items to import, then it can either import them directly or delay
    the import of each item separately.
    """

    def run(self, filters=None):
        """ Run the synchronization """
        record_ids = self.backend_adapter.search(filters)
        for record_id in record_ids:
            self._import_record(record_id)

    def _import_record(self, record_id):
        """ Import a record directly or delay the import of the record.

        Method to implement in sub-classes.
        """
        raise NotImplementedError


class DirectBatchImporter(BatchImporter):
    """ Import the records directly, without delaying the jobs. """
    _model_name = None

    def _import_record(self, record_id):
        """ Import the record directly """
        import_record(self.session,
                      self.model._name,
                      self.backend_record.id,
                      record_id)


class DelayedBatchImporter(BatchImporter):
    """ Delay import of the records """
    _model_name = None

    def _import_record(self, record_id, **kwargs):
        """ Delay the import of the records"""
        import_record.delay(self.session,
                            self.model._name,
                            self.backend_record.id,
                            record_id,
                            **kwargs)


@odoo
class SimpleRecordImporter(OdooImporter):
    """ Import one external Odoo """
    _model_name = [
        'odoo.res.partner.category',
        'odoo.product.uom.categ',
    ]


@odoo
class AddCheckpoint(ConnectorUnit):
    """ Add a connector.checkpoint on the underlying model
    (not the odoo.* but the _inherits'ed model) """

    _model_name = ['odoo.product.product',
                   'odoo.product.category',
                   ]

    def run(self, openerp_binding_id):
        binding = self.model.browse(openerp_binding_id)
        record = binding.openerp_id
        add_checkpoint(self.session,
                       record._model._name,
                       record.id,
                       self.backend_record.id)


@job(default_channel='root.odoo')
def import_batch(session, model_name, backend_id, filters=None):
    """ Prepare a batch import of records from extrnal Odoo """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(BatchImporter)
    importer.run(filters=filters)


@job(default_channel='root.odoo')
@related_action(action=link)
def import_record(session, model_name, backend_id, odoo_id, force=False):
    """ Import a record from external Odoo """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(OdooImporter)
    importer.run(odoo_id, force=force)
