#!/usr/bin/env python3
"""
REST API Server for Document Converters
Provides endpoints to convert Chart of Accounts and Balance Sheet documents to JSON
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
from pathlib import Path
from io import BytesIO
import traceback
from werkzeug.utils import secure_filename

# Import our converters
from accountsConverter import AccountsConverter
from balanceSheetConverter import BalanceSheetConverter
from profitLossConverter import ProfitLossConverter
from trialBalanceConverter import TrialBalanceConverter
from cashFlowConverter import CashFlowConverter
from generalLedgerConverter import GeneralLedgerConverter
from journalEntriesConverter import JournalEntriesConverter
from accountsPayableConverter import AccountsPayableConverter
from accountsReceivableConverter import AccountsReceivableConverter
from customerConcentrationConverter import CustomerConcentrationConverter
from vendorConcentrationConverter import VendorConcentrationConverter
from batch_processor import BatchProcessor

# Import database client
from db_client import get_db_client

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize database client
db_client = get_db_client()

# Configure upload settings
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file(file):
    """Validate uploaded file"""
    if not file or file.filename == '':
        return False, "No file provided"
    
    if not allowed_file(file.filename):
        return False, f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
    
    return True, None

def save_to_database_if_requested(result, data_type, file):
    """
    Save result to database if requested via form parameters
    
    Args:
        result: Converted data
        data_type: Type of document (e.g., 'trial_balance')
        file: Uploaded file object
        
    Returns:
        Dict with saved status and details
    """
    # Check if database save is requested
    save_to_db = request.form.get('save_to_db', 'false').lower() == 'true'
    
    if not save_to_db:
        return {'saved_to_db': False}
    
    # Get project_id from form
    project_id = request.form.get('project_id')
    
    if not project_id:
        return {
            'saved_to_db': False,
            'db_error': 'project_id required when save_to_db=true'
        }
    
    # Optional parameters
    source_document_id = request.form.get('source_document_id')
    
    # Attempt to save
    success = db_client.save_converted_data(
        project_id=project_id,
        data_type=data_type,
        data=result,
        source_document_id=source_document_id,
        filename=secure_filename(file.filename)
    )
    
    return {
        'saved_to_db': success,
        'project_id': project_id if success else None,
        'db_configured': db_client.is_configured()
    }

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Document Converter API",
        "db_configured": db_client.is_configured(),
        "endpoints": {
            "direct_upload": {
                "accounts": "/api/convert/accounts",
                "balance-sheet": "/api/convert/balance-sheet",
                "profit-loss": "/api/convert/profit-loss",
                "trial-balance": "/api/convert/trial-balance",
                "cash-flow": "/api/convert/cash-flow",
                "general-ledger": "/api/convert/general-ledger"
            },
            "from_storage": {
                "accounts": "/api/convert-from-storage/accounts",
                "balance-sheet": "/api/convert-from-storage/balance-sheet",
                "profit-loss": "/api/convert-from-storage/profit-loss",
                "trial-balance": "/api/convert-from-storage/trial-balance",
                "cash-flow": "/api/convert-from-storage/cash-flow",
                "general-ledger": "/api/convert-from-storage/general-ledger"
            },
            "batch": {
                "balance-sheet": "/api/batch/balance-sheet",
                "profit-loss": "/api/batch/profit-loss",
                "trial-balance": "/api/batch/trial-balance",
                "cash-flow": "/api/batch/cash-flow",
                "general-ledger": "/api/batch/general-ledger",
                "mixed": "/api/batch/mixed"
            }
        }
    })

# Store accounts in memory for lookup (in production, this would be a database)
accounts_cache = {}

@app.route('/api/accounts/lookup', methods=['POST'])
def lookup_account():
    """
    Look up account ID by name
    
    Request body: {"name": "Account Name"}
    Returns: {"id": "123", "name": "Account Name", ...}
    """
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({"error": "Account name required"}), 400
        
        account_name = data['name'].strip().lower()
        
        # Look up in cache
        for acc_id, account in accounts_cache.items():
            if account['name'].lower() == account_name:
                return jsonify({
                    "success": True,
                    "account": account
                })
        
        # Try fuzzy matching
        for acc_id, account in accounts_cache.items():
            if account_name in account['name'].lower() or account['name'].lower() in account_name:
                return jsonify({
                    "success": True,
                    "account": account,
                    "fuzzy_match": True
                })
        
        return jsonify({
            "success": False,
            "error": "Account not found"
        }), 404
        
    except Exception as e:
        app.logger.error(f"Error looking up account: {str(e)}")
        return jsonify({
            "error": "Failed to lookup account",
            "details": str(e)
        }), 500

@app.route('/api/accounts/load', methods=['POST'])
def load_accounts():
    """
    Load Chart of Accounts into memory for lookups
    
    Accepts: CSV, XLSX, or PDF file
    Returns: Success status
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = AccountsConverter()
            accounts = converter.convert_file(tmp_path)
            
            # Store in cache
            global accounts_cache
            accounts_cache = {acc['id']: acc for acc in accounts}
            
            # Return success response
            return jsonify({
                "success": True,
                "accounts_loaded": len(accounts),
                "message": "Chart of Accounts loaded successfully"
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error loading accounts: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to load accounts",
            "details": str(e)
        }), 500

