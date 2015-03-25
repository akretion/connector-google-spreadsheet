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

import logging

import gspread
import base64
from oauth2client.client import SignedJwtAssertionCredentials
from openerp import models, fields, api
from openerp.addons.connector.session import ConnectorSession
from openerp.addons.connector.queue.job import job, related_action

SEPARATOR = ';'
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

    def _prepare_import_args(self, fields, line_start, line_end, col_end):
        return {
            'document_url': self.document_url,
            'document_sheet': self.document_sheet,
            'fields': fields,
            'chunk_line_start': line_start,
            'chunk_line_end': line_end,
            'sheet_col_end': col_end,
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
        # first column data cells (without header)
        first_column_cells = sheet.col_values(1)[1:]
        chunk_size = 0
        line_start = 2
        line_end = line_start
        first_row = sheet.row_values(1)
        import_fields = first_row
        col_end = len(first_row)
        eof = len(first_column_cells) + 1
        for cell in first_column_cells:
            chunk_size = line_end - line_start
            if chunk_size >= self.chunk_size or line_end >= eof:
                import_args = self._prepare_import_args(
                    import_fields, line_start, line_end, col_end
                )
                import_document.delay(session, self._name, import_args)
                line_end += 1
                line_start = line_end
            else:
                line_end += 1

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
    line_start = args['chunk_line_start']
    line_end = args['chunk_line_end']
    col_end = args['sheet_col_end']
    fields = args['fields']
    model_obj = session.pool[args['odoo_model']]

    backend = session.browse('google.spreadsheet.backend', backend_id)
    document = open_document(backend, document_url)
    sheet = document.worksheet(document_sheet)

    start = sheet.get_addr_int(line_start, 1)
    stop = sheet.get_addr_int(line_end, col_end)
    chunk = sheet.range(start + ':' + stop)
    data = []
    row = [''] * col_end
    current_row = 2
    for cell in chunk:
        if cell.row != current_row:
            data.append(row)
            row = [''] * col_end
        row[cell.col - 1] = cell.value
        current_row = cell.row

    result = model_obj.load(session.cr,
                            session.uid,
                            fields,
                            data,
                            context=session.context)
    return result
