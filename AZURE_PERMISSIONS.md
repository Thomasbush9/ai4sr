# Azure Permissions Required

## Current Issue

User `bushth@ext.euda.europa.eu` needs permissions to use the Azure AI Project.

## How to Grant Permissions

### Option 1: Azure Portal (Recommended)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your AI Project: **oai-ai4sr-project**
3. Click **Access Control (IAM)** in the left menu
4. Click **+ Add** → **Add role assignment**
5. Select role: **Cognitive Services OpenAI User**
6. Click **Next**
7. Click **+ Select members**
8. Search for: `bushth@ext.euda.europa.eu`
9. Select the user and click **Select**
10. Click **Review + assign**

### Option 2: Azure CLI

```bash
# Get your Azure AI Project resource ID (already in your .env)
RESOURCE_ID="/subscriptions/ebdbbfdb-a6d3-4bff-a72a-91580614d95a/resourceGroups/rg-ai4sr/providers/Microsoft.CognitiveServices/accounts/oai-ai4sr/projects/oai-ai4sr-project"

# Grant yourself the role
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee bushth@ext.euda.europa.eu \
  --scope $RESOURCE_ID
```

## Required Roles

For full functionality, assign these roles:

- **Cognitive Services OpenAI User** - Use AI models
- **Cognitive Services OpenAI Contributor** - Manage deployments (optional)

## Verify Permissions

After granting permissions, test again:

```bash
python test_azure_setup.py
```

## Troubleshooting

If you still get permission errors:

1. **Wait 5 minutes** - Permissions can take time to propagate
2. **Sign out and back in**: `az logout` then `az login`
3. **Check subscription**: Verify you're using the correct subscription
   ```bash
   az account show
   ```

## Documentation

Full guide: https://aka.ms/FoundryPermissions