@app.route('/api/convert/accounts', methods=['POST'])
def convert_accounts():
    """
    Convert Chart of Accounts document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON array of accounts
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = AccountsConverter()
            result = converter.convert_file(tmp_path)
            
            # Also update the cache
            global accounts_cache
            accounts_cache = {acc['id']: acc for acc in result}
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'chart_of_accounts', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "count": len(result),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting accounts: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/balance-sheet', methods=['POST'])
def convert_balance_sheet():
    """
    Convert Balance Sheet document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON array of monthly balance sheets
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = BalanceSheetConverter()
            result = converter.convert_file(tmp_path)
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'balance_sheet', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "months": len(result),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting balance sheet: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/profit-loss', methods=['POST'])
def convert_profit_loss():
    """
    Convert Profit and Loss document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON array of monthly profit and loss reports
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = ProfitLossConverter()
            result = converter.convert_file(tmp_path)
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'income_statement', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "months": len(result),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting profit and loss: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/trial-balance', methods=['POST'])
def convert_trial_balance():
    """
    Convert Trial Balance document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON object with monthly trial balance reports
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = TrialBalanceConverter()
            result = converter.convert_file(tmp_path)
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'trial_balance', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "months": len(result.get('monthlyReports', [])),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting trial balance: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/cash-flow', methods=['POST'])
def convert_cash_flow():
    """
    Convert Cash Flow Statement document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON array of monthly cash flow statements
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = CashFlowConverter()
            result = converter.convert_file(tmp_path)
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'cash_flow', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "months": len(result),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting cash flow: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/general-ledger', methods=['POST'])
def convert_general_ledger():
    """
    Convert General Ledger document to JSON
    
    Accepts: CSV, XLSX, or PDF file
    Returns: JSON object with general ledger data
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert file
            converter = GeneralLedgerConverter()
            result = converter.convert_file(tmp_path)
            
            # Save to database if requested
            db_result = save_to_database_if_requested(result, 'general_ledger', file)
            
            # Return JSON response
            return jsonify({
                "success": True,
                "data": result,
                "accounts": len(result.get('rows', {}).get('row', [])),
                "filename": secure_filename(file.filename),
                **db_result
            })
            
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error converting general ledger: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to convert file",
            "details": str(e)
        }), 500

@app.route('/api/convert/journal-entries', methods=['POST'])
def convert_journal_entries():
    """Convert Journal Entries document to JSON"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            converter = JournalEntriesConverter()
            result = converter.convert_file(tmp_path)
            db_result = save_to_database_if_requested(result, 'journal_entries', file)
            return jsonify({"success": True, "data": result, "filename": secure_filename(file.filename), **db_result})
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        app.logger.error(f"Error converting journal entries: {str(e)}")
        return jsonify({"error": "Failed to convert file", "details": str(e)}), 500

@app.route('/api/convert/accounts-payable', methods=['POST'])
def convert_accounts_payable():
    """Convert Accounts Payable document to JSON"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            converter = AccountsPayableConverter()
            result = converter.convert_file(tmp_path)
            db_result = save_to_database_if_requested(result, 'accounts_payable', file)
            return jsonify({"success": True, "data": result, "count": len(result), "filename": secure_filename(file.filename), **db_result})
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        app.logger.error(f"Error converting accounts payable: {str(e)}")
        return jsonify({"error": "Failed to convert file", "details": str(e)}), 500

