# QuickBooks Document Converters

A comprehensive suite of Python converters that transform various financial document formats (CSV, XLSX, PDF) into standardized JSON formats compatible with QuickBooks Online.

## Features

- **Multiple Format Support**: Converts CSV, XLSX, and PDF files
- **Eleven Document Types Supported**:
  - Chart of Accounts
  - Balance Sheet (monthly)
  - Profit & Loss (monthly)
  - Trial Balance (monthly with debit/credit columns)
  - Cash Flow Statement (monthly)
  - General Ledger (transaction-level detail)
  - Journal Entries (transaction-level detail)
  - Accounts Payable Aging Summary
  - Accounts Receivable Aging Summary
  - Vendor Concentration (Expenses by Vendor)
  - Customer Concentration (Sales by Customer)
- **Database Integration**: Automatic saving to Supabase database
- **Dual Workflows**: Direct upload OR process from Supabase Storage
- **22 REST API Endpoints**: 11 direct upload + 11 storage-based
- **Account ID Lookup**: Automatically uses account IDs from Chart of Accounts for consistency
- **Flexible Parsing**: Handles various report layouts and formats
- **Error Handling**: Comprehensive error messages and validation
- **Container-Optimized**: In-memory processing for cloud deployments

## Installation
## Installation

1. Ensure you have Python 3.6 or higher installed
2. Clone or download this repository
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. **(Optional)** Configure database integration:

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your credentials
QBTOJSON_API_KEY=your-api-key-here
DB_PROXY_URL=https://your-project.supabase.co/functions/v1/db-proxy
```

Generate an API key:
```bash
openssl rand -base64 32
```

## Converters

### 1. Chart of Accounts Converter (`accountsConverter.py`)

Converts account lists into QuickBooks JSON format.

```bash
# Convert and print to stdout
python accountsConverter.py "sampleReports/Sandbox Company_US_9_Account List.csv"

# Convert and save to file
python accountsConverter.py "sampleReports/Sandbox Company_US_9_Account List.csv" -o accounts.json
```

### 2. Balance Sheet Converter (`balanceSheetConverter.py`)

Converts monthly balance sheet reports with hierarchical asset/liability structure.

```bash
python balanceSheetConverter.py "sampleReports/Sandbox Company_US_1_Balance Sheet.csv" -o balance_sheet.json
```

### 3. Profit & Loss Converter (`profitLossConverter.py`)

Converts monthly P&L reports with income and expense sections.

```bash
python profitLossConverter.py "sampleReports/Sandbox Company_US_1_Profit and Loss by Month.csv" -o profit_loss.json
```

### 4. Trial Balance Converter (`trialBalanceConverter.py`)

Converts monthly trial balance reports with debit and credit columns.

```bash
python trialBalanceConverter.py "sampleReports/TrialBalance.pdf" -o trial_balance.json
```

### 5. Cash Flow Statement Converter (`cashFlowConverter.py`)

Converts monthly cash flow statements with operating, investing, and financing activities.

```bash
python cashFlowConverter.py "sampleReports/Sandbox Company_US_1_Statement of Cash Flows_many_months.csv" -o cash_flow.json
```

### 6. General Ledger Converter (`generalLedgerConverter.py`)

Converts general ledger reports with transaction-level detail organized by account.

```bash
python generalLedgerConverter.py "sampleReports/Sandbox Company_US_1_General Ledger.csv" -o general_ledger.json
```

### 7. Journal Entries Converter (`journalEntriesConverter.py`)

Converts journal entry reports with transaction-level detail including debits and credits.

```bash
python journalEntriesConverter.py "sampleReports/Sandbox Company_US_1_Journal.csv" -o journal_entries.json
```

### 8. Accounts Payable Aging Converter (`accountsPayableConverter.py`)

Converts A/P aging summary reports showing vendor balances by aging bucket.

```bash
python accountsPayableConverter.py "sampleReports/Sandbox Company_US_1_A_P Aging Summary Report.csv" -o ap_aging.json
```

### 9. Accounts Receivable Aging Converter (`accountsReceivableConverter.py`)

Converts A/R aging summary reports showing customer balances by aging bucket. Handles hierarchical customer relationships.

```bash
python accountsReceivableConverter.py "sampleReports/Sandbox Company_US_1_A_R Aging Summary Report.csv" -o ar_aging.json
```

### 10. Vendor Concentration Converter (`vendorConcentrationConverter.py`)

Converts Expenses by Vendor Summary reports into a simple array format with percentage calculations.

```bash
python vendorConcentrationConverter.py "sampleReports/Sandbox Company_US_1_Expenses by Vendor Summary.csv" -o vendor_concentration.json
```

### 11. Customer Concentration Converter (`customerConcentrationConverter.py`)

Converts Sales by Customer Summary reports into a simple array format with percentage calculations. Consolidates hierarchical customer data.

```bash
python customerConcentrationConverter.py "sampleReports/Sandbox Company_US_1_Sales by Customer Summary.csv" -o customer_concentration.json
```

## Database Integration

### Overview

The service can automatically save conversion results to a Supabase database via the `db-proxy` Edge Function. This enables:

- ✅ Persistent storage of all converted financial data
- ✅ Two flexible workflows: direct upload or storage-based processing
- ✅ Audit trail with source document tracking
- ✅ Project-based organization
- ✅ Container-optimized in-memory processing

### Setup

1. **Generate an API key** for secure communication:
```bash
openssl rand -base64 32
```

2. **Add to your `.env` file**:
```bash
QBTOJSON_API_KEY=your-generated-key-here
DB_PROXY_URL=https://your-project.supabase.co/functions/v1/db-proxy
```

3. **Configure in Supabase** (add the same key to your Supabase project):
```bash
cd your-supabase-project
supabase secrets set QBTOJSON_API_KEY="your-generated-key-here"
```

### Database Tables

#### `processed_data` Table
Stores all converted QuickBooks data:

```sql
- id (uuid) - Primary key
- project_id (uuid) - Links to your project
- source_document_id (uuid) - Optional link to source file
- source_type (text) - Always 'qbtojson'
- data_type (text) - Document type (e.g., 'trial_balance', 'balance_sheet')
- data (jsonb) - Full converted JSON
- record_count (integer) - Number of records/accounts
- period_start (date) - Optional start date
- period_end (date) - Optional end date
- created_at (timestamp) - When processed
```

#### `documents` Table
Tracks uploaded files (if using storage-based workflow):

```sql
- id (uuid) - Document ID
- project_id (uuid) - Project reference
- file_name (text) - Original filename
- file_path (text) - Storage path
- processing_status (text) - 'pending', 'processing', 'completed', 'failed'
- created_at (timestamp) - Upload time
```

### Two Workflows

#### Workflow A: Direct Upload (with Optional DB Save)

Upload files directly to the API. Optionally save results to database.

**Without Database Save:**
```bash
curl -X POST http://localhost:5000/api/convert/trial-balance \
  -F "file=@trial_balance.xlsx"
