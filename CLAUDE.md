# 🔍 Systematic Review Assistant

> An AI-assisted toolkit for **systematic literature reviews** — from document ingestion to evidence synthesis, with humans firmly in the loop.

Built with **Claude Code** as a development partner to keep the codebase readable, reproducible, and review-friendly.

---

## 🧠 What this project does

This project supports **systematic and semi-systematic reviews** by automating the *boring but fragile* parts of the workflow:

- extract relevant documents from keywords (expansion, pico search)
- start automatic screening 
- assisted screening with LLMs 
- RAG func 
- supported with DSPy

## ✅ Completed - Azure Migration

**Branch:** `azure-migration-and-auth`

### What Was Done:
- ✅ Created new branch
- ✅ Fixed security issues (removed exposed keys)
- ✅ Migrated all agents to Azure AI Foundry
- ✅ Added Microsoft authentication framework
- ✅ Full test suite

### Current Status:
- Code: Ready ✓
- Auth: Working (`az login`) ✓
- Permissions: Needs admin grant ⏳

See `README_AZURE_MIGRATION.md` for quick start. 


## Rules:

- Behave like a senior software eng. 
- be very specific in your change and rememer to git 
- do not add boilerplate code. 
- the goal is to support microsoft azure and auth, not perfect behavior . 
