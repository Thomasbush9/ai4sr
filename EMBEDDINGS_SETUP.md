# Embeddings Configuration Guide

## Overview

The application uses embeddings for semantic search in the RAG system. You have two options:

1. **Azure OpenAI Embeddings** (recommended for production)
2. **OpenAI Embeddings** (fallback, works out of the box)

The system automatically tries Azure first, then falls back to OpenAI if Azure is unavailable.

## Option 1: Azure Embeddings (Recommended)

### Setup

1. Grant permissions on Cognitive Services resource (see `SETUP_AZURE_EMBEDDINGS.md`)
2. Configure in `.env`:
   ```bash
   AZURE_EXISTING_AIPROJECT_ENDPOINT=https://...
   AZURE_OPENAI_DIRECT_ENDPOINT=https://oai-ai4sr.cognitiveservices.azure.com
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small
   ```

### Advantages
- Uses your Azure subscription
- No additional API costs
- Integrated with your Azure infrastructure

## Option 2: OpenAI Embeddings (Fallback)

### Setup

Simply add to `.env`:
```bash
OPENAI_KEY=sk-your-openai-api-key-here
```

That's it! The system will automatically use OpenAI if Azure fails.

### Advantages
- Works immediately (no Azure permissions needed)
- Good for testing and development
- Simple setup

### Cost
- OpenAI charges per token for embeddings
- Check [OpenAI Pricing](https://openai.com/pricing) for current rates

## Automatic Fallback

The system works as follows:

1. **Try Azure first** - If Azure embeddings are configured and working
2. **Fall back to OpenAI** - If Azure fails (permissions, errors, etc.) and `OPENAI_KEY` is set
3. **Use DB queries** - If both fail (no vector search, but app still works)

## Testing

Test your configuration:

```bash
python test_embeddings.py
```

This will show which provider is being used.

## For Submission

**Recommended approach:**
- Document both options in your submission
- Users can choose based on their setup:
  - Azure users: Use Azure embeddings (no extra cost)
  - Others: Use OpenAI embeddings (simple setup)

**Example submission note:**
> "The application supports both Azure and OpenAI embeddings. Azure is tried first (if configured), with automatic fallback to OpenAI. For testing without Azure permissions, simply set `OPENAI_KEY` in your `.env` file."


