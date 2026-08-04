"""AI Lead Qualification Agent.

Reads leads from leads.csv, asks Gemini to score and justify each lead's
priority, drafts a personalized follow-up email for High-priority leads,
and writes the results to qualified_leads.json.
"""

import json
import os
import random
import sys
import time
from typing import Literal, Optional

import pandas as pd
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODEL = "gemini-2.5-flash"
INPUT_CSV = "leads.csv"
OUTPUT_JSON = "qualified_leads.json"
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 3.0
DELAY_BETWEEN_LEADS_SECONDS = 2.0


class LeadAnalysis(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    justification: str
    follow_up_email: Optional[str] = None


SYSTEM_PROMPT = """You are a lead qualification analyst for a web/software development agency.

For each lead, assess Budget and Message to assign a priority:
- High: clear, substantial budget and a specific, well-defined need or timeline.
- Medium: some budget or need signal, but missing clarity on one of the two.
- Low: vague or absent budget, and a vague or exploratory message.

When priority is High, also draft a short, highly personalized follow-up email (with a subject line) that
references the lead's specific business type, stated need, and budget, and proposes a clear next step.
For Medium/Low leads, leave follow_up_email as null."""


def load_leads(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        print(f"Error: input file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    return pd.read_csv(csv_path)


def build_user_message(lead: pd.Series) -> str:
    return (
        f"Name: {lead['Name']}\n"
        f"Email: {lead['Email']}\n"
        f"Business Type: {lead['Business_Type']}\n"
        f"Budget: {lead['Budget']}\n"
        f"Message: {lead['Message']}"
    )


def _unusable_response_reason(response: genai_types.GenerateContentResponse) -> str:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        return f"blocked ({feedback.block_reason})"
    candidates = getattr(response, "candidates", None) or []
    if candidates and getattr(candidates[0], "finish_reason", None):
        return f"finish_reason={candidates[0].finish_reason}"
    return "unknown reason"


def analyze_lead(client: genai.Client, lead: pd.Series) -> LeadAnalysis:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=build_user_message(lead),
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=LeadAnalysis,
                ),
            )
            break
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            retryable = e.code == 429 or e.code >= 500
            if not retryable or attempt == MAX_RETRIES:
                raise
            delay = RETRY_BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 1)
            print(f"  {e.code} error — retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...",
                  file=sys.stderr)
            time.sleep(delay)

    if response.parsed is None:
        raise RuntimeError(f"Gemini returned no usable content ({_unusable_response_reason(response)}).")

    return response.parsed


def main() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print(
            "Error: no API credentials found. Set GEMINI_API_KEY in your environment "
            "or a .env file (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    leads_df = load_leads(INPUT_CSV)

    results = []
    for i, (_, lead) in enumerate(leads_df.iterrows()):
        if i > 0:
            time.sleep(DELAY_BETWEEN_LEADS_SECONDS)

        record = {
            "name": lead["Name"],
            "email": lead["Email"],
            "business_type": lead["Business_Type"],
            "budget": lead["Budget"],
            "message": lead["Message"],
        }

        print(f"Analyzing lead: {lead['Name']}...")
        try:
            analysis = analyze_lead(client, lead)
            record["priority"] = analysis.priority
            record["justification"] = analysis.justification
            record["follow_up_email"] = analysis.follow_up_email
            record["status"] = "success"
        except genai_errors.ClientError as e:
            message = str(e.message or "")
            if e.code in (401, 403) or "API key not valid" in message or "API_KEY_INVALID" in message:
                print("Error: invalid API key. Aborting.", file=sys.stderr)
                sys.exit(1)
            if e.code == 429:
                print("  Rate limited — skipping this lead.", file=sys.stderr)
                record.update(priority=None, justification=None, follow_up_email=None,
                               status="error", error="rate_limited")
            else:
                print(f"  API error ({e.code}): {e.message} — skipping this lead.", file=sys.stderr)
                record.update(priority=None, justification=None, follow_up_email=None,
                               status="error", error=f"client_error_{e.code}")
        except genai_errors.ServerError as e:
            print(f"  Server error ({e.code}): {e.message} — skipping this lead.", file=sys.stderr)
            record.update(priority=None, justification=None, follow_up_email=None,
                           status="error", error=f"server_error_{e.code}")
        except RuntimeError as e:
            print(f"  Unexpected response — skipping this lead: {e}", file=sys.stderr)
            record.update(priority=None, justification=None, follow_up_email=None,
                           status="error", error=str(e))

        results.append(record)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    succeeded = sum(1 for r in results if r["status"] == "success")
    print(f"\nDone. {succeeded}/{len(results)} leads analyzed. Results saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
