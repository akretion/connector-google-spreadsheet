# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for Odoo
#   Copyright (C) 2015-TODAY Akretion (http://www.akretion.com).
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
{
    'name': 'Google Spreadsheet Import',
    'version': '0.1',
    'author': 'Akretion',
    'license': 'AGPL-3',
    'category': 'Connector',
    'description': '''
        This module allows to load Google Spreadsheets into Odoo.
        This module requires the following Python dependencies:

        pip install pyOpenSSL (>= 0.14)
        pip install oauth2client (>= 1.4.7)
        pip install gspread (>= 0.2.3
    ''',
    'depends': [
        'connector',
        'web_sheet_full_width_selective',
    ],
    'data': [
        'ir_exports_line_data.xml',
        'ir_cron_data.xml',
        'backend_view.xml',
        'security/ir.model.access.csv'
    ],
    'external_dependencies': {
        'python': ['OpenSSL', 'oauth2client', 'gspread'],
    },
    'installable': True,
    'application': False,
}
