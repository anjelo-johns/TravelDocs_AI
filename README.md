# TravelDocs AI — Microsoft Azure AI Foundry & Travel Vault

A Flask travel documentation application fully integrated with **Microsoft Azure AI Foundry** (and Azure OpenAI Service) for automated travel document extraction, expiry monitoring, cognitive document summarization, and an intelligent travel copilot.

---

## 🚀 Features

- **Microsoft Azure AI Foundry Integration**: Native support for models deployed in Azure AI Foundry (Project endpoints, Serverless / Model Catalog APIs, and Azure OpenAI Service).
- **Automated Document Intelligence**: Analyzes boarding passes, flight confirmations, hotel bookings, visas, and passports. Extracts:
  - Document Title & Type (Passport, Visa, Flight Ticket, Train Ticket, Hotel Booking, etc.)
  - PNR / Confirmation / Document Number
  - Issue & Expiry Dates
  - AI Bulleted Summary (terminal, baggage, check-in rules, emergency contacts)
  - Critical Traveler Alerts & Warnings (e.g. 6-month passport validity rules)
- **PDF & File Text Extraction**: Direct extraction from uploaded PDF itineraries and ticket files using `pypdf`.
- **Azure AI Copilot**: Interactive travel assistant that knows your upcoming trips, stored documents, and expiry warnings.
- **Graceful Fallback Mode**: Intelligent local heuristic extraction and simulated copilot if credentials are not yet configured.
- **Live Connection Diagnostics**: One-click connection test to verify Microsoft Azure AI Foundry endpoint latency and model availability.

---

## ⚙️ Microsoft Azure AI Foundry Configuration

Edit `.env` (or copy `.env.example` to `.env`):

```env
SECRET_KEY=change-me-to-a-secure-secret-key
HOST=0.0.0.0
PORT=5000
FLASK_DEBUG=0

# Microsoft Azure AI Foundry Configuration
MODEL_PROVIDER=azure_ai_foundry
MODEL_ENDPOINT=https://<your-foundry-resource>.services.ai.azure.com/models
MODEL_DEPLOYMENT=<your-model-deployment-name>
MODEL_API_KEY=<your-foundry-api-key>
MODEL_API_VERSION=2024-10-21
```

### Where to get these from Microsoft Azure AI Foundry:
1. Open the [Azure AI Foundry Portal](https://ai.azure.com/).
2. Select your Project &rarr; **Models + endpoints** (or **Deployments**).
3. Click on your deployed model (e.g., `gpt-4o`, `phi-4`, `llama-3.3`, or `deepseek-r1`):
   - `MODEL_ENDPOINT`: copy the **Target URI** (e.g., `https://<project>.services.ai.azure.com/models` or `https://<model>.<region>.models.ai.azure.com`).
   - `MODEL_API_KEY`: copy **Key** (Primary or Secondary API Key).
   - `MODEL_DEPLOYMENT`: the deployment name you assigned to your model.

---

## 💻 Local Windows Setup

```powershell
cd E:\TravelDocs_AI_Deployment
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck and model status |
| `GET` | `/api/model/status` | Current Azure OpenAI deployment configuration |
| `POST` | `/api/model/test-connection` | Pings Azure OpenAI deployment and returns latency |
| `POST` | `/api/model/analyze` | Analyzes travel text or uploaded file with Azure OpenAI |
| `POST` | `/api/ai/chat` | Chat with Azure Travel Copilot with full vault context |

---

## 🐳 Docker Deployment

```powershell
docker compose up --build
```
