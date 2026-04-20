# Abbott CONNECTA — AI Coaching Analytics Platform

## Overview
Production-grade AI coaching analytics platform built with FastAPI, LangGraph, and Azure-native services.

## Architecture
- **FastAPI** backend on Azure Container Apps
- **LangGraph** multi-agent orchestration (Supervisor → Retrieval/Coaching/Analytics/Recommendation)
- **Azure Functions** for CSV ingestion pipeline
- **Azure AI Search** for vector + semantic search
- **Azure OpenAI** (GPT-4o + text-embedding-3-large)
- **PostgreSQL** for relational data
- **Redis** for caching
- **Azure Service Bus** for async messaging

## Quick Start

### Prerequisites
- Python 3.12+
- Azure CLI
- Docker

### Local Development
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Configure local environment
uvicorn app.main:app --reload --port 8000
Deploy Infrastructure
az deployment group create \
  --resource-group connecta-rg \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.parameters.json
  
API Endpoints
Method	    Path	                        Description
POST	/api/v1/chat/	                Chat with AI coaching assistant
POST	/api/v1/chat/stream	            Streaming chat response
POST	/api/v1/upload/csv	            Upload CSV for ingestion
GET	    /api/v1/upload/status/{id}	    Check ingestion status
GET	    /api/v1/history/sessions	    List conversation sessions
GET	    /api/v1/history/sessions/{id}	Get session messages
POST	/api/v1/auth/validate	        Validate Azure AD token
GET	    /api/v1/auth/me	                Get current user profile
GET	    /health                     	Health check

Security
-- Azure AD (Entra ID) SSO authentication
-- Managed Identity for all Azure service access
-- Azure Key Vault for all secrets
-- RBAC-based authorization
-- Content Safety filtering on all AI responses
-- PII redaction
---

This completes **every single file** referenced in the project structure. Every `__init__.py`, every service, every repository, every model, every middleware, every Bicep module, every CI/CD workflow, every configuration file, and the README are now fully implemented.