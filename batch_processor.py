#!/usr/bin/env python3
"""
Batch Processor for Financial Documents
Handles processing of multiple individual monthly files and consolidating them
"""

import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import calendar

# Import our converters
from balanceSheetConverter import BalanceSheetConverter
from profitLossConverter import ProfitLossConverter
from trialBalanceConverter import TrialBalanceConverter
from cashFlowConverter import CashFlowConverter
from generalLedgerConverter import GeneralLedgerConverter


class BatchProcessor:
    """Process multiple individual monthly files and consolidate them"""
    
    def __init__(self, use_account_lookup: bool = True, api_base_url: str = "http://localhost:8080"):
        self.use_account_lookup = use_account_lookup
        self.api_base_url = api_base_url
        
    def extract_date_from_filename(self, filename: str) -> Tuple[Optional[str], Optional[date]]:
        """
        Extract month/year from filename patterns like:
        - April 24 balance sheet.pdf -> 2024-04
        - Feb 25 P&L.pdf -> 2025-02
        - 2024-03 Balance Sheet.csv -> 2024-03
        - march 25 cash flow.pdf -> 2025-03
        """
        filename_lower = filename.lower()
        
        # Pattern 1: Month Year format (e.g., "April 24", "Feb 25")
        month_year_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{2,4})'
        match = re.search(month_year_pattern, filename_lower)
        if match:
            month_str = match.group(1)
            year_str = match.group(2)
            
            # Convert month name to number
            month_map = {
                'january': 1, 'jan': 1,
                'february': 2, 'feb': 2,
                'march': 3, 'mar': 3,
                'april': 4, 'apr': 4,
                'may': 5,
                'june': 6, 'jun': 6,
                'july': 7, 'jul': 7,
                'august': 8, 'aug': 8,
                'september': 9, 'sep': 9, 'sept': 9,
                'october': 10, 'oct': 10,
                'november': 11, 'nov': 11,
                'december': 12, 'dec': 12
            }
            
            month_num = month_map.get(month_str)
            if month_num:
                # Handle 2-digit year
                year = int(year_str)
                if year < 100:
                    year = 2000 + year
                
                month_str_formatted = f"{year}-{month_num:02d}"
                month_date = date(year, month_num, 1)
                return month_str_formatted, month_date
        
        # Pattern 2: YYYY-MM format
        yyyy_mm_pattern = r'(\d{4})-(\d{1,2})'
        match = re.search(yyyy_mm_pattern, filename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                month_str_formatted = f"{year}-{month:02d}"
                month_date = date(year, month, 1)
                return month_str_formatted, month_date
        
        # Pattern 3: MM/YYYY or MM.YYYY format
        mm_yyyy_pattern = r'(\d{1,2})[/.](\d{4})'
        match = re.search(mm_yyyy_pattern, filename)
        if match:
            month = int(match.group(1))
            year = int(match.group(2))
            if 1 <= month <= 12:
                month_str_formatted = f"{year}-{month:02d}"
                month_date = date(year, month, 1)
                return month_str_formatted, month_date
        
        return None, None
    
    def detect_document_type(self, filename: str, content: Optional[str] = None) -> Optional[str]:
        """
        Detect the type of financial document based on filename or content
        Returns: 'balance_sheet', 'profit_loss', 'trial_balance', 'cash_flow', 'general_ledger', or None
        """
        filename_lower = filename.lower()
        
        # Check filename patterns
        if any(term in filename_lower for term in ['balance sheet', 'balancesheet', 'balance_sheet', 'bs']):
            return 'balance_sheet'
        elif any(term in filename_lower for term in ['p&l', 'profit loss', 'profit and loss', 'profitloss', 'profit_loss', 'pl', 'income statement']):
            return 'profit_loss'
        elif any(term in filename_lower for term in ['trial balance', 'trialbalance', 'trial_balance', 'tb']):
            return 'trial_balance'
        elif any(term in filename_lower for term in ['cash flow', 'cashflow', 'cash_flow', 'cf', 'statement of cash flows']):
            return 'cash_flow'
        elif any(term in filename_lower for term in ['general ledger', 'generalledger', 'general_ledger', 'gl', 'ledger']):
            return 'general_ledger'
        
        # If content is provided, check content patterns
        if content:
            content_lower = content.lower()
            if any(term in content_lower for term in ['assets', 'liabilities', 'equity', 'current assets']):
                return 'balance_sheet'
            elif any(term in content_lower for term in ['revenue', 'income', 'expenses', 'gross profit', 'net income']):
                return 'profit_loss'
            elif 'debit' in content_lower and 'credit' in content_lower:
                return 'trial_balance'
            elif any(term in content_lower for term in ['operating activities', 'investing activities', 'financing activities', 'cash flows']):
                return 'cash_flow'
            elif any(term in content_lower for term in ['distribution account', 'transaction date', 'transaction type']) and 'balance' in content_lower:
                return 'general_ledger'
        
        return None
    
    def process_balance_sheet_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process multiple balance sheet files and consolidate them
        
        Args:
            files: List of file paths or tuples of (filename, content)
        
        Returns:
            Consolidated balance sheet data
        """
        converter = BalanceSheetConverter(self.use_account_lookup, self.api_base_url)
        monthly_data = {}
        errors = []
        
        for file_item in files:
            try:
                # Handle both file paths and file content tuples
                if isinstance(file_item, tuple):
                    filename, content = file_item
                    # Create a temporary file
                    suffix = Path(filename).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(content)
                        tmp_path = Path(tmp_file.name)
                else:
                    tmp_path = file_item
                    filename = tmp_path.name
                
                # Extract date from filename
                month_str, month_date = self.extract_date_from_filename(filename)
                
                if not month_str:
                    errors.append({
                        "file": filename,
                        "error": "Could not extract date from filename"
                    })
                    continue
                
                # Process the file
                try:
                    # Convert single file
                    result = converter.convert_file(tmp_path)
                    
                    # The result is already an array of months, but for individual files
                    # it should contain just one month
                    if result and len(result) > 0:
                        # If multiple months in file, use all of them
                        for month_data in result:
                            month_key = month_data.get('month', month_str)
                            monthly_data[month_key] = month_data
                    
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                
                # Clean up temp file if we created one
                if isinstance(file_item, tuple) and tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                errors.append({
                    "file": filename if isinstance(file_item, tuple) else str(file_item),
                    "error": str(e)
                })
        
        # Sort by date and create final array
        sorted_months = sorted(monthly_data.keys())
        result = [monthly_data[month] for month in sorted_months]
        
        return {
            "success": True,
            "data": result,
            "months_processed": len(result),
            "files_processed": len(files),
            "errors": errors if errors else None,
            "missing_months": self._find_missing_months(sorted_months) if sorted_months else None
        }
    
    def process_profit_loss_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process multiple P&L files and consolidate them
        """
        converter = ProfitLossConverter(self.use_account_lookup, self.api_base_url)
        monthly_data = {}
        errors = []
        
        for file_item in files:
            try:
                # Handle both file paths and file content tuples
                if isinstance(file_item, tuple):
                    filename, content = file_item
                    # Create a temporary file
                    suffix = Path(filename).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(content)
                        tmp_path = Path(tmp_file.name)
                else:
                    tmp_path = file_item
                    filename = tmp_path.name
                
                # Extract date from filename
                month_str, month_date = self.extract_date_from_filename(filename)
                
                if not month_str:
                    errors.append({
                        "file": filename,
                        "error": "Could not extract date from filename"
                    })
                    continue
                
                # Process the file
                try:
                    # Convert single file
                    result = converter.convert_file(tmp_path)
                    
                    if result and len(result) > 0:
                        # If multiple months in file, use all of them
                        for month_data in result:
                            month_key = month_data.get('month', month_str)
                            monthly_data[month_key] = month_data
                    
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                
                # Clean up temp file if we created one
                if isinstance(file_item, tuple) and tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                errors.append({
                    "file": filename if isinstance(file_item, tuple) else str(file_item),
                    "error": str(e)
                })
        
        # Sort by date and create final array
        sorted_months = sorted(monthly_data.keys())
        result = [monthly_data[month] for month in sorted_months]
        
        return {
            "success": True,
            "data": result,
            "months_processed": len(result),
            "files_processed": len(files),
            "errors": errors if errors else None,
            "missing_months": self._find_missing_months(sorted_months) if sorted_months else None
        }
    
    def process_trial_balance_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process multiple trial balance files and consolidate them
        """
        converter = TrialBalanceConverter(self.use_account_lookup, self.api_base_url)
        monthly_reports = []
        errors = []
        all_months = []
        
        for file_item in files:
            try:
                # Handle both file paths and file content tuples
                if isinstance(file_item, tuple):
                    filename, content = file_item
                    # Create a temporary file
                    suffix = Path(filename).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(content)
                        tmp_path = Path(tmp_file.name)
                else:
                    tmp_path = file_item
                    filename = tmp_path.name
                
                # Extract date from filename
                month_str, month_date = self.extract_date_from_filename(filename)
                
                if not month_str:
                    errors.append({
                        "file": filename,
                        "error": "Could not extract date from filename"
                    })
                    continue
                
                all_months.append(month_str)
                
                # Process the file
                try:
                    # Convert single file
                    result = converter.convert_file(tmp_path)
                    
                    if result and 'monthlyReports' in result:
                        # Add all monthly reports from this file
                        monthly_reports.extend(result['monthlyReports'])
                    
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                
                # Clean up temp file if we created one
                if isinstance(file_item, tuple) and tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                errors.append({
                    "file": filename if isinstance(file_item, tuple) else str(file_item),
                    "error": str(e)
                })
        
        # Sort reports by date
        monthly_reports.sort(key=lambda x: (x.get('year', '2025'), x.get('month', 'JANUARY')))
        
        # Create summary
        if monthly_reports:
            start_date = monthly_reports[0].get('startDate', '')
            end_date = monthly_reports[-1].get('endDate', '')
        else:
            start_date = ''
            end_date = ''
        
        result = {
            "monthlyReports": monthly_reports,
            "summary": {
                "requestStartDate": start_date,
                "requestEndDate": end_date,
                "totalMonths": len(monthly_reports),
                "accountingMethod": "Accrual"
            }
        }
        
        sorted_months = sorted(all_months) if all_months else []
        
        return {
            "success": True,
            "data": result,
            "months_processed": len(monthly_reports),
            "files_processed": len(files),
            "errors": errors if errors else None,
            "missing_months": self._find_missing_months(sorted_months) if sorted_months else None
        }
    
    def process_cash_flow_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process multiple cash flow statement files and consolidate them
        """
        converter = CashFlowConverter(self.use_account_lookup, self.api_base_url)
        monthly_data = {}
        errors = []
        
        for file_item in files:
            try:
                # Handle both file paths and file content tuples
                if isinstance(file_item, tuple):
                    filename, content = file_item
                    # Create a temporary file
                    suffix = Path(filename).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(content)
                        tmp_path = Path(tmp_file.name)
                else:
                    tmp_path = file_item
                    filename = tmp_path.name
                
                # Extract date from filename
                month_str, month_date = self.extract_date_from_filename(filename)
                
                if not month_str:
                    errors.append({
                        "file": filename,
                        "error": "Could not extract date from filename"
                    })
                    continue
                
                # Process the file
                try:
                    # Convert single file
                    result = converter.convert_file(tmp_path)
                    
                    if result and len(result) > 0:
                        # If multiple months in file, use all of them
                        for month_data in result:
                            month_key = month_data.get('month', month_str)
                            monthly_data[month_key] = month_data
                    
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                
                # Clean up temp file if we created one
                if isinstance(file_item, tuple) and tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                errors.append({
                    "file": filename if isinstance(file_item, tuple) else str(file_item),
                    "error": str(e)
                })
        
        # Sort by date and create final array
        sorted_months = sorted(monthly_data.keys())
        result = [monthly_data[month] for month in sorted_months]
        
        return {
            "success": True,
            "data": result,
            "months_processed": len(result),
            "files_processed": len(files),
            "errors": errors if errors else None,
            "missing_months": self._find_missing_months(sorted_months) if sorted_months else None
        }
    
    def process_general_ledger_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process multiple general ledger files and consolidate them
        """
        converter = GeneralLedgerConverter(self.use_account_lookup, self.api_base_url)
        all_ledgers = []
        errors = []
        
        for file_item in files:
            try:
                # Handle both file paths and file content tuples
                if isinstance(file_item, tuple):
                    filename, content = file_item
                    # Create a temporary file
                    suffix = Path(filename).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(content)
                        tmp_path = Path(tmp_file.name)
                else:
                    tmp_path = file_item
                    filename = tmp_path.name
                
                # Process the file
                try:
                    # Convert single file
                    result = converter.convert_file(tmp_path)
                    
                    if result:
                        # Add filename to the result for reference
                        result['source_file'] = filename
                        all_ledgers.append(result)
                    
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                
                # Clean up temp file if we created one
                if isinstance(file_item, tuple) and tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                errors.append({
                    "file": filename if isinstance(file_item, tuple) else str(file_item),
                    "error": str(e)
                })
        
        # If only one file, return its result directly
        if len(all_ledgers) == 1:
            result = all_ledgers[0]
        else:
            # Merge multiple ledgers (combine accounts)
            result = self._merge_general_ledgers(all_ledgers)
        
        return {
            "success": True,
            "data": result,
            "files_processed": len(files),
            "ledgers_combined": len(all_ledgers),
            "errors": errors if errors else None
        }
    
    def _merge_general_ledgers(self, ledgers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple general ledgers into one consolidated ledger
        """
        if not ledgers:
            return {}
        
        # Start with the first ledger as base
        merged = ledgers[0].copy()
        
        # Combine rows from all ledgers
        all_rows = []
        for ledger in ledgers:
            if 'rows' in ledger and 'row' in ledger['rows']:
                all_rows.extend(ledger['rows']['row'])
        
        # Group by account and merge
        account_map = {}
        for row in all_rows:
            if row.get('type') == 'SECTION' and row.get('header'):
                account_name = row['header']['colData'][0]['value']
                if account_name not in account_map:
                    account_map[account_name] = row
                else:
                    # Merge transactions
                    existing_transactions = account_map[account_name].get('rows', {}).get('row', [])
                    new_transactions = row.get('rows', {}).get('row', [])
                    account_map[account_name]['rows']['row'] = existing_transactions + new_transactions
        
        # Update merged result with combined rows
        merged['rows']['row'] = list(account_map.values())
        
        # Update header to reflect consolidation
        if len(ledgers) > 1:
            # Find the overall date range
            all_start_dates = []
            all_end_dates = []
            for ledger in ledgers:
                if 'header' in ledger:
                    if ledger['header'].get('startPeriod'):
                        all_start_dates.append(ledger['header']['startPeriod'])
                    if ledger['header'].get('endPeriod'):
                        all_end_dates.append(ledger['header']['endPeriod'])
            
            if all_start_dates:
                merged['header']['startPeriod'] = min(all_start_dates)
            if all_end_dates:
                merged['header']['endPeriod'] = max(all_end_dates)
        
        return merged
    
    def process_mixed_batch(self, files: List[Union[Path, Tuple[str, bytes]]]) -> Dict[str, Any]:
        """
        Process a mixed batch of different document types
        Automatically detects and routes each file to the appropriate processor
        """
        # Group files by type
        grouped_files = {
            'balance_sheet': [],
            'profit_loss': [],
            'trial_balance': [],
            'cash_flow': [],
            'general_ledger': [],
            'unknown': []
        }
        
        for file_item in files:
            if isinstance(file_item, tuple):
                filename, content = file_item
            else:
                filename = file_item.name
                content = None
            
            doc_type = self.detect_document_type(filename, content)
            if doc_type:
                grouped_files[doc_type].append(file_item)
            else:
                grouped_files['unknown'].append(file_item)
        
        # Process each type
        results = {}
        
        if grouped_files['balance_sheet']:
            results['balance_sheet'] = self.process_balance_sheet_batch(grouped_files['balance_sheet'])
        
        if grouped_files['profit_loss']:
            results['profit_loss'] = self.process_profit_loss_batch(grouped_files['profit_loss'])
        
        if grouped_files['trial_balance']:
            results['trial_balance'] = self.process_trial_balance_batch(grouped_files['trial_balance'])
        
        if grouped_files['cash_flow']:
            results['cash_flow'] = self.process_cash_flow_batch(grouped_files['cash_flow'])
        
        if grouped_files['general_ledger']:
            results['general_ledger'] = self.process_general_ledger_batch(grouped_files['general_ledger'])
        
        # Prepare summary
        total_processed = sum(len(files) for files in grouped_files.values() if files)
        total_success = sum(
            result.get('months_processed', result.get('ledgers_combined', 0)) 
            for result in results.values()
        )
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "total_files": len(files),
                "files_processed": total_processed,
                "balance_sheets": len(grouped_files['balance_sheet']),
                "profit_loss": len(grouped_files['profit_loss']),
                "trial_balances": len(grouped_files['trial_balance']),
                "cash_flows": len(grouped_files['cash_flow']),
                "general_ledgers": len(grouped_files['general_ledger']),
                "unknown_files": len(grouped_files['unknown'])
            },
            "unknown_files": [
                f.name if isinstance(f, Path) else f[0] 
                for f in grouped_files['unknown']
            ] if grouped_files['unknown'] else None
        }
    
    def _find_missing_months(self, months: List[str]) -> List[str]:
        """Find missing months in a date range"""
        if not months or len(months) < 2:
            return []
        
        # Parse first and last month
        first = datetime.strptime(months[0], '%Y-%m').date()
        last = datetime.strptime(months[-1], '%Y-%m').date()
        
        # Generate all months in range
        missing = []
        current = first
        month_set = set(months)
        
        while current <= last:
            month_str = current.strftime('%Y-%m')
            if month_str not in month_set:
                missing.append(month_str)
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return missing
    
    def process_zip_file(self, zip_path: Path, doc_type: str = 'mixed') -> Dict[str, Any]:
        """
        Process a zip file containing multiple financial documents
        """
        extracted_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if not file_info.is_dir() and not file_info.filename.startswith('__MACOSX'):
                    # Read file content
                    content = zip_file.read(file_info.filename)
                    extracted_files.append((file_info.filename, content))
        
        # Route to appropriate processor
        if doc_type == 'balance_sheet':
            return self.process_balance_sheet_batch(extracted_files)
        elif doc_type == 'profit_loss':
            return self.process_profit_loss_batch(extracted_files)
        elif doc_type == 'trial_balance':
            return self.process_trial_balance_batch(extracted_files)
        elif doc_type == 'cash_flow':
            return self.process_cash_flow_batch(extracted_files)
        elif doc_type == 'general_ledger':
            return self.process_general_ledger_batch(extracted_files)
        else:
            return self.process_mixed_batch(extracted_files)