@app.route('/api/convert/accounts-receivable', methods=['POST'])
def convert_accounts_receivable():
    """Convert Accounts Receivable document to JSON"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            converter = AccountsReceivableConverter()
            result = converter.convert_file(tmp_path)
            db_result = save_to_database_if_requested(result, 'accounts_receivable', file)
            return jsonify({"success": True, "data": result, "count": len(result), "filename": secure_filename(file.filename), **db_result})
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        app.logger.error(f"Error converting accounts receivable: {str(e)}")
        return jsonify({"error": "Failed to convert file", "details": str(e)}), 500

@app.route('/api/convert/customer-concentration', methods=['POST'])
def convert_customer_concentration():
    """Convert Customer Concentration document to JSON"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            converter = CustomerConcentrationConverter()
            result = converter.convert_file(tmp_path)
            db_result = save_to_database_if_requested(result, 'customer_concentration', file)
            return jsonify({"success": True, "data": result, "count": len(result), "filename": secure_filename(file.filename), **db_result})
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        app.logger.error(f"Error converting customer concentration: {str(e)}")
        return jsonify({"error": "Failed to convert file", "details": str(e)}), 500

@app.route('/api/convert/vendor-concentration', methods=['POST'])
def convert_vendor_concentration():
    """Convert Vendor Concentration document to JSON"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = Path(tmp_file.name)
        
        try:
            converter = VendorConcentrationConverter()
            result = converter.convert_file(tmp_path)
            db_result = save_to_database_if_requested(result, 'vendor_concentration', file)
            return jsonify({"success": True, "data": result, "count": len(result), "filename": secure_filename(file.filename), **db_result})
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception as e:
        app.logger.error(f"Error converting vendor concentration: {str(e)}")
        return jsonify({"error": "Failed to convert file", "details": str(e)}), 500

# Storage-based conversion endpoints - Helper function
def convert_from_storage_helper(converter_class, data_type, file_path, project_id, source_document_id=None):
    """Helper function for storage-based conversions"""
    # Download file from storage
    file_bytes = db_client.download_from_storage(file_path)
    
    # Save to temp file (converters expect Path)
    suffix = Path(file_path).suffix or '.xlsx'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = Path(tmp_file.name)
    
    try:
        # Convert
        converter = converter_class()
        result = converter.convert_file(tmp_path)
        
        # Save to database
        save_success = db_client.save_converted_data(
            project_id=project_id,
            data_type=data_type,
            data=result,
            source_document_id=source_document_id,
            filename=file_path.split('/')[-1]
        )
        
        return result, save_success
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

@app.route('/api/convert-from-storage/trial-balance', methods=['POST'])
def convert_trial_balance_from_storage():
    """Convert Trial Balance from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            TrialBalanceConverter, 'trial_balance',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result,
            "months": len(result.get('monthlyReports', [])),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/balance-sheet', methods=['POST'])
def convert_balance_sheet_from_storage():
    """Convert Balance Sheet from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            BalanceSheetConverter, 'balance_sheet',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "months": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/profit-loss', methods=['POST'])
def convert_profit_loss_from_storage():
    """Convert Profit & Loss from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            ProfitLossConverter, 'income_statement',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "months": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/cash-flow', methods=['POST'])
def convert_cash_flow_from_storage():
    """Convert Cash Flow from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            CashFlowConverter, 'cash_flow',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "months": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/general-ledger', methods=['POST'])
def convert_general_ledger_from_storage():
    """Convert General Ledger from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            GeneralLedgerConverter, 'general_ledger',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result,
            "accounts": len(result.get('rows', {}).get('row', [])),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/accounts', methods=['POST'])
