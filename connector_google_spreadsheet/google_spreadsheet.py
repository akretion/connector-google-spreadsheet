# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for Odoo
#   Copyright (C) 2015 Akretion (http://www.akretion.com).
#   @author Sylvain Calador <sylvain.calador@akretion.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import re
import logging

import gspread
import base64
from oauth2client.client import SignedJwtAssertionCredentials
from openerp import models, fields, api
from openerp.exceptions import Warning
from openerp.tools.translate import _
from openerp.addons.connector.session import ConnectorSession
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.exception import FailedJobError

SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://docs.google.com/feeds']

_logger = logging.getLogger(__name__)


def open_document(backend, document_url):

    # Auhentification
    private_key = base64.b64decode(backend.p12_key)
    credentials = SignedJwtAssertionCredentials(
        backend.email, private_key, SCOPE)
    gc = gspread.authorize(credentials)

    document = gc.open_by_url(document_url)
    return document


class GoogleSpreadsheetDocument(models.Model):
    _name = 'google.spreadsheet.document'
    _description = 'Google Spreadsheet Document'

    name = fields.Char('Name', size=255, required=True)
    model_id = fields.Many2one('ir.model', string='Odoo Model', required=True)
    document_url = fields.Char('Documen URL', size=255, required=True)
    document_sheet = fields.Char(
        'Document sheet name', size=255, required=True)
    submission_date = fields.Datetime('Submission date')
    chunk_size = fields.Integer('Chunk size', default=100)
    active = fields.Boolean('Active')
    backend_id = fields.Many2one(
        'google.spreadsheet.backend',
        string='Google Spreadsheet Backend'
    )

    def _prepare_import_args(
            self, fields, row_start, row_end, col_start, col_end, error_col):
        return {
            'document_url': self.document_url,
            'document_sheet': self.document_sheet,
            'fields': fields,
            'chunk_row_start': row_start,
            'chunk_row_end': row_end,
            'sheet_col_start': col_start,
            'sheet_col_end': col_end,
            'error_col': error_col,
            'odoo_model': self.model_id.model,
            'backend_id': self.backend_id.id,
        }

    @api.one
    def run(self):
        session = ConnectorSession(
            self.env.cr,
            self.env.uid,
            self.env.context,
        )
        backend = self.backend_id
        document = open_document(backend, self.document_url)
        sheet = document.worksheet(self.document_sheet)

        row_start = 2
        row_end = row_start

        first_row = sheet.row_values(1)
        if first_row[0] == 'ERRORS':
            col_start = 2
            import_fields = first_row[1:]
            error_col = 1

        else:
            col_start = 1
            import_fields = first_row
            error_col = None

        # first column data cells (without header)
        first_column_cells = sheet.col_values(col_start)[1:]
        if not first_column_cells:
            message = _('Nothing to import,'
                        'the first column of data seams empty!')
            raise Warning(message)

        col_end = len(first_row)
        eof = len(first_column_cells) + 1

        for cell in first_column_cells:
            chunk_size = row_end - row_start
            if chunk_size >= self.chunk_size or row_end >= eof:
                import_args = self._prepare_import_args(
                    import_fields,
                    row_start,
                    row_end,
                    col_start,
                    col_end,
                    error_col
                )
                import_document.delay(session, self._name, import_args)
                row_end += 1
                row_start = row_end
            else:
                row_end += 1

        self.submission_date = fields.Datetime.now()


class GoogleSpreadsheetBackend(models.Model):
    _name = 'google.spreadsheet.backend'
    _description = 'Google Spreadsheet Backend'

    _inherit = 'connector.backend'

    _backend_type = 'google.spreadsheet'

    name = fields.Char('Name', size=80)
    email = fields.Char('Google Email')
    p12_key = fields.Binary('Google P12 key')
    version = fields.Selection(selection=[('3.0', 'Version 3')])
    document_ids = fields.One2many(
        'google.spreadsheet.document',
        'backend_id', string='Google spreadsheet documents',
    )


def open_document_url(session, job):
    url = job.args[1]['document_url']
    action = {
        'type': 'ir.actions.act_url',
        'target': 'new',
        'url': url,
    }
    return action


@job
@related_action(action=open_document_url)
def import_document(session, model_name, args):

    backend_id = args['backend_id']
    document_url = args['document_url']
    document_sheet = args['document_sheet']
    fields = args['fields']
    row_start = args['chunk_row_start']
    row_end = args['chunk_row_end']
    col_start = args['sheet_col_start']
    col_end = args['sheet_col_end']
    error_col = args['error_col']
    model_obj = session.pool[args['odoo_model']]

    backend = session.browse('google.spreadsheet.backend', backend_id)
    document = open_document(backend, document_url)
    sheet = document.worksheet(document_sheet)

    start = sheet.get_addr_int(row_start, col_start)
    stop = sheet.get_addr_int(row_end, col_end)
    chunk = sheet.range(start + ':' + stop)

    cols = col_end - col_start + 1
    rows = row_end - row_start + 1
    data = [['' for c in range(cols)] for r in range(rows)]
    for cell in chunk:
        data[cell.row - 2][cell.col - col_start] = cell.value

    # skip all non-model fields
    special_fields = ['.id', 'id']

    model_field_names = [k for k, v in model_obj._all_columns.iteritems()]
    model_field_names.extend(special_fields)

    field_names = []
    for field in fields:
        if field and field not in special_fields:
            field = re.sub('^(\w*).*', '\\1', field)
        field_names.append(field)

    skip_fields = list(set(field_names) - set(model_field_names))
    skip_indexes = [i for i, f in enumerate(fields) if f in skip_fields]

    for index in sorted(skip_indexes, reverse=True):
        del fields[index]
        for row in data:
            del row[index]

    # import the chunk of clean data
    result = model_obj.load(session.cr,
                            session.uid,
                            fields,
                            data,
                            context=session.context)

    # clear previous errors
    if error_col is not None:
        start = sheet.get_addr_int(row_start, error_col)
        stop = sheet.get_addr_int(row_end, error_col)
        error_cells = sheet.range(start + ':' + stop)
        for cell in error_cells:
            cell.value = ''
        sheet.update_cells(error_cells)

    # log errors
    errors = False
    messages = []
    for m in result['messages']:
        row = row_start + m['record']
        message = m['message']
        message_type = m['type']
        messages.append('%s:line %i: %s' % (message_type, row, message))
        if message_type == 'error':
            errors = True
            if error_col is not None:
                error_cell = sheet.get_addr_int(row, error_col)
                sheet.update_acell(error_cell, message)

    if errors:
        raise FailedJobError(messages)
    else:
        imported_ids = ', '.join([str(id_) for id_ in result['ids']])
        messages.append('Imported/Updated ids: %s' % imported_ids)

    return '\n'.join(messages)
