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
import xmlrpclib
import erppeek
from openerp.addons.connector.unit.backend_adapter import CRUDAdapter
from openerp.addons.connector.exception import (NetworkRetryableError,
                                                RetryableJobError)
from datetime import datetime
import logging
import socket
_logger = logging.getLogger(__name__)


class OdooLocation(object):

    def __init__(self, location, database, username, password):
        self._location = location
        self.database = database
        self.username = username
        self.password = password

    @property
    def location(self):
        location = self._location
        return location


class OdooCRUDAdapter(CRUDAdapter):
    """ External Records Adapter for Odoo """

    def __init__(self, connector_env):
        """

        :param connector_env: current environment (backend, session, ...)
        :type connector_env: :class:`connector.connector.ConnectorEnvironment`
        """
        super(OdooCRUDAdapter, self).__init__(connector_env)
        backend = self.backend_record
        odoo = OdooLocation(
            backend.location,
            backend.database,
            backend.username,
            backend.password,
        )
        self.odoo = odoo

    def search(self, domain, **kwargs):
        """ Search records according to some criterias
        and returns a list of ids """
        raise NotImplementedError

    def read(self, domain, **kwargs):
        """ Returns the information of a record """
        raise NotImplementedError

    def search_read(self, domain=None, fields=None):
        """ Search records according to some criterias
        and returns their information"""
        raise NotImplementedError

    def create(self, values, **kwargs):
        """ Create a record on the external system """
        raise NotImplementedError

    def write(self, ids, values, **kwargs):
        """ Update records on the external system """
        raise NotImplementedError

    def delete(self, ids, **kwargs):
        """ Delete a record on the external system """
        raise NotImplementedError

    def _call(self, model_name, method, *args, **kwargs):
        try:
            _logger.debug("Start calling Odoo api %s", method)
            client = erppeek.Client(
                self.odoo.location, self.odoo.database,
                self.odoo.username, self.odoo.password)
            start = datetime.now()
            try:
                result = client.execute(
                    model_name,
                    method,
                    *args,
                    **kwargs
                )
            except:
                _logger.error(
                    "api.execute(%s, %s) failed", method, args)
                raise
            else:
                _logger.debug(
                    "api.execute(%s, %s) returned %s in %s seconds",
                    method, args, result,
                    (datetime.now() - start).seconds)
            return result
        except (socket.gaierror, socket.error, socket.timeout) as err:
            raise NetworkRetryableError(
                'A network error caused the failure of the job: '
                '%s' % err)
        except xmlrpclib.ProtocolError as err:
            if err.errcode in [502,   # Bad gateway
                               503,   # Service unavailable
                               504]:  # Gateway timeout
                raise RetryableJobError(
                    'A protocol error caused the failure of the job:\n'
                    'URL: %s\n'
                    'HTTP/HTTPS headers: %s\n'
                    'Error code: %d\n'
                    'Error message: %s\n' %
                    (err.url, err.headers, err.errcode, err.errmsg))
            else:
                raise


class GenericAdapter(OdooCRUDAdapter):

    _model_name = None
    _odoo_model = None

    def search(self, domain=None, **kwargs):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        return self._call(
            self._odoo_model,
            'search',
            [domain] if domain else [],
            **kwargs)

    def read(self, ids, **kwargs):
        """ Returns the information of a record

        :rtype: dict
        """
        return self._call(
            self._odoo_model,
            'read',
            ids,
            **kwargs)

    def search_read(self, filters=None):
        """ Search records according to some criterias
        and returns their information"""
        return self._call(
            self._odoo_model,
            'search_read', [filters])

    def create(self, values, **kwargs):
        """ Create a record on the external system """
        return self._call(
            self._odoo_model,
            'create',
            values,
            **kwargs)

    def write(self, ids, values, **kwargs):
        """ Update records on the external system """
        return self._call(
            self._odoo_model,
            'write',
            ids,
            values,
            **kwargs)

    def delete(self, ids, **kwargs):
        """ Delete a record on the external system """
        return self._call(
            self._odoo_model,
            'unlink',
            ids,
            **kwargs)