```

**With Database Save:**
```bash
curl -X POST http://localhost:5000/api/convert/trial-balance \
  -F "file=@trial_balance.xlsx" \
  -F "save_to_db=true" \
  -F "project_id=your-project-uuid" \
  -F "source_document_id=optional-doc-uuid"
```

**Use when:**
- Testing conversions
- One-off file processing
- Don't need persistent storage
- Want immediate JSON response

#### Workflow B: From Supabase Storage (Auto-Saves)

Process files already in Supabase Storage. Always saves to database.

```bash
curl -X POST http://localhost:5000/api/convert-from-storage/trial-balance \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "project-123/trial_balance.xlsx",
    "project_id": "project-uuid",
    "source_document_id": "document-uuid"
  }'
```

**Use when:**
- Files uploaded via your web app
- Building automated pipelines
- Need audit trail
- Want database persistence
- Processing large batches

**Benefits:**
- ✅ In-memory processing (faster, no disk I/O)
- ✅ Container-friendly
- ✅ Results automatically saved
- ✅ Full source tracking

## REST API

The `api_server.py` provides **22 HTTP endpoints** for all converters.

### Starting the Server

```bash
python api_server.py
```

The server will start on `http://localhost:5000` (or port specified by PORT environment variable).

### Health Check

```bash
curl http://localhost:5000/health
```

Returns:
```json
{
  "status": "healthy",
  "service": "Document Converter API",
  "db_configured": true,
  "endpoints": {
    "direct_upload": { /* 11 endpoints */ },
    "from_storage": { /* 11 endpoints */ },
    "batch": { /* 6 endpoints */ }
  }
}
```

### Direct Upload Endpoints

Upload files directly via multipart/form-data. Optionally save to database.

#### Chart of Accounts
```bash
# Basic conversion
curl -X POST -F "file=@AccountList.csv" \
  http://localhost:5000/api/convert/accounts

# With database save
curl -X POST -F "file=@AccountList.csv" \
  -F "save_to_db=true" \
  -F "project_id=your-project-uuid" \
  http://localhost:5000/api/convert/accounts
```

