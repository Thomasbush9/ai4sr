# Azure Credentials Setup Guide

## Two Types of Authentication

### 1. **Server → Azure** (Backend)
Your Flask server needs credentials to call Azure AI APIs.

**Options:**
- **Option A: Service Principal** (Production & Docker) - Set in `.env`
- **Option B: `az login`** (Local dev only, outside containers) - One-time CLI login

### 2. **User → Your App** (Frontend)
End users authenticate via Microsoft login in the browser.
**No `az login` required for users!**

---

## Setup for Server → Azure

### Option A: Service Principal (Recommended)

**Required for Docker containers!** Service principal credentials work automatically in containers without any manual authentication.

1. **Create a Service Principal** in Azure Portal:
   - Go to Azure Active Directory → App registrations → New registration
   - Name it: `ai4sr-service-principal`
   - Copy these values:
     - **Application (client) ID**
     - **Directory (tenant) ID**

2. **Create a Client Secret**:
   - Go to Certificates & secrets → New client secret
   - Copy the **secret value**

3. **Grant Access** to your AI Project:
   - Go to your AI Project in Azure Portal
   - Access Control (IAM) → Add role assignment
   - Role: "Cognitive Services OpenAI User"
   - Assign to your service principal

4. **Add to `.env`**:
   ```bash
   MICROSOFT_TENANT_ID=your-tenant-id
   MICROSOFT_CLIENT_ID=your-client-id
   MICROSOFT_CLIENT_SECRET=your-client-secret
   ```

   **Note:** Docker containers automatically load these from `.env` - no `az login` needed!

### Option B: Azure CLI (Local Dev Only)

**Only works outside Docker containers!** For local development on your machine.

Just run once:
```bash
az login
```

This stores credentials locally. **NOT for production or Docker containers!**

**Note:** If running in Docker, use Service Principal (Option A) instead.

---

## What End Users Need

**Nothing!** They just:
1. Visit your app
2. Click "Login with Microsoft"
3. Authenticate in browser

No CLI, no credentials files.

---

## Testing

```bash
# Test server credentials
python test_azure_setup.py

# Should show:
# ✓ Azure AI Projects credentials configured
# ✓ Chat completion successful
```

---

## Production Deployment

Use **Azure Managed Identity** (no credentials needed):
1. Deploy to Azure (App Service, Container Apps, etc.)
2. Enable Managed Identity
3. Grant it access to AI Project
4. Remove all credential env vars
5. DefaultAzureCredential will auto-detect it!