def convert_accounts_from_storage():
    """Convert Chart of Accounts from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            AccountsConverter, 'chart_of_accounts',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "count": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/journal-entries', methods=['POST'])
def convert_journal_entries_from_storage():
    """Convert Journal Entries from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            JournalEntriesConverter, 'journal_entries',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result,
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/accounts-payable', methods=['POST'])
def convert_accounts_payable_from_storage():
    """Convert Accounts Payable from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            AccountsPayableConverter, 'accounts_payable',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "count": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/accounts-receivable', methods=['POST'])
def convert_accounts_receivable_from_storage():
    """Convert Accounts Receivable from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            AccountsReceivableConverter, 'accounts_receivable',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "count": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/customer-concentration', methods=['POST'])
def convert_customer_concentration_from_storage():
    """Convert Customer Concentration from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            CustomerConcentrationConverter, 'customer_concentration',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "count": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/convert-from-storage/vendor-concentration', methods=['POST'])
def convert_vendor_concentration_from_storage():
    """Convert Vendor Concentration from Supabase Storage"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data or 'project_id' not in data:
            return jsonify({"error": "file_path and project_id required"}), 400
        
        result, saved = convert_from_storage_helper(
            VendorConcentrationConverter, 'vendor_concentration',
            data['file_path'], data['project_id'], data.get('source_document_id')
        )
        
        return jsonify({
            "success": True, "data": result, "count": len(result),
            "file_path": data['file_path'], "saved_to_db": saved, "project_id": data['project_id']
        })
    except Exception as e:
        return jsonify({"error": "Failed to convert", "details": str(e)}), 500

@app.route('/api/info', methods=['GET'])
def api_info():
    """Get API information and usage examples"""
    return jsonify({
        "name": "Document Converter API",
        "version": "1.0.0",
        "endpoints": [
            {
                "path": "/api/accounts/load",
                "method": "POST",
                "description": "Load Chart of Accounts for ID lookups",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The Chart of Accounts file to load"
                    }
                },
                "response": {
                    "success": "boolean",
                    "accounts_loaded": "number of accounts loaded",
                    "message": "status message"
                }
            },
            {
                "path": "/api/accounts/lookup",
                "method": "POST",
                "description": "Look up account ID by name",
                "request": {
                    "type": "application/json",
                    "body": {
                        "name": "Account name to look up"
                    }
                },
                "response": {
                    "success": "boolean",
                    "account": "account object with id, name, etc.",
                    "fuzzy_match": "boolean (optional) - indicates if fuzzy matching was used"
                }
            },
            {
                "path": "/api/convert/accounts",
                "method": "POST",
                "description": "Convert Chart of Accounts to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "array of account objects",
                    "count": "number of accounts",
                    "filename": "original filename"
                }
            },
            {
                "path": "/api/convert/balance-sheet",
                "method": "POST",
                "description": "Convert Balance Sheet to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "array of monthly balance sheet objects",
                    "months": "number of months",
                    "filename": "original filename"
                }
            },
            {
                "path": "/api/convert/profit-loss",
                "method": "POST",
                "description": "Convert Profit and Loss to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "array of monthly profit and loss objects",
                    "months": "number of months",
                    "filename": "original filename"
                }
            },
            {
                "path": "/api/convert/trial-balance",
                "method": "POST",
                "description": "Convert Trial Balance to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "object with monthlyReports array and summary",
                    "months": "number of months",
                    "filename": "original filename"
                }
            },
            {
                "path": "/api/convert/cash-flow",
                "method": "POST",
                "description": "Convert Cash Flow Statement to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "array of monthly cash flow objects",
                    "months": "number of months",
                    "filename": "original filename"
                }
            },
            {
                "path": "/api/convert/general-ledger",
                "method": "POST",
                "description": "Convert General Ledger to JSON",
                "accepts": ["CSV", "XLSX", "PDF"],
                "request": {
                    "type": "multipart/form-data",
                    "fields": {
                        "file": "The document file to convert"
                    }
                },
                "response": {
                    "success": "boolean",
                    "data": "object with general ledger data",
                    "accounts": "number of accounts",
                    "filename": "original filename"
                }
            }
        ],
        "examples": {
            "curl": {
                "accounts": 'curl -X POST -F "file=@AccountList.csv" http://localhost:5000/api/convert/accounts',
                "balance_sheet": 'curl -X POST -F "file=@BalanceSheet.pdf" http://localhost:5000/api/convert/balance-sheet',
                "profit_loss": 'curl -X POST -F "file=@ProfitLoss.csv" http://localhost:5000/api/convert/profit-loss',
                "trial_balance": 'curl -X POST -F "file=@TrialBalance.xlsx" http://localhost:5000/api/convert/trial-balance',
                "cash_flow": 'curl -X POST -F "file=@CashFlow.csv" http://localhost:5000/api/convert/cash-flow',
                "general_ledger": 'curl -X POST -F "file=@GeneralLedger.csv" http://localhost:5000/api/convert/general-ledger'
            }
        }
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500

