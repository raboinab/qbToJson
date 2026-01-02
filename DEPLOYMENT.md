# 🚀 qbToJson - Cloud Run Deployment Guide

## 📋 Prerequisites

Before deploying, ensure you have:

- ✅ Google Cloud SDK installed (`gcloud`)
- ✅ Docker installed
- ✅ Authenticated with Google Cloud (`gcloud auth login`)
- ✅ Project set to `qofeai` (`gcloud config set project qofeai`)
- ✅ Docker configured for GCR (`gcloud auth configure-docker`)

## 🎯 Quick Deploy

### Option 1: Automated Deployment (Recommended)

Run the deployment script:

```bash
cd /Users/araboin/qofeai/qbToJson
./deploy.sh
```

This will:
1. ✅ Build the Docker image
2. ✅ Push to Google Container Registry
3. ✅ Deploy to Cloud Run
4. ✅ Display the service URL

### Option 2: Manual Deployment

If you prefer manual control:

```bash
# 1. Build the Docker image
docker build --platform linux/amd64 -t gcr.io/qofeai/qbtojson:latest .

# 2. Push to GCR
docker push gcr.io/qofeai/qbtojson:latest

# 3. Deploy to Cloud Run
gcloud run deploy qbtojson \
  --image gcr.io/qofeai/qbtojson:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --min-instances 0
```

## 🧪 Testing After Deployment

Once deployed, test the service:

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe qbtojson --region us-central1 --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test API info endpoint
curl $SERVICE_URL/api/info

# Test document conversion
curl -X POST -F "file=@sampleReports/AccountList.csv" $SERVICE_URL/api/convert/accounts
```

## 📊 Service Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| **Memory** | 1Gi | Sufficient for PDF processing |
| **CPU** | 1 | Single CPU core |
| **Timeout** | 300s | 5 minutes for large files |
| **Max Instances** | 10 | Auto-scales up to 10 |
| **Min Instances** | 0 | Scales to zero when idle |
| **Authentication** | Unauthenticated | Publicly accessible |

## 🔧 Configuration Options

### Environment Variables

You can add environment variables during deployment:

```bash
gcloud run deploy qbtojson \
  --image gcr.io/qofeai/qbtojson:latest \
  --set-env-vars="LOG_LEVEL=INFO,MAX_FILE_SIZE=20971520"
```

### Memory and CPU Adjustments

For heavier workloads:

```bash
gcloud run deploy qbtojson \
  --image gcr.io/qofeai/qbtojson:latest \
  --memory 2Gi \
  --cpu 2
```

## 🔒 Security Considerations

### Making Service Private

If you want to require authentication:

```bash
gcloud run deploy qbtojson \
  --image gcr.io/qofeai/qbtojson:latest \
  --no-allow-unauthenticated
```

Then access with:
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $SERVICE_URL/health
```

## 📈 Monitoring

### View Logs

```bash
gcloud run services logs read qbtojson --region us-central1 --limit 50
```

### Stream Logs

```bash
gcloud run services logs tail qbtojson --region us-central1
```

### View Metrics

Visit Cloud Console:
```
https://console.cloud.google.com/run/detail/us-central1/qbtojson/metrics?project=qofeai
```

## 🔄 Updating the Service

To deploy updates:

```bash
# Rebuild and redeploy
./deploy.sh

# Or manually:
docker build --platform linux/amd64 -t gcr.io/qofeai/qbtojson:latest .
docker push gcr.io/qofeai/qbtojson:latest
gcloud run deploy qbtojson --image gcr.io/qofeai/qbtojson:latest --region us-central1
```

## 🧹 Cleanup

### Delete the Service

```bash
gcloud run services delete qbtojson --region us-central1
```

### Delete Container Images

```bash
gcloud container images delete gcr.io/qofeai/qbtojson:latest --quiet
```

## 🐛 Troubleshooting

### Build Fails

**Issue:** Docker build fails
**Solution:** 
- Check Docker is running
- Ensure you're in the correct directory
- Check Dockerfile syntax

### Push Fails

**Issue:** Cannot push to GCR
**Solution:**
```bash
gcloud auth configure-docker
```

### Deployment Fails

**Issue:** Cloud Run deployment fails
**Solution:**
- Check quota limits
- Verify project permissions
- Check service account permissions

### Service Returns 500 Errors

**Issue:** Service crashes or returns errors
**Solution:**
```bash
# Check logs
gcloud run services logs read qbtojson --region us-central1 --limit 50

# Check service status
gcloud run services describe qbtojson --region us-central1
```

## 🔗 Integration

### Calling from Other Services

```javascript
// Example: JavaScript/Node.js
const response = await fetch('https://qbtojson-xxx-uc.a.run.app/api/convert/accounts', {
  method: 'POST',
  body: formData
});
const data = await response.json();
```

```python
# Example: Python
import requests

url = 'https://qbtojson-xxx-uc.a.run.app/api/convert/accounts'
files = {'file': open('accounts.csv', 'rb')}
response = requests.post(url, files=files)
data = response.json()
```

## 📚 API Endpoints

After deployment, these endpoints will be available:

- `GET /health` - Health check
- `GET /api/info` - API documentation
- `POST /api/convert/accounts` - Convert Chart of Accounts
- `POST /api/convert/balance-sheet` - Convert Balance Sheet
- `POST /api/convert/profit-loss` - Convert Profit & Loss
- `POST /api/convert/trial-balance` - Convert Trial Balance
- `POST /api/convert/cash-flow` - Convert Cash Flow
- `POST /api/convert/general-ledger` - Convert General Ledger
- `POST /api/accounts/load` - Load accounts for lookup
- `POST /api/accounts/lookup` - Look up account by name
- `POST /api/batch/*` - Batch processing endpoints

## 💡 Tips

1. **Use batch endpoints** for multiple files to reduce API calls
2. **Monitor costs** - Cloud Run charges per 100ms of execution time
3. **Set max-instances** to control costs in production
4. **Use Cloud Storage** for very large files instead of direct upload
5. **Enable Cloud CDN** if serving static responses frequently

## 🎉 Success!

Once deployed, your service will be available at:
```
https://qbtojson-7lqwugl3xa-uc.a.run.app
```

(The exact URL will be shown after deployment)

---

**Need Help?** Check the logs or open an issue in the repository.
