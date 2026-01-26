# Azure Migration Setup Guide

This guide will help you configure the AI4SR application to use Azure OpenAI and Microsoft Authentication.

## ✅ Migration Status

- **Code Migration**: Complete ✓
- **All Agents Migrated**: 7/7 ✓
- **Flask App**: Working ✓
- **Configuration Required**: Yes

## 📋 Prerequisites

1. **Azure OpenAI Service** access
2. **Microsoft Entra ID** (Azure AD) application (optional, for authentication)
3. Python 3.8+ environment

## 🔧 Configuration Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Azure OpenAI

Edit your `.env` file (see `.env.example` for template):

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-02-01
```

**How to get these values:**
- Go to [Azure Portal](https://portal.azure.com)
- Navigate to your Azure OpenAI resource
- Copy the **Endpoint** and **Key** from the "Keys and Endpoint" section
- Create deployments for:
  - A chat model (e.g., gpt-4o-mini)
  - An embedding model (e.g., text-embedding-3-small)

### 3. Configure Microsoft Authentication (Optional)

If you want to enable Microsoft account login:

```bash
# Microsoft Authentication
MICROSOFT_CLIENT_ID=your-app-client-id
MICROSOFT_CLIENT_SECRET=your-app-client-secret
MICROSOFT_TENANT_ID=your-tenant-id
MICROSOFT_REDIRECT_URI=http://localhost:5000/auth/callback
```

**How to register your app:**
1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click "New registration"
3. Set redirect URI to `http://localhost:5000/auth/callback`
4. After creation, copy the Client ID and Tenant ID
5. Create a client secret under "Certificates & secrets"

### 4. Configure Flask Secret Key

```bash
# Flask Configuration
FLASK_SECRET_KEY=your-random-secret-key-here
```

Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 🧪 Testing

Run the automated test suite:

```bash
python test_azure_setup.py
```

Expected output:
```
✓ PASS: agents
✓ PASS: flask
✓ PASS: chat (if Azure configured)
✓ PASS: embeddings (if Azure configured)
```

## 🚀 Running the Application

Start the Flask server:

```bash
python webapp/app.py
```

The app will be available at: `http://localhost:5000`

## 📝 What Changed

### Migrated Components

All agents now use Azure OpenAI instead of DSPy:

- ✅ `agents/screening.py` - Paper screening
- ✅ `agents/keyword_exp.py` - Keyword generation
- ✅ `agents/pico.py` - PICO expansion
- ✅ `agents/review_agent.py` - Paper review
- ✅ `agents/cold_start_agent.py` - Cold start labeling
- ✅ `agents/rag_agent.py` - RAG Q&A (including embeddings)
- ✅ `agents/orchestrator.py` - Workflow orchestration

### New Features

- **Azure OpenAI Integration**: Centralized client in `agents/azure_config.py`
- **Microsoft Authentication**: Login flow via `/auth/*` endpoints
- **Session Management**: Secure Flask sessions
- **Updated Endpoints**: `/api/test-azure-config` replaces `/api/test-openai`

### Security Improvements

- ✅ Removed exposed API keys from version control
- ✅ Added `.env.example` template
- ✅ Removed hardcoded personal emails
- ✅ Added session-based authentication

## 🔍 API Endpoint Changes

| Old Endpoint | New Endpoint | Notes |
|--------------|--------------|-------|
| `/api/test-openai` | `/api/test-azure-config` | Tests Azure OpenAI connection |
| N/A | `/auth/login` | Microsoft login |
| N/A | `/auth/callback` | OAuth callback |
| N/A | `/auth/logout` | Logout |
| N/A | `/auth/user` | Get current user |

## ⚠️ Migration Notes

1. **No DSPy**: All DSPy code has been removed. Agents use direct Azure OpenAI API calls.
2. **API Keys**: User-provided API keys in the frontend are no longer used. The app uses server-side Azure credentials.
3. **Embeddings**: RAG embeddings now use Azure OpenAI's embedding endpoint.
4. **Authentication**: Authentication is optional but recommended for production.

## 🐛 Troubleshooting

### "Azure OpenAI credentials not configured"
- Check that `.env` file exists and contains valid Azure credentials
- Verify credentials at: `python test_azure_setup.py`

### "Import Error: No module named 'msal'"
- Run: `pip install -r requirements.txt`

### "Authentication required" errors
- Either configure Microsoft auth or disable the `@require_auth` decorators in `webapp/routes.py`

### API Rate Limits
- Azure OpenAI has different rate limits than OpenAI
- Check your quota in Azure Portal

## 📞 Support

For issues:
1. Run `python test_azure_setup.py` and share output
2. Check Flask logs for errors
3. Verify Azure Portal credentials
4. Review `.env` configuration

## 🎯 Next Steps

1. ✅ Configure Azure OpenAI credentials
2. ✅ Run test suite
3. ✅ Start Flask app
4. Configure Microsoft auth (optional)
5. Deploy to production
6. Update frontend to use new endpoints
