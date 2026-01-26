# Azure AI Foundry Migration - Quick Start

**Branch:** `azure-migration-and-auth`

## What's Done ✅

- ✅ Migrated all 7 agents from OpenAI to Azure AI Foundry
- ✅ Removed exposed API keys
- ✅ Configured Azure authentication with `az login`
- ✅ Ready for Microsoft user authentication

## Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Authenticate with Azure
```bash
az login
```
Follow browser prompts to sign in.

### 3. Configure Environment
Your `.env` should have:
```bash
AZURE_EXISTING_AIPROJECT_ENDPOINT=<your-project-endpoint>
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
```

### 4. Grant Permissions (Admin Required)

**Admin:** Grant this role in [Azure Portal](https://portal.azure.com):
- **Resource**: Your AI Project
- **Role**: `Cognitive Services OpenAI User`
- **User**: The user who needs access

**Quick command:**
```bash
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee <user-email> \
  --scope "<your-ai-project-resource-id>"
```

### 5. Test
```bash
python test_azure_setup.py
```

Expected output:
```
✓ Azure AI Project client created
✓ Agent ready: ai4sr-agent
✓ Chat successful!
```

## Current Status

✅ **Code**: Fully migrated
✅ **Authentication**: Working (`az login`)
❌ **Permissions**: Waiting for admin

## Quick Test (No permissions needed)
```bash
# Just verify connection
python -c "
from agents.azure_config import get_project_client
client = get_project_client()
print('✓ Connected to Azure AI Project')
"
```

## Start the App
Once permissions are granted:
```bash
python webapp/app.py
```
Visit: http://localhost:5000

## Files Changed

**Core:**
- `agents/azure_config.py` - Azure AI Foundry integration
- All 7 agent files - Use Azure instead of OpenAI

**Config:**
- `.env` - Azure project endpoint
- `requirements.txt` - Added `azure-ai-projects`, `azure-identity`

**Docs:**
- `test_azure_setup.py` - Automated testing
- This file

## Troubleshooting

### "PermissionDenied" error
→ Admin needs to grant role (see step 4)

### "Azure CLI not found"
```bash
brew install azure-cli
az login
```

### "Module not found: azure.ai"
```bash
pip install --pre azure-ai-projects azure-identity
```

## Next Steps

1. **Admin grants permissions** (5 min)
2. **Test works** → `python test_azure_setup.py`
3. **Add Microsoft user auth** (optional, for end users)
4. **Deploy to production**

---

**Questions?** See detailed docs:
- `ADMIN_SETUP_REQUIRED.md` - Permission details
- `CREDENTIALS_GUIDE.md` - Authentication options
- `SETUP_AZURE.md` - Full migration guide
