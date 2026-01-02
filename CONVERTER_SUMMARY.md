# Chart of Accounts Converter - Summary

## What We Built

A flexible Python application (`accountsConverter.py`) that converts various document formats containing chart of accounts data into a standardized JSON format compatible with your application. This is specifically designed for Chart of Accounts reports, with room for additional converters for other report types.

## Key Features

1. **Multi-format Support**
   - CSV files (no dependencies required)
   - Excel files (.xlsx) - requires openpyxl
   - PDF files - requires pdfplumber

2. **Flexible Type Handling**
   - The converter preserves the original account types and detail types from source documents
   - No hardcoded mappings - works with any business's chart of accounts
   - Intelligently determines classification and account type based on the "Type" field
   - Passes through detail types as-is (with minor formatting cleanup)

3. **Batch Processing**
   - Can process single files or entire directories
   - Command-line interface for easy automation

## How It Works

The converter:
1. Reads the source document (CSV, XLSX, or PDF)
2. Extracts account information:
   - Full name → name
   - Type → used to determine classification and accountType
   - Detail type → accountSubType (cleaned but preserved)
   - Description → description
   - Total balance → currentBalance
3. Generates required QuickBooks fields:
   - Unique IDs
   - Timestamps
   - Default values for missing fields
   - Currency information (USD)
4. Outputs JSON in the expected format

## Usage Examples

### Command Line
```bash
# Convert single file
python3 accountsConverter.py "path/to/accounts.csv" -o output.json

# Batch convert directory
python3 accountsConverter.py --batch sampleReports/ -o converted/
```

### Programmatic Usage
```python
from accountsConverter import AccountsConverter

converter = AccountsConverter()
accounts = converter.convert_file("accounts.csv")
```

## Important Notes

- The converter preserves the original detail types from your documents
- It doesn't try to map or change account types - it just transforms the format
- This makes it suitable for any business, not just the sample data
- Missing fields are populated with sensible defaults (null, empty arrays, etc.)

## Files Created

1. `accountsConverter.py` - Main Chart of Accounts converter application
2. `requirements.txt` - Optional dependencies for Excel and PDF support
3. `README.md` - User documentation
4. `example_usage.py` - Example code showing how to use the converter
5. `CONVERTER_SUMMARY.md` - This summary document

## Future Converters

This naming convention allows for additional report converters:
- `invoicesConverter.py` - For invoice reports
- `customersConverter.py` - For customer lists
- `transactionsConverter.py` - For transaction reports
- etc.
