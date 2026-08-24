import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generate_triage_note(case):
    referral = case["referral"]
    resident = case["resident"]
    household = case["household"]
    events = case["events"]

    prompt = f"""
You are an AI assistant helping a benefits caseworker.

Your job is ONLY to prepare a draft triage note.
You must NOT make decisions about eligibility, award amounts,
suspension, termination, reinstatement, payment details,
or findings of fraud or misconduct.

The policy engine has already determined that this case
is allowed to receive an AI-generated draft.

CASE INFORMATION

Referral:
{json.dumps(referral, indent=2)}

Resident:
{json.dumps(resident, indent=2)}

Household:
{json.dumps(household, indent=2)}

Previous case events:
{json.dumps(events, indent=2)}

Prepare a concise triage note containing:

1. Summary
2. Key facts
3. Reason for referral
4. Suggested next step for the caseworker
5. Questions or information the caseworker may need to verify

Important:
-Do not make a final decision.

-Do not recommend changing, increasing, decreasing,
suspending, terminating, or reinstating an award.

-Do not recommend changing eligibility.

-Do not recommend changing payment details.

-Do not make findings about fraud, misconduct,
misrepresentation, or resident fault.

-Do not instruct the caseworker to perform a restricted action.

Your suggested next step must be limited to:
- reviewing the referral,
- verifying information,
- gathering missing evidence,
- contacting the resident where permitted,
- documenting information,
- or referring the case to the appropriate human decision-maker.

Clearly distinguish facts from suggestions.

Return ONLY valid JSON in this format:

{{
  "summary": "...",
  "key_facts": [
    "...",
    "..."
  ],
  "reason_for_referral": "...",
  "suggested_next_step": "...",
  "questions_for_caseworker": [
    "...",
    "..."
  ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()

    # Remove markdown code fences if Gemini adds them
    if text.startswith("```json"):
        text = text[7:]

    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())