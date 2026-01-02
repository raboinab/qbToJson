# qbToJson - Supabase Integration Guide

## 🎯 Overview

This guide shows how to integrate the qbToJson service with Supabase to poll for uploaded QuickBooks files, transform them using the converters, and store the processed data in the unified `processed_data` table.

---

## 📊 Architecture

```
User uploads QB file → Supabase (documents table, status='pending')
    ↓
qbToJson Service polls for pending documents
    ↓
Download file from Supabase Storage
    ↓
Transform using Converters (trialBalanceConverter.py, etc.)
    ↓
Store in Supabase (processed_data table via Edge Function)
    ↓
Update document status (status='completed')
    ↓
shepiSheets reads data → Creates Google Sheet
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies

```bash
pip install requests python-dotenv
```

### 2. Add Environment Variables

Create `.env` file:

```bash
SUPABASE_URL=https://klccgigaedojxdpnkjcd.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

### 3. Add Supabase Client (see below)

Copy the `supabase_client.py` file into your project.

### 4. Create Polling Script

```python
from supabase_client import SupabaseClient
from trialBalanceConverter import convert_trial_balance

# Initialize
supabase = SupabaseClient()

# Poll for pending documents
pending_docs = supabase.get_pending_documents(project_id, 'quickbooks_file')

for doc in pending_docs:
    # Download and process
    file_data = supabase.download_document(doc['file_path'])
    transformed = convert_trial_balance(file_data)
    
    # Store result
    supabase.store_processed_data(
        project_id=doc['project_id'],
        source_document_id=doc['id'],
        data_type='trial_balance',
        data=transformed
    )
    
    # Mark complete
    supabase.update_document_status(doc['id'], 'completed')
```

---

## 📋 Prerequisites