#### Balance Sheet
```bash
curl -X POST -F "file=@BalanceSheet.xlsx" \
  http://localhost:5000/api/convert/balance-sheet
```

#### Profit & Loss
```bash
curl -X POST -F "file=@ProfitLoss.csv" \
  http://localhost:5000/api/convert/profit-loss
```

#### Trial Balance
```bash
curl -X POST -F "file=@TrialBalance.pdf" \
  http://localhost:5000/api/convert/trial-balance
```

#### Cash Flow Statement
```bash
curl -X POST -F "file=@CashFlow.csv" \
  http://localhost:5000/api/convert/cash-flow
```

#### General Ledger
```bash
curl -X POST -F "file=@GeneralLedger.xlsx" \
  http://localhost:5000/api/convert/general-ledger
```

#### Journal Entries
```bash
curl -X POST -F "file=@JournalEntries.csv" \
  http://localhost:5000/api/convert/journal-entries
```

#### Accounts Payable Aging
```bash
curl -X POST -F "file=@AP_Aging.xlsx" \
  http://localhost:5000/api/convert/accounts-payable
```

#### Accounts Receivable Aging
```bash
curl -X POST -F "file=@AR_Aging.csv" \
  http://localhost:5000/api/convert/accounts-receivable
```

#### Customer Concentration
```bash
curl -X POST -F "file=@CustomerConcentration.xlsx" \
  http://localhost:5000/api/convert/customer-concentration
```

#### Vendor Concentration
```bash
curl -X POST -F "file=@VendorConcentration.csv" \
  http://localhost:5000/api/convert/vendor-concentration
```

### Storage-Based Endpoints

Process files from Supabase Storage. Always saves results to database.

All storage-based endpoints follow the same pattern:

```bash
curl -X POST http://localhost:5000/api/convert-from-storage/{document-type} \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "project-id/filename.xlsx",
    "project_id": "project-uuid",
    "source_document_id": "document-uuid"
  }'
```

Available endpoints:
- `/api/convert-from-storage/accounts`
- `/api/convert-from-storage/balance-sheet`
- `/api/convert-from-storage/profit-loss`
- `/api/convert-from-storage/trial-balance`
- `/api/convert-from-storage/cash-flow`
- `/api/convert-from-storage/general-ledger`
- `/api/convert-from-storage/journal-entries`
- `/api/convert-from-storage/accounts-payable`
- `/api/convert-from-storage/accounts-receivable`
- `/api/convert-from-storage/customer-concentration`
- `/api/convert-from-storage/vendor-concentration`

**Response includes:**
```json
{
  "success": true,
  "data": { /* converted data */ },
  "file_path": "project-123/trial_balance.xlsx",
  "saved_to_db": true,
  "project_id": "project-uuid"
}
```

### Helper Endpoints

#### Load Chart of Accounts (for ID lookups)
```bash
curl -X POST -F "file=@AccountList.csv" \
  http://localhost:5000/api/accounts/load
```

#### Look up Account ID
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"name": "Sales"}' \
  http://localhost:5000/api/accounts/lookup
