#!/usr/bin/env python3
"""
Regression tests for General Ledger parsing of QuickBooks exports that include a
leading 'Distribution account' column (which shifts every data column by one),
plus header date formats that lack explicit day numbers.

Reproduces the Milano Hospitality GL failures:
  - HTTP 500 on a GL whose header was "January-December, 2025" (month range, no days)
  - Silent column misalignment when a 'Distribution account' column is present
    (date/amount/balance were read from the wrong columns)
"""
import tempfile
from pathlib import Path

import openpyxl

from generalLedgerConverter import GeneralLedgerConverter


# Layout WITH a leading 'Distribution account' column (Milano 2024/2025/2023 layout)
HEADER_WITH_DIST = ['', 'Distribution account', 'Transaction date', 'Transaction type',
                    'Num', 'Name', 'Memo/Description', 'Split account', 'Amount', 'Balance']
# Layout WITHOUT the distribution account column (Milano 26YTD layout)
HEADER_NO_DIST = ['', 'Transaction date', 'Transaction type', 'Num', 'Name',
                  'Description', 'Split', 'Amount', 'Balance']


def _write_xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    wb.save(tmp.name)
    return Path(tmp.name)


def _first_account(result):
    rows = result.get('rows', {}).get('row', [])
    for r in rows:
        if r.get('type') == 'SECTION':
            return r
    return None


def test_with_distribution_account_column():
    """date/amount/balance must come from the correct (shifted) columns."""
    rows = [
        ['General Ledger'],
        ['Acme LLC'],
        ['January 1-December 31, 2024'],
        [],
        HEADER_WITH_DIST,
        ['1020 Checking'],
        ['', 'Beginning Balance', '', '', '', '', '', '', '', '1000.00'],
        ['', '1020 Checking', '01/15/2024', 'Expense', '', 'Vendor A',
         'memo text', 'Rent', '-500.00', '500.00'],
        ['', '1020 Checking', '02/20/2024', 'Deposit', '', 'Customer B',
         '', 'Sales', '750.00', '1250.00'],
        ['Total for 1020 Checking', '', '', '', '', '', '', '', '250.00', ''],
    ]
    path = _write_xlsx(rows)
    conv = GeneralLedgerConverter()
    raw = conv.parse_xlsx(path)

    acct = raw['accounts']['1020 Checking']
    txns = acct['transactions']

    # Opening balance must be preserved as a Beginning Balance row
    bb = [t for t in txns if t['type'] == 'Beginning Balance']
    assert len(bb) == 1, f"expected 1 Beginning Balance row, got {len(bb)}"
    assert bb[0]['balance'] == '1000.00', f"beginning balance misread: {bb[0]['balance']!r}"

    # 2 real transactions
    real = [t for t in txns if t['type'] in ('Expense', 'Deposit')]
    assert len(real) == 2, f"expected 2 real txns, got {len(real)}: {real}"

    t0 = real[0]
    assert t0['date'] == '01/15/2024', f"date misread: {t0['date']!r}"
    assert t0['type'] == 'Expense', f"type misread: {t0['type']!r}"
    assert t0['amount'] == '-500.00', f"amount misread: {t0['amount']!r}"
    assert t0['balance'] == '500.00', f"balance misread: {t0['balance']!r}"
    assert t0['split_account'] == 'Rent', f"split misread: {t0['split_account']!r}"

    # Transaction date range must now be recoverable (was the root of the 500)
    rng = conv.extract_transaction_date_range(raw['accounts'])
    assert rng[0] is not None and rng[1] is not None, f"no tx dates found: {rng}"

    # Total for the account picks up the amount column
    assert acct['total'] == '250.00', f"total misread: {acct['total']!r}"
    print("OK: with-distribution-account layout parses correct columns")


def test_without_distribution_account_column():
    """The legacy layout (no dist column) must still parse correctly."""
    rows = [
        ['Acme LLC'],
        ['General Ledger'],
        ['January 1-May 31, 2026'],
        [],
        HEADER_NO_DIST,
        ['1020 Checking'],
        ['', '01/10/2026', 'Expense', '', 'Vendor A', 'memo', 'Rent', '-300.00', '700.00'],
        ['Total for 1020 Checking', '', '', '', '', '', '', '-300.00', ''],
    ]
    path = _write_xlsx(rows)
    conv = GeneralLedgerConverter()
    raw = conv.parse_xlsx(path)

    acct = raw['accounts']['1020 Checking']
    t0 = acct['transactions'][0]
    assert t0['date'] == '01/10/2026', f"date misread: {t0['date']!r}"
    assert t0['amount'] == '-300.00', f"amount misread: {t0['amount']!r}"
    assert t0['balance'] == '700.00', f"balance misread: {t0['balance']!r}"
    assert acct['total'] == '-300.00', f"total misread: {acct['total']!r}"
    print("OK: no-distribution-account layout still parses correctly")


def test_header_date_patterns():
    conv = GeneralLedgerConverter()
    cases = {
        "January-December, 2025": ("2025-01-01", "2025-12-31"),
        "January - December 2025": ("2025-01-01", "2025-12-31"),
        "Jan-Dec 2025": ("2025-01-01", "2025-12-31"),
        "2025-01-01 - 2025-12-31": ("2025-01-01", "2025-12-31"),
        "10/1/2024 through 9/30/2025": ("2024-10-01", "2025-09-30"),
        # existing formats must still work
        "January 1-December 31, 2024": ("2024-01-01", "2024-12-31"),
        "August 13-December 31, 2023": ("2023-08-13", "2023-12-31"),
    }
    for header, (exp_start, exp_end) in cases.items():
        parsed = conv.parse_date_range(header)
        assert parsed is not None, f"FAILED to parse header: {header!r}"
        _, start, end = parsed
        assert start.strftime('%Y-%m-%d') == exp_start, f"{header!r} start {start} != {exp_start}"
        assert end.strftime('%Y-%m-%d') == exp_end, f"{header!r} end {end} != {exp_end}"
    print("OK: header date patterns parse correctly")


if __name__ == '__main__':
    test_with_distribution_account_column()
    test_without_distribution_account_column()
    test_header_date_patterns()
    print("\nAll GL column-mapping regression tests passed.")