### Required Access
- Supabase service role key (get from: https://supabase.com/dashboard/project/klccgigaedojxdpnkjcd/settings/api)
- Access to Supabase storage bucket
- Project ID from Supabase

### Required Environment
- Python 3.8+
- pip (for dependencies)
- Access to Supabase instance

---

## 🔧 Implementation

### Step 1: Create Supabase Client Module

Create: `supabase_client.py`

```python
"""
Supabase client for qbToJson service.
Handles document polling, storage access, and processed data storage.
"""

import os
import requests
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupabaseClient:
    """Client for interacting with Supabase."""
    
    def __init__(self):
        """Initialize Supabase client with service role key."""
        self.supabase_url = os.environ.get("SUPABASE_URL", "https://klccgigaedojxdpnkjcd.supabase.co")
        self.service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.service_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
            "Content-Type": "application/json"
        }
        
        logger.info("SupabaseClient initialized successfully")
    
    # ==================== DOCUMENT POLLING ====================
    
    def get_pending_documents(self, project_id: Optional[str] = None, 
                             category: str = "quickbooks_file") -> List[Dict]:
        """
        Get pending documents to process.
        
        Args:
            project_id: Optional project UUID to filter by
            category: Document category (default: 'quickbooks_file')
            
        Returns:
            List of pending document records
        """
        try:
            url = f"{self.supabase_url}/rest/v1/documents"
            params = {
                "category": f"eq.{category}",
                "processing_status": "eq.pending",
                "select": "*",
                "order": "created_at.asc"
            }
            
            if project_id:
                params["project_id"] = f"eq.{project_id}"
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            results = response.json()
            logger.info(f"Found {len(results)} pending documents")
            return results
            
        except requests.RequestException as e:
            logger.error(f"Error fetching pending documents: {e}")
            return []
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """
        Get a specific document by ID.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document record or None
        """
        try:
            url = f"{self.supabase_url}/rest/v1/documents"
            params = {
                "id": f"eq.{document_id}",
                "select": "*"
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            results = response.json()
            return results[0] if results else None
            
        except requests.RequestException as e:
            logger.error(f"Error fetching document: {e}")
            return None
    
    # ==================== STORAGE ACCESS ====================
    
    def download_document(self, file_path: str) -> bytes:
        """
        Download file from Supabase Storage.
        
        Args:
            file_path: Path in storage bucket (e.g., 'project-id/filename.xlsx')
            
        Returns:
            File content as bytes
        """
        try:
            # Extract bucket and path
            # Assuming file_path format: "bucket/path/to/file"
            bucket = "documents"  # Default bucket
            
            url = f"{self.supabase_url}/storage/v1/object/{bucket}/{file_path}"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            logger.info(f"Downloaded file: {file_path}")
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"Error downloading file {file_path}: {e}")
            raise
    
    def get_signed_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Get signed URL for file download (alternative method).
        
        Args:
            file_path: Path in storage bucket
            expires_in: URL expiration in seconds (default: 1 hour)
            
        Returns:
            Signed URL string or None
        """
        try:
            bucket = "documents"
            url = f"{self.supabase_url}/storage/v1/object/sign/{bucket}/{file_path}"
            
            payload = {"expiresIn": expires_in}
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            signed_url = result.get("signedURL")
            
            if signed_url:
                # Construct full URL
                return f"{self.supabase_url}/storage/v1{signed_url}"
            
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error getting signed URL: {e}")
            return None
    
    # ==================== PROCESSED DATA STORAGE ====================
    
    def store_processed_data(self, project_id: str, data_type: str, data: Dict,
                            source_document_id: Optional[str] = None,
                            period_start: Optional[str] = None,
                            period_end: Optional[str] = None,
                            record_count: Optional[int] = None) -> bool:
        """
        Store processed data via Edge Function.
        
        Args:
            project_id: Supabase project UUID
            data_type: Type of data (e.g., 'trial_balance', 'balance_sheet')
            data: Processed data dictionary
            source_document_id: Optional source document UUID
            period_start: Optional period start date (YYYY-MM-DD)
            period_end: Optional period end date (YYYY-MM-DD)
            record_count: Optional number of records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.supabase_url}/functions/v1/processed-data-create"
            
            payload = {
                "project_id": project_id,
                "source_type": "qbtojson",
                "data_type": data_type,
                "data": data
            }
            
            if source_document_id:
                payload["source_document_id"] = source_document_id
            if period_start:
                payload["period_start"] = period_start
            if period_end:
                payload["period_end"] = period_end
            if record_count is not None:
                payload["record_count"] = record_count
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logger.info(f"Successfully stored {data_type} data for project: {project_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error storing processed data: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False
    
    # ==================== DOCUMENT STATUS UPDATES ====================
    
    def update_document_status(self, document_id: str, status: str,
                               parsed_summary: Optional[Dict] = None) -> bool:
        """
        Update document processing status.
        
        Args:
            document_id: Document UUID
            status: New status ('processing', 'completed', 'failed')
            parsed_summary: Optional summary of parsed data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.supabase_url}/rest/v1/documents"
            params = {"id": f"eq.{document_id}"}
            
            data = {
                "processing_status": status,
                "updated_at": "now()"
            }
            
            if parsed_summary:
                data["parsed_summary"] = parsed_summary
            
            headers = {**self.headers, "Prefer": "return=representation"}
            
            response = requests.patch(url, headers=headers, params=params, json=data)
            response.raise_for_status()
            
            logger.info(f"Updated document {document_id} status to: {status}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error updating document status: {e}")
            return False
    
    def mark_document_failed(self, document_id: str, error_message: str) -> bool:
        """
        Mark document as failed with error message.
        
        Args:
            document_id: Document UUID
            error_message: Error description
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_document_status(
            document_id,
            'failed',
            parsed_summary={"error": error_message}
        )


# Example usage and testing
if __name__ == "__main__":
    # Initialize client
    client = SupabaseClient()
    
    # Test: Get pending documents
    pending = client.get_pending_documents()
    print(f"Found {len(pending)} pending documents")
    
    if pending:
        doc = pending[0]
        print(f"First document: {doc['id']} - {doc['file_name']}")
```

### Step 2: Create Processing Workflow

Create: `process_documents.py`

```python
"""
Main processing workflow for qbToJson service.
Polls for pending documents and processes them.
"""

import logging
import time
from typing import Dict
from supabase_client import SupabaseClient
import trialBalanceConverter
import balanceSheetConverter
import profitLossConverter
# Import other converters as needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process uploaded QuickBooks documents."""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        
    def detect_document_type(self, file_name: str, file_content: bytes) -> str:
        """
        Detect the type of QuickBooks document.
        
        Args:
            file_name: Name of the uploaded file
            file_content: File content as bytes
            
        Returns:
            Document type ('trial_balance', 'balance_sheet', etc.)
        """
        # Simple detection based on filename
        file_name_lower = file_name.lower()
        
        if 'trial' in file_name_lower or 'tb' in file_name_lower:
            return 'trial_balance'
        elif 'balance' in file_name_lower or 'bs' in file_name_lower:
            return 'balance_sheet'
        elif 'profit' in file_name_lower or 'loss' in file_name_lower or 'pl' in file_name_lower:
            return 'income_statement'
        elif 'ledger' in file_name_lower or 'gl' in file_name_lower:
            return 'general_ledger'
        else:
            # Default or use content analysis
            return 'unknown'
    
    def process_document(self, document: Dict) -> bool:
        """
        Process a single document.
        
        Args:
            document: Document record from Supabase
            
        Returns:
            True if successful, False otherwise
        """
        doc_id = document['id']
        file_path = document['file_path']
        file_name = document['file_name']
        project_id = document['project_id']
        
        try:
            logger.info(f"Processing document: {file_name} ({doc_id})")
            
            # Update status to 'processing'
            self.supabase.update_document_status(doc_id, 'processing')
            
            # Download file
            file_content = self.supabase.download_document(file_path)
            
            # Detect document type
            doc_type = self.detect_document_type(file_name, file_content)
            
            if doc_type == 'unknown':
                logger.warning(f"Unknown document type: {file_name}")
                self.supabase.mark_document_failed(doc_id, "Unknown document type")
                return False
            
            # Transform based on type
            transformed_data = self.transform_data(file_content, doc_type)
            
            if not transformed_data:
                self.supabase.mark_document_failed(doc_id, "Transformation failed")
                return False
            
            # Store in Supabase
            success = self.supabase.store_processed_data(
                project_id=project_id,
                data_type=doc_type,
                data=transformed_data,
                source_document_id=doc_id,
                record_count=len(transformed_data.get('rows', []))
            )
            
            if not success:
                self.supabase.mark_document_failed(doc_id, "Failed to store processed data")
                return False
            
            # Mark as completed
            self.supabase.update_document_status(
                doc_id,
                'completed',
                parsed_summary={
                    "type": doc_type,
                    "record_count": len(transformed_data.get('rows', []))
                }
            )
            
            logger.info(f"Successfully processed document: {file_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            self.supabase.mark_document_failed(doc_id, str(e))
            return False
    
    def transform_data(self, file_content: bytes, doc_type: str) -> Dict:
        """
        Transform data using appropriate converter.
        
        Args:
            file_content: File content as bytes
            doc_type: Document type
            
        Returns:
            Transformed data dictionary
        """
        try:
            if doc_type == 'trial_balance':
                return trialBalanceConverter.convert(file_content)
            elif doc_type == 'balance_sheet':
                return balanceSheetConverter.convert(file_content)
            elif doc_type == 'income_statement':
                return profitLossConverter.convert(file_content)
            # Add other converters
            else:
                logger.error(f"No converter for type: {doc_type}")
                return {}
                
        except Exception as e:
            logger.error(f"Error transforming data: {e}")
            return {}
    
    def process_pending_documents(self, project_id: str = None):
        """
        Process all pending documents.
        
        Args:
            project_id: Optional project ID to filter by
        """
        logger.info("Checking for pending documents...")
        
        pending_docs = self.supabase.get_pending_documents(project_id)
        
        if not pending_docs:
            logger.info("No pending documents found")
            return
        
        logger.info(f"Found {len(pending_docs)} pending documents")
        
        for doc in pending_docs:
            self.process_document(doc)
    
    def run_continuous(self, interval: int = 60):
        """
        Run continuous polling loop.
        
        Args:
            interval: Seconds between polls (default: 60)
        """
        logger.info(f"Starting continuous polling (interval: {interval}s)")
        
        while True:
            try:
                self.process_pending_documents()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
            
            time.sleep(interval)


if __name__ == "__main__":
    processor = DocumentProcessor()
    
    # Option 1: Process once
    # processor.process_pending_documents()
    
    # Option 2: Continuous polling
    processor.run_continuous(interval=60)
```

### Step 3: Update Environment Configuration

Create `.env.example`:

```bash
# Supabase Configuration
SUPABASE_URL=https://klccgigaedojxdpnkjcd.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Processing Configuration
POLL_INTERVAL=60  # Seconds between checks
BATCH_SIZE=10     # Max documents to process at once
```

### Step 4: Update requirements.txt

Add to `requirements.txt`:

```txt
requests>=2.31.0
python-dotenv>=1.0.0
# Keep existing dependencies
```

---

## 📊 Supported Data Types

Use these standard data type names when storing data:

| data_type | Description | Converter File |
|-----------|-------------|----------------|
| `trial_balance` | Trial Balance | trialBalanceConverter.py |
| `balance_sheet` | Balance Sheet | balanceSheetConverter.py |
| `income_statement` | Profit & Loss | profitLossConverter.py |
| `chart_of_accounts` | Chart of Accounts | accountsConverter.py |
| `general_ledger` | General Ledger | generalLedgerConverter.py |
| `ar_aging` | AR Aging | accountsReceivableConverter.py |
| `ap_aging` | AP Aging | accountsPayableConverter.py |
| `cash_flow` | Cash Flow | cashFlowConverter.py |

---

## 🧪 Testing

### Test Script

Create `test_integration.py`:

```python
"""Test Supabase integration."""

from supabase_client import SupabaseClient

def test_connection():
    """Test basic connection."""
    try:
        client = SupabaseClient()
        print("✅ Connection successful")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_poll_documents():
    """Test document polling."""
    try:
        client = SupabaseClient()
        docs = client.get_pending_documents()
        print(f"✅ Found {len(docs)} pending documents")
        return True
    except Exception as e:
        print(f"❌ Polling failed: {e}")
        return False

def test_store_data():
    """Test storing processed data."""
    try:
        client = SupabaseClient()
        
        test_data = {
            "header": {
                "report_type": "Trial Balance",
                "period": "2024-01-01 to 2024-12-31"
            },
            "rows": [
                {"account": "Cash", "debit": 1000, "credit": 0}
            ]
        }
        
        success = client.store_processed_data(
            project_id="test-project-id",
            data_type="trial_balance",
            data=test_data
        )
        
        if success:
            print("✅ Data storage successful")
        else:
            print("❌ Data storage failed")
        
        return success
        
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Supabase integration tests...\n")
    
    test_connection()
    test_poll_documents()
    # test_store_data()  # Uncomment to test with real project ID
```

Run tests:

```bash
python test_integration.py
```

---

## 🚀 Deployment

### Option 1: Docker Deployment

Update `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run the processor
CMD ["python", "process_documents.py"]
```

Build and run:

```bash
# Build
docker build -t qbtojson:latest .

# Run with environment variables
docker run -e SUPABASE_URL=$SUPABASE_URL \
           -e SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY \
           qbtojson:latest
```

### Option 2: Cloud Run Deployment

```bash
# Build and push
gcloud builds submit --tag gcr.io/your-project/qbtojson

# Deploy with secrets
gcloud run deploy qbtojson \
  --image gcr.io/your-project/qbtojson \
  --set-env-vars SUPABASE_URL=https://klccgigaedojxdpnkjcd.supabase.co \
  --set-secrets SUPABASE_SERVICE_ROLE_KEY=supabase-service-key:latest \
  --region us-central1
```

---

## 🔍 Troubleshooting

### Issue: "SUPABASE_SERVICE_ROLE_KEY not found"

**Solution:**
```bash
# Check .env file exists
ls -la .env

# Load environment
export $(cat .env | xargs)

# Verify loaded
echo $SUPABASE_SERVICE_ROLE_KEY
```

### Issue: "No pending documents found"

**Possible causes:**
- No files uploaded yet
- Documents already processed
- Wrong category filter

**Solution:**
- Check Supabase Dashboard → Documents table
- Verify `processing_status` = 'pending'
- Verify `category` = 'quickbooks_file'

### Issue: "Failed to download file"

**Cause:** Storage permissions or invalid path

**Solution:**
- Verify file_path format in documents table
- Check service role key has storage access
- Test with signed URL method

### Issue: "Transformation failed"

**Cause:** Invalid file format or converter error

**Solution:**
- Check file is valid CSV/Excel
- Test converter directly
- Add logging to converter
- Handle edge cases

---

## 📋 Integration Checklist

- [ ] Install Python dependencies
- [ ] Get Supabase service role key
- [ ] Create `.env` file with credentials
- [ ] Add `supabase_client.py` to project
- [ ] Create `process_documents.py` workflow
- [ ] Update each converter to handle errors
- [ ] Test connection
- [ ] Test document polling
- [ ] Test data storage
- [ ] Test full workflow end-to-end
- [ ] Deploy to Cloud Run
- [ ] Set up monitoring/logging
- [ ] Verify with shepiSheets integration

---

## 🔐 Security Best Practices

1. **Never commit .env file**
   ```bash
   echo ".env" >> .gitignore
   git rm --cached .env  # If already committed
   ```

2. **Use environment variables in production**
   - Cloud Run: Use secrets manager
   - Docker: Pass via -e flags
   - Local: Use .env file

3. **Rotate service keys periodically**

4. **Monitor API usage**
   - Check Supabase logs
   - Set up alerts for failures

---

## 📚 Additional Resources

- **Supabase Dashboard:** https://supabase.com/dashboard/project/klccgigaedojxdpnkjcd
- **Python Requests Docs:** https://requests.readthedocs.io/
- **API Reference:** See BACKEND_INTEGRATION_REFERENCE.md

---

## ✅ Success Criteria

Your integration is successful when:

1. ✅ qbToJson polls for pending documents
2. ✅ Files are downloaded successfully
3. ✅ Data is transformed by converters
4. ✅ Processed data appears in Supabase
5. ✅ Document status updates to 'completed'
6. ✅ shepiSheets can read the data
7. ✅ Google Sheets are populated

---

## 🎯 Next Steps

1. **Test with sample files** - Verify each converter works
2. **Add error handling** - Handle edge cases
3. **Set up monitoring** - Track processing metrics
4. **Optimize performance** - Batch processing if needed
5. **Document edge cases** - Add to troubleshooting

**Your qbToJson service is ready to integrate with Supabase!** 🚀
