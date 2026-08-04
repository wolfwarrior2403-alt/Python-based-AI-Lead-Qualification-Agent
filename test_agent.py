"""Unit tests for agent.py.

Runs offline — the Gemini API call in analyze_lead() is mocked, so no
API key or network access is required.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

import pandas as pd
from pydantic import ValidationError

from agent import LeadAnalysis, analyze_lead, build_user_message, load_leads


def make_lead(**overrides) -> pd.Series:
    defaults = {
        "Name": "Jane Doe",
        "Email": "jane@example.com",
        "Business_Type": "SaaS",
        "Budget": "$10,000/month",
        "Message": "We need a new dashboard by next quarter.",
    }
    defaults.update(overrides)
    return pd.Series(defaults)


def make_response(parsed=None, block_reason=None, finish_reason=None):
    """Build a fake google.genai GenerateContentResponse-like object."""
    response = MagicMock()
    response.parsed = parsed

    feedback = MagicMock()
    feedback.block_reason = block_reason
    response.prompt_feedback = feedback

    if finish_reason is not None:
        candidate = MagicMock()
        candidate.finish_reason = finish_reason
        response.candidates = [candidate]
    else:
        response.candidates = []

    return response


class LoadLeadsTests(unittest.TestCase):
    def test_reads_expected_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "leads.csv")
            pd.DataFrame([make_lead()]).to_csv(path, index=False)

            df = load_leads(path)

            self.assertEqual(len(df), 1)
            for col in ("Name", "Email", "Business_Type", "Budget", "Message"):
                self.assertIn(col, df.columns)

    def test_missing_file_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            load_leads("does_not_exist.csv")
        self.assertEqual(ctx.exception.code, 1)


class BuildUserMessageTests(unittest.TestCase):
    def test_includes_all_fields(self):
        lead = make_lead(Name="Sarah Chen", Budget="$15,000/month")
        message = build_user_message(lead)

        self.assertIn("Name: Sarah Chen", message)
        self.assertIn("Budget: $15,000/month", message)
        self.assertIn("Message: We need a new dashboard by next quarter.", message)


class AnalyzeLeadTests(unittest.TestCase):
    def test_parses_high_priority_response_with_email(self):
        parsed = LeadAnalysis(
            priority="High",
            justification="Clear budget and defined scope.",
            follow_up_email="Subject: Next steps\n\nHi Jane, ...",
        )
        client = MagicMock()
        client.models.generate_content.return_value = make_response(parsed=parsed)

        result = analyze_lead(client, make_lead())

        self.assertEqual(result.priority, "High")
        self.assertIsNotNone(result.follow_up_email)
        client.models.generate_content.assert_called_once()

    def test_parses_low_priority_response_without_email(self):
        parsed = LeadAnalysis(priority="Low", justification="Vague message, no budget.")
        client = MagicMock()
        client.models.generate_content.return_value = make_response(parsed=parsed)

        result = analyze_lead(client, make_lead(Budget="idk", Message="just looking"))

        self.assertEqual(result.priority, "Low")
        self.assertIsNone(result.follow_up_email)

    def test_blocked_response_raises_runtime_error(self):
        client = MagicMock()
        client.models.generate_content.return_value = make_response(block_reason="SAFETY")

        with self.assertRaises(RuntimeError):
            analyze_lead(client, make_lead())

    def test_unparsed_response_raises_runtime_error(self):
        client = MagicMock()
        client.models.generate_content.return_value = make_response(finish_reason="MAX_TOKENS")

        with self.assertRaises(RuntimeError):
            analyze_lead(client, make_lead())


class LeadAnalysisSchemaTests(unittest.TestCase):
    def test_accepts_valid_priority_values(self):
        for value in ("High", "Medium", "Low"):
            obj = LeadAnalysis(priority=value, justification="x")
            self.assertEqual(obj.priority, value)

    def test_rejects_invalid_priority(self):
        with self.assertRaises(ValidationError):
            LeadAnalysis(priority="Urgent", justification="x")

    def test_follow_up_email_defaults_to_none(self):
        obj = LeadAnalysis(priority="Low", justification="x")
        self.assertIsNone(obj.follow_up_email)


if __name__ == "__main__":
    unittest.main()