```

### API Information
```bash
curl http://localhost:5000/api/info
```

Returns full API documentation with examples.

## Account ID Consistency

For best results, follow this workflow:

1. **First**, load or convert your Chart of Accounts
2. **Then**, convert Balance Sheet, P&L, Trial Balance, and Cash Flow reports

The converters will automatically look up account IDs from the Chart of Accounts, ensuring consistency across all reports.

## Input Format Requirements

### Chart of Accounts
- Headers: Full name, Type, Detail type, Description, Total balance
- Types: Equity, Expenses, Income, Other Current Assets, etc.

### Balance Sheet
- Monthly columns with account hierarchies
- Sections: Assets, Liabilities, Equity
- Supports indentation or grouping for sub-accounts

### Profit & Loss
- Monthly columns with income and expense sections
- Supports hierarchical grouping (e.g., "Total for X")
- Handles calculated rows (Gross Profit, Net Income)

### Trial Balance
- Monthly columns with Debit and Credit sub-columns
- Account names in first column
- Total row at bottom

### Cash Flow Statement
- Monthly columns with cash flow activities
- Three main sections: Operating Activities, Investing Activities, Financing Activities
- Net Income adjustments and cash balance tracking
- Supports date ranges (e.g., "Aug 1 - Aug 26 2025")

### General Ledger
- Transaction-level detail organized by account
- Date range headers (e.g., "January 1-September 8, 2025")
- Transaction types: Invoice, Payment, Bill, Check, Deposit, Transfer
- Running balance for each transaction
- Account subtotals and grand totals

### Journal Entries
- Transaction-level detail with journal entry numbers
- Date, transaction type, number, name, memo, account, debit, credit, amount
- Grouped by journal entry number
- Split entries showing debits and credits

### Accounts Payable Aging
- Vendor column followed by aging buckets
- Aging buckets: Current, 1-30, 31-60, 61-90, 91 and over
- Total column showing vendor balance
- TOTAL row at bottom

### Accounts Receivable Aging
- Customer column followed by aging buckets
- Aging buckets: Current, 1-30, 31-60, 61-90, 91 and over
- Supports hierarchical customers (parent with sub-locations)
- Total rows for parent customers
- TOTAL row at bottom

### Vendor Concentration
- Two columns: Vendor and Total
- Simple list of vendors with their expense amounts
- Converter calculates percentages automatically
- Sorts by payment amount descending

### Customer Concentration
- Two columns: Customer and Total
- Simple list of customers with their revenue amounts
- Handles hierarchical customers (consolidates sub-customers into parent)
- Converter calculates percentages automatically
- Sorts by revenue amount descending

## Output Format

All converters generate QuickBooks-compatible JSON structures:

### Chart of Accounts
```json
{
  "id": "200",
  "name": "Advertising",
  "accountType": "EXPENSE",
  "accountSubType": "AdvertisingPromotional",
  "classification": "EXPENSE",
  "currentBalance": 0.00,
  "active": true,
  "currencyRef": {
    "value": "USD",
    "name": "United States Dollar"
  }
}
```

### Balance Sheet (Monthly)
```json
{
  "month": "2025-01",
  "startDate": "2025-01-01",
  "endDate": "2025-01-31",
  "report": {
    "header": {...},
    "columns": {...},
    "rows": {
      "row": [
        // Hierarchical structure with ASSETS, LIABILITIES, EQUITY
      ]
    }
  }
}
```

### Profit & Loss (Monthly)
```json
{
  "month": "2025-01",
  "startDate": "2025-01-01",
  "endDate": "2025-01-31",
  "report": {
    "header": {...},
    "columns": {...},
    "rows": {
      "row": [
        // Income and Expense sections with sub-groups
      ]
    }
  }
}
```

### Trial Balance
```json
{
  "monthlyReports": [
    {
      "month": "JANUARY",
      "year": "2025",
      "startDate": "2025-01-01",
      "endDate": "2025-01-31",
      "report": {
        "header": {...},
        "columns": {
          "column": [
            // Account column and Debit/Credit columns
          ]
        },
        "rows": {
          "row": [
            // Account rows with debit/credit values
          ]
        }
      }
    }
  ],
  "summary": {
    "requestStartDate": "2025-01-01",
    "requestEndDate": "2025-07-31",
    "totalMonths": 7,
    "accountingMethod": "Accrual"
  }
}
```

### Cash Flow Statement (Monthly)
```json
{
  "month": "2025-01",
  "startDate": "2025-01-01",
  "endDate": "2025-01-31",
  "report": {
    "header": {...},
    "columns": {...},
    "rows": {
      "row": [
        {
          "group": "NetIncome",
          "rows": {
            "row": [{"id": "1", "value": [{"value": "10000.00"}]}]
          }
        },
        {
          "group": "OperatingAdjustments",
          "rows": {
            "row": [
              // Adjustments to reconcile net income
            ]
          }
        },
        {
          "group": "OperatingActivities",
          "rows": {
            "row": [
              // Net cash from operating activities
            ]
          }
        },
        {
          "group": "InvestingActivities",
          "rows": {
            "row": [
              // Cash flows from investing
            ]
          }
        },
        {
          "group": "FinancingActivities",
          "rows": {
            "row": [
              // Cash flows from financing
            ]
          }
        },
        {
          "group": "CashIncrease",
          "rows": {
            "row": [{"value": [{"value": "5000.00"}]}]
          }
        },
        {
          "group": "BeginningCash",
          "rows": {
            "row": [{"value": [{"value": "20000.00"}]}]
          }
        },
        {
          "group": "EndingCash",
          "rows": {
            "row": [{"value": [{"value": "25000.00"}]}]
          }
        }
      ]
    }
  }
}
```

### General Ledger (Transaction Detail)
```json
{
  "startDate": "2025-01-01",
  "endDate": "2025-09-08",
  "report": {
    "header": {
      "reportName": "General Ledger",
      "reportBasis": "Accrual",
      "startPeriod": "2025-01-01",
      "endPeriod": "2025-09-08",
      "reportDate": "2025-09-08T00:00:00",
      "currency": "USD",
      "options": [
        {
          "name": "account_method",
          "value": "Accrual"
        },
        {
          "name": "summarize_column_by",
          "value": "none"
        }
      ]
    },
    "columns": {
      "column": [
        {"value": "Date", "type": "date"},
        {"value": "Transaction Type", "type": "text"}, 
        {"value": "No.", "type": "text"},
        {"value": "Name", "type": "text"},
        {"value": "Customer", "type": "text"},
        {"value": "Vendor", "type": "text"},
        {"value": "Category", "type": "text"},
        {"value": "Amount", "type": "money"},
        {"value": "Balance", "type": "money"}
      ]
    },
    "rows": {
      "row": [
        {
          "group": {
            "id": "101",
            "value": "Checking",
            "accountType": "Bank",
            "rows": {
              "row": [
                {
                  "value": [
                    {"value": "2025-01-01", "type": "date"},
                    {"value": "Opening Balance"},
                    {"value": ""},
                    {"value": ""},
                    {"value": ""},
                    {"value": ""},
                    {"value": ""},
                    {"value": "20000.00", "type": "money"},
                    {"value": "20000.00", "type": "money"}
                  ]
                },
                {
                  "value": [
                    {"value": "2025-01-15", "type": "date"},
                    {"value": "Invoice"},
                    {"value": "INV-001"},
                    {"value": "Customer A"},
                    {"value": "Customer A"},
                    {"value": ""},
                    {"value": "Services Income"},
                    {"value": "5000.00", "type": "money"},
                    {"value": "25000.00", "type": "money"}
                  ]
                }
              ]
            }
          }
        },
        // Additional accounts with their transactions...
      ]
    }
  }
}
```

### Journal Entries
```json
{
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "entries": [
    {
      "journalNo": "1",
      "date": "2025-01-15",
      "transactionType": "Journal Entry",
      "name": "Accrual Entry",
      "memo": "Record accrued expenses",
      "lines": [
        {
          "account": "Rent Expense",
          "accountId": "55",
          "debit": 1500.00,
          "credit": 0.00,
          "amount": 1500.00
        },
        {
          "account": "Accounts Payable",
          "accountId": "33",
          "debit": 0.00,
          "credit": 1500.00,
          "amount": -1500.00
        }
      ],
      "total": {
        "debit": 1500.00,
        "credit": 1500.00
      }
    }
  ]
}
```

### Accounts Payable Aging
```json
{
  "header": {
    "time": "2025-12-22T14:14:21.000+00:00",
    "reportName": "AgedPayables",
    "dateMacro": "today",
    "startPeriod": "2025-12-22",
    "endPeriod": "2025-12-22",
    "currency": "USD"
  },
  "columns": {
    "column": [
      {"colTitle": "", "colType": "Vendor"},
      {"colTitle": "Current", "colType": "Money"},
      {"colTitle": "1 - 30", "colType": "Money"},
      {"colTitle": "31 - 60", "colType": "Money"},
      {"colTitle": "61 - 90", "colType": "Money"},
      {"colTitle": "91 and over", "colType": "Money"},
      {"colTitle": "Total", "colType": "Money"}
    ]
  },
  "rows": {
    "row": [
      {
        "colData": [
          {"value": "ABC Supplies", "id": "31"},
          {"value": "500.00"},
          {"value": ""},
          {"value": ""},
          {"value": ""},
          {"value": "241.23"},
          {"value": "741.23"}
        ]
      }
    ]
  }
}
```

### Accounts Receivable Aging
```json
{
  "header": {
    "time": "2025-12-22T14:13:16.000+00:00",
    "reportName": "AgedReceivables",
    "dateMacro": "today",
    "startPeriod": "2025-12-22",
    "endPeriod": "2025-12-22",
    "currency": "USD"
  },
  "columns": {
    "column": [
      {"colTitle": "", "colType": "Customer"},
      {"colTitle": "Current", "colType": "Money"},
      {"colTitle": "1 - 30", "colType": "Money"},
      {"colTitle": "31 - 60", "colType": "Money"},
      {"colTitle": "61 - 90", "colType": "Money"},
      {"colTitle": "91 and over", "colType": "Money"},
      {"colTitle": "Total", "colType": "Money"}
    ]
  },
  "rows": {
    "row": [
      {
        "header": {
          "colData": [
            {"value": "ABC Company", "id": "7"},
            {"value": ""},
            {"value": ""},
            {"value": ""},
            {"value": ""},
            {"value": ""},
            {"value": "0.00"}
          ]
        },
        "rows": {
          "row": [
            {
              "colData": [
                {"value": "Main Office", "id": "8"},
                {"value": ""},
                {"value": ""},
                {"value": ""},
                {"value": ""},
                {"value": "477.50"},
                {"value": "477.50"}
              ],
              "type": "DATA"
            }
          ]
        },
        "summary": {
          "colData": [
            {"value": "Total ABC Company"},
            {"value": "0.00"},
            {"value": "0.00"},
            {"value": "0.00"},
            {"value": "0.00"},
            {"value": "477.50"},
            {"value": "477.50"}
          ]
        },
        "type": "SECTION"
      }
    ]
  }
}
```

### Vendor Concentration
```json
[
  {
    "vendorName": "ABC Supplies",
    "payments": 2241.23,
    "percentage": 36.489221236142924
  },
  {
    "vendorName": "XYZ Services",
    "payments": 900.0,
    "percentage": 14.652801859928982
  },
  {
    "vendorName": "Office Depot",
    "payments": 755.0,
    "percentage": 12.292072671384869
  }
]
```

### Customer Concentration
```json
[
  {
    "customerName": "Acme Corp",
    "revenue": 2369.52,
    "percentage": 23.38155975741405
  },
  {
    "customerName": "Widget Inc",
    "revenue": 1091.25,
    "percentage": 10.768057279650765
  },
  {
    "customerName": "Tech Solutions",
    "revenue": 954.75,
    "percentage": 9.421125028862834
  }
]
```

## Configuration

### Account Lookup Client

The converters can be configured to use account lookups:

```python
from balanceSheetConverter import BalanceSheetConverter

