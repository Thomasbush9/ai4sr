# Admin Setup Required

## Current Status

✅ Code migration complete
✅ User authenticated (`bushth@ext.euda.europa.eu`)
❌ Permissions needed to use Azure AI Foundry

## Required Permissions

User `bushth@ext.euda.europa.eu` needs these permissions on the AI Project:

### Resource
- **Project**: `oai-ai4sr-project`
- **Resource ID**: `/subscriptions/ebdbbfdb-a6d3-4bff-a72a-91580614d95a/resourceGroups/rg-ai4sr/providers/Microsoft.CognitiveServices/accounts/oai-ai4sr/projects/oai-ai4sr-project`

### Required Role
**Cognitive Services OpenAI Contributor**

This role includes:
- `Microsoft.CognitiveServices/accounts/AIServices/agents/write` (create/manage agents)
- `Microsoft.CognitiveServices/accounts/AIServices/agents/read` (read agents)
- `Microsoft.CognitiveServices/accounts/AIServices/connections/read` (read connections)

## How Admin Can Grant Access

### Via Azure Portal
1. Navigate to the AI Project in Azure Portal
2. Go to **Access Control (IAM)**
3. Click **Add role assignment**
4. Select role: **Cognitive Services OpenAI Contributor**
5. Assign to: `bushth@ext.euda.europa.eu`
6. Save

### Via Azure CLI
```bash
az role assignment create \
  --role "Cognitive Services OpenAI Contributor" \
  --assignee bushth@ext.euda.europa.eu \
  --scope "/subscriptions/ebdbbfdb-a6d3-4bff-a72a-91580614d95a/resourceGroups/rg-ai4sr/providers/Microsoft.CognitiveServices/accounts/oai-ai4sr/projects/oai-ai4sr-project"
```

## Alternative: Pre-create an Agent

If you can't grant full permissions, admin can:

1. Create an agent in the AI Project portal with these settings:
   - **Name**: `ai4sr-agent`
   - **Model**: `gpt-4o-mini` (or your deployment name)
   - **Instructions**: "You are an AI assistant helping with systematic literature reviews."

2. Grant user **read-only** access:
   - Role: **Cognitive Services OpenAI User**

3. Update `.env` with agent ID:
   ```bash
   AZURE_EXISTING_AGENT_ID=<agent-id-from-portal>
   ```

## After Permissions are Granted

Wait 2-5 minutes for propagation, then test:

```bash
python test_azure_setup.py
```

Should see:
```
✓ Azure AI Project client created
✓ Agent ready: ai4sr-agent
✓ Chat successful!
```

## Documentation
- Permission guide: https://aka.ms/FoundryPermissions
- Azure AI Studio: https://ai.azure.com
