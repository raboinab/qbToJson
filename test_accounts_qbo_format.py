#!/usr/bin/env python3
"""
Regression test: QBO chart-of-accounts CSV/XLSX export.

QuickBooks Online exports the chart of accounts with headers
'Account number, Account name, Account type, Detail type' (lowercase 't' in
'type'), which differs from the QB desktop Account List ('Full name'/'Type').
The parser previously only recognized the latter, so every QBO row was skipped
and 0 accounts were produced (observed on project 621a6c9f VampireFreaks.csv).
"""
import csv
import tempfile
from pathlib import Path

import openpyxl

from accountsConverter import AccountsConverter

ROWS = [
    ['Account number', 'Account name', 'Account type', 'Detail type'],
    ['1000', 'Suspense', 'Bank', 'Checking'],
    ['1015', 'Wells Fargo Business Checking - 7179', 'Bank', 'Checking'],
    ['1075', 'Sezzle Accounts', 'Bank', 'Checking'],
    ['', 'Sezzle Accounts:Sezzle Interest Account - CAD', 'Bank', 'Checking'],
    ['2000', 'Accounts Payable (A/P)', 'Accounts payable (A/P)', 'Accounts Payable (A/P)'],
    ['4000', 'Sales', 'Income', 'Sales of Product Income'],
    ['6000', 'Advertising', 'Expenses', 'Advertising/Promotional'],
    # report decoration with no type -> must be skipped
    ['', 'TOTAL', '', ''],
]


def _write_csv():
    tmp = tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w', newline='')
    csv.writer(tmp).writerows(ROWS)
    tmp.close()
    return Path(tmp.name)


def _write_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in ROWS:
        ws.append(r)
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    wb.save(tmp.name)
    return Path(tmp.name)


def _assert_accounts(accounts, label):
    # 7 real accounts; the TOTAL decoration row is skipped
    assert len(accounts) == 7, f"[{label}] expected 7 accounts, got {len(accounts)}"

    by_name = {a['name']: a for a in accounts}
    # account number captured
    assert by_name['Suspense']['acctNum'] == '1000', f"[{label}] acctNum not captured"
    assert by_name['Suspense']['accountType'] == 'BANK', f"[{label}] type misclassified"
    # sub-account detected with a resolved parent reference
    sub = next(a for a in accounts if a['subAccount'])
    assert 'Sezzle Interest Account - CAD' in sub['name'], f"[{label}] wrong sub-account leaf"
    assert sub['parentRef'] and sub['parentRef']['value'], f"[{label}] sub-account parent not linked"
    print(f"OK: QBO chart-of-accounts {label} parses {len(accounts)} accounts")


def test_qbo_csv():
    conv = AccountsConverter()
    _assert_accounts(conv.convert_file(str(_write_csv())), 'CSV')


def test_qbo_xlsx():
    conv = AccountsConverter()
    _assert_accounts(conv.convert_file(str(_write_xlsx())), 'XLSX')


if __name__ == '__main__':
    test_qbo_csv()
    test_qbo_xlsx()
    print("\nAll QBO chart-of-accounts regression tests passed.")