# With account lookup (default)
converter = BalanceSheetConverter(use_account_lookup=True)

# Without account lookup
converter = BalanceSheetConverter(use_account_lookup=False)

# Custom API URL
converter = BalanceSheetConverter(api_base_url="http://localhost:8080")
```

## Troubleshooting

### Common Issues

1. **ImportError for openpyxl or pdfplumber**
   ```bash
   pip install -r requirements.txt
   ```

2. **Database save fails / Unauthorized error**
   - Check that `QBTOJSON_API_KEY` is set in `.env`
   - Verify the same key is added to Supabase secrets
   - Test db-proxy connectivity:
   ```bash
   curl -X POST https://your-project.supabase.co/functions/v1/db-proxy \
     -H "x-api-key: your-key" \
     -H "x-service-name: test" \
     -H "Content-Type: application/json" \
     -d '{"action":"query","table":"processed_data","operation":"select","limit":1}'
   ```

3. **Storage-based endpoint fails**
   - Verify file exists in Supabase Storage at the specified path
   - Check `file_path` format: `"project-id/filename.xlsx"`
   - Ensure `project_id` is a valid UUID
   - Confirm db-proxy has storage operations enabled

4. **Account lookup API not available**
   - Start the API server first: `python api_server.py`
   - Or disable account lookup in converters

5. **PDF parsing issues**
   - Ensure PDFs are text-based (not scanned images)
   - Check that the PDF has a clear table structure

6. **Month detection issues**
   - Converters look for month names in headers
   - Ensure months are spelled out (January, February, etc.)

7. **"QBTOJSON_API_KEY not configured" warning**
   - This is normal if you haven't set up database integration
   - Add the key to `.env` to enable database features
   - The API will still work without it (just won't save to DB)

### Debug Mode

For detailed error messages, run converters directly:

```bash
python -u accountsConverter.py input.csv
```

Check API server logs for database connection issues:
```bash
# Run with verbose output
python api_server.py
```

Test database connectivity:
```python
from db_client import get_db_client

db_client = get_db_client()
print(f"Database configured: {db_client.is_configured()}")
```

## Development

### Adding New Converters

1. Create a new converter class inheriting from base patterns
2. Implement file parsing methods for CSV, XLSX, and PDF
3. Add the converter to `api_server.py`
4. Update this README

### Running Tests

```bash
# Test individual converters
python accountsConverter.py --test
python balanceSheetConverter.py --test
python profitLossConverter.py --test
python trialBalanceConverter.py --test
python cashFlowConverter.py --test
python generalLedgerConverter.py --test
```

## License

This project is provided as-is for educational and business use.
