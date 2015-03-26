# connector-google-spreadsheet

This module allows the importation of Google Spreadsheet into Odoo.

Important notes:
================
- The header row is mandatory, and use the same syntax as
  native Odoo CSV importation tool.
- In order to upload importation errors into Google Spreadsheet
  you must title the *first* column of your Google sheet: "ERRORS".
- In order to determine the rows to import the program check the length
  of the first column of data. In other words if the first column of
  *data* (not the "ERRORS" column) is empty the corresponding record
  is not imported.
- Empty columns (with even the header cell empty) are ignored.
- Unknown model's columns are also ignored.

Dependencies:
=============

This module requires the following Python dependencies:

    pip install pyOpenSSL
    pip install oauth2client
    pip install gspread

Authors:
========
- Copyright (C) 2015-TODAY Akretion (http://www.akretion.com).
- Sylvain Calador <sylvain.calador@akretion.com>

License:
========
AGPL-V3

(Work in progress)
