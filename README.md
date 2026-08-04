# AI Lead-Qualification Agent (Powered by Gemini 2.5)

> Turn raw, unstructured inbound leads into ranked, actionable sales intelligence — automatically.

## Overview

The AI Lead-Qualification Agent is a lightweight Python automation pipeline that transforms unstructured client inquiries into structured, sales-ready intelligence. It ingests incoming client data from a CSV source, dynamically parses each record's business context, and routes it through Google's **Gemini 2.5 Flash** model for evaluation.

Every response returned by the model is constrained to a strict **Pydantic schema**, guaranteeing that priority ratings, justifications, and follow-up content are always well-formed and machine-readable — never free-form text that needs to be parsed or guessed at downstream. Based on the evaluated **priority metric** (`High`, `Medium`, or `Low`), the agent automatically routes each lead and, for high-value opportunities, drafts a highly personalized, professional follow-up sales email referencing the lead's specific business type, stated need, and budget.

The result is a fully compiled, structured JSON ledger of every lead — ready to feed into a CRM, a sales dashboard, or a human review queue.

**Key capabilities:**

- 🔍 **Dynamic parsing** of arbitrary inbound lead data (name, business type, budget, and free-text message)
- 🧱 **Schema-enforced output** via Pydantic + Gemini Structured Outputs — no brittle regex or manual JSON parsing
- 🚦 **Priority routing** — automatic `High` / `Medium` / `Low` triage based on budget clarity and stated need
- ✉️ **Automated email drafting** — a tailored, professional follow-up email is generated for every `High`-priority lead
- 🛡️ **Resilient by design** — automatic exponential-backoff retries on transient API errors (`429`, `5xx`) and graceful, non-fatal error handling per lead
- 📊 **Auditable output** — every run produces a durable JSON tracking log for downstream reporting

---

## System Architecture

```
┌────────────────────┐        ┌──────────────────────────┐        ┌───────────────────────┐
│  CSV / Data Stream  │  ───▶  │  Gemini 2.5 Flash         │  ───▶  │  JSON Tracking Logs    │
│  (leads.csv)        │        │  Evaluation Engine        │        │  (qualified_leads.json)│
│                      │        │                           │        │                        │
│  Name, Business      │        │  • Pydantic schema        │        │  • priority             │
│  Type, Budget,        │        │    enforcement            │        │  • justification        │
│  Message              │        │  • Priority triage        │        │  • follow_up_email      │
│                      │        │  • Email drafting         │        │  • status / error       │
└────────────────────┘        └──────────────────────────┘        └───────────────────────┘
```

| Stage | Responsibility |
|---|---|
| **1. Ingestion** | `pandas` reads `leads.csv`, normalizing each row into a structured lead record. |
| **2. Evaluation** | Each lead is sent to `gemini-2.5-flash` with a system prompt instructing the model to triage priority and, when warranted, draft outreach copy. The response is constrained via a `pydantic.BaseModel` passed as `response_schema`, so the SDK returns a validated Python object — not raw text. |
| **3. Resilience layer** | Transient failures (`429` rate limits, `5xx` server errors) are retried with exponential backoff. Non-retryable errors (e.g. invalid credentials) fail fast; per-lead errors are logged and skipped without halting the batch. |
| **4. Persistence** | The fully compiled array of evaluated leads — including status metadata for any failures — is written to `qualified_leads.json` for downstream consumption. |

---

## Installation

### Prerequisites

- Python 3.10+
- A [Google AI Studio](https://aistudio.google.com/apikey) API key for the Gemini API

### 1. Clone the repository

```bash
git clone https://github.com/wolfwarrior2403-alt/Python-based-AI-Lead-Qualification-Agent.git
cd Python-based-AI-Lead-Qualification-Agent
```

### 2. (Recommended) Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `google-genai` | Official Google SDK for calling the Gemini API |
| `pydantic` | Schema definition and validation for structured model output |
| `pandas` | CSV ingestion and lead data handling |
| `python-dotenv` | Loads environment variables from a local `.env` file |

### 4. Configure environment variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API key:

```env
GEMINI_API_KEY=your-api-key-here
```

> ⚠️ `.env` is git-ignored by default. Never commit real API keys to version control.

### 5. Run the agent

```bash
python gemini_agent.py
```

You'll see live progress in the terminal as each lead is analyzed:

```
Loaded 5 leads from leads.csv

[1/5] Analyzing lead: Sarah Chen (E-commerce (Fashion Retail))...
    -> Priority: High - follow-up email drafted
[2/5] Analyzing lead: Mike (not sure)...
    -> Priority: Low - no email needed
...

Done. 5/5 leads analyzed. Results saved to qualified_leads.json
```

Results are written to **`qualified_leads.json`** in the project root.

---

## Input / Output Reference

**Input** (`leads.csv`) — one row per lead:

| Column | Description |
|---|---|
| `Name` | Lead's full name |
| `Email` | Lead's contact email |
| `Business_Type` | Industry or business category |
| `Budget` | Stated or implied budget |
| `Message` | Free-text inquiry from the lead |

**Output** (`qualified_leads.json`) — one object per lead:

```json
{
  "name": "Sarah Chen",
  "email": "sarah.chen@brightpeak.com",
  "business_type": "E-commerce (Fashion Retail)",
  "budget": "$15,000/month",
  "message": "We need a full Shopify Plus migration...",
  "priority": "High",
  "justification": "Clear, substantial budget and a specific, urgent need.",
  "follow_up_email": "Subject: ...\n\nDear Sarah, ...",
  "status": "success"
}
```

Leads that fail evaluation (e.g. due to a rate limit or an upstream error) are still included in the output with `"status": "error"` and an `"error"` code, so no lead is ever silently dropped.

---

## Testing

A unit test suite (`test_agent.py`) validates the CSV loader, prompt construction, and response-parsing logic against mocked API responses — no live API key or network access required:

```bash
python test_agent.py -v
```

---

## License

This project is released under the **MIT License** — free to use, modify, and distribute, including for commercial purposes, provided the original copyright notice is retained. See below.

```
MIT License

Copyright (c) 2026 [Your Name or Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**For proprietary / client-engagement use:** if this project is being delivered as bespoke work for a specific client rather than distributed as open source, replace the section above with a closed, all-rights-reserved notice, e.g.:

```
Copyright (c) 2026 [Your Name or Organization]. All rights reserved.

This software and associated documentation are the confidential and
proprietary property of [Client/Organization Name]. Unauthorized copying,
distribution, or use of this software, via any medium, is strictly
prohibited without prior written permission.
```

Choose whichever license text applies to your use case and remove the other.