# Batch processing endpoints
@app.route('/api/batch/balance-sheet', methods=['POST'])
def batch_balance_sheet():
    """
    Process multiple Balance Sheet files and consolidate them
    
    Accepts: Multiple files or ZIP file containing CSV, XLSX, or PDF files
    Returns: Consolidated JSON array of monthly balance sheets
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'balance_sheet')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_balance_sheet_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch balance sheet processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

@app.route('/api/batch/profit-loss', methods=['POST'])
def batch_profit_loss():
    """
    Process multiple Profit & Loss files and consolidate them
    
    Accepts: Multiple files or ZIP file containing CSV, XLSX, or PDF files
    Returns: Consolidated JSON array of monthly P&L reports
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'profit_loss')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_profit_loss_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch profit loss processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

@app.route('/api/batch/trial-balance', methods=['POST'])
def batch_trial_balance():
    """
    Process multiple Trial Balance files and consolidate them
    
    Accepts: Multiple files or ZIP file containing CSV, XLSX, or PDF files
    Returns: Consolidated JSON object with monthly trial balance reports
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'trial_balance')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_trial_balance_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch trial balance processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

@app.route('/api/batch/cash-flow', methods=['POST'])
def batch_cash_flow():
    """
    Process multiple Cash Flow Statement files and consolidate them
    
    Accepts: Multiple files or ZIP file containing CSV, XLSX, or PDF files
    Returns: Consolidated JSON array of monthly cash flow statements
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'cash_flow')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_cash_flow_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch cash flow processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

@app.route('/api/batch/general-ledger', methods=['POST'])
def batch_general_ledger():
    """
    Process multiple General Ledger files and consolidate them
    
    Accepts: Multiple files or ZIP file containing CSV, XLSX, or PDF files
    Returns: Consolidated JSON object with general ledger data
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'general_ledger')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_general_ledger_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch general ledger processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

@app.route('/api/batch/mixed', methods=['POST'])
def batch_mixed():
    """
    Process multiple mixed financial documents and group by type
    
    Accepts: Multiple files or ZIP file containing mixed document types
    Returns: Grouped results by document type
    """
    try:
        processor = BatchProcessor()
        files_to_process = []
        
        # Check if files are in request
        if 'files' in request.files:
            # Multiple files uploaded
            files = request.files.getlist('files')
            for file in files:
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    return jsonify({"error": f"Invalid file {file.filename}: {error_msg}"}), 400
                
                # Read file content
                content = file.read()
                files_to_process.append((file.filename, content))
        
        elif 'file' in request.files and request.files['file'].filename.endswith('.zip'):
            # ZIP file uploaded
            zip_file = request.files['file']
            
            # Save ZIP temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                zip_file.save(tmp_file.name)
                tmp_path = Path(tmp_file.name)
            
            try:
                result = processor.process_zip_file(tmp_path, 'mixed')
                return jsonify(result)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        
        else:
            return jsonify({"error": "No files provided. Upload multiple files or a ZIP file"}), 400
        
        # Process the files
        result = processor.process_mixed_batch(files_to_process)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in batch mixed processing: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to process batch",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    # Run the development server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
