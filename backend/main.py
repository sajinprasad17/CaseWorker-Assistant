from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from dotenv import load_dotenv
from datetime import date
from backend.policy.policy_engine import evaluate_case
from backend.ai.triage_service import generate_triage_note

load_dotenv()

app = FastAPI(title="CaseGuard AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "history_data.json"
)

with open(HISTORY_FILE, "r", encoding="utf-8") as file:
    HISTORY_DATA = json.load(file)

# Find the data folder relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERRAL_FILE = os.path.join(BASE_DIR, "data", "referral-queue.json")

def calculate_age(date_of_birth: str) -> int:
    birth_date = date.fromisoformat(date_of_birth)
    today = date.today()

    age = today.year - birth_date.year

    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


def load_referrals():
    with open(REFERRAL_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
def root():
    return {"message": "CaseGuard AI backend is running"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/referrals")
def get_referrals():
    referrals = load_referrals()

    return {
        "count": len(referrals),
        "referrals": referrals
    }


@app.get("/api/referrals/{referral_id}")
def get_referral(referral_id: str):
    referrals = load_referrals()

    for referral in referrals:
        if referral["referral_id"] == referral_id:
            return referral

    raise HTTPException(
        status_code=404,
        detail="Referral not found"
    )


@app.get("/api/residents/{resident_id}")
def get_resident(resident_id: str):

    resident = HISTORY_DATA.get(resident_id)

    if resident is None:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return resident


@app.get("/api/residents/{resident_id}/household")
def get_household(resident_id: str):

    resident = HISTORY_DATA.get(resident_id)

    if resident is None:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return {
        "resident_ref": resident["resident_ref"],
        "household": resident["household"]
    }


@app.get("/api/residents/{resident_id}/events")
def get_events(resident_id: str):

    resident = HISTORY_DATA.get(resident_id)

    if resident is None:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return {
        "resident_ref": resident["resident_ref"],
        "events": resident["events"]
    }


@app.get("/api/cases/{referral_id}/decision")
def get_case_decision(referral_id: str):

    # Get the complete case
    case = get_case(referral_id)

    # Evaluate policy
    decision = evaluate_case(case)

    return {
        "referral_id": referral_id,
        "decision": decision
    }


@app.get("/api/cases/{referral_id}")
def get_case(referral_id: str):

    # Find referral
    referrals = load_referrals()

    referral = next(
        (
            r for r in referrals
            if r["referral_id"] == referral_id
        ),
        None
    )

    if referral is None:
        raise HTTPException(
            status_code=404,
            detail="Referral not found"
        )

    resident_id = referral["resident_ref"]

    # Get resident directly from local history data
    resident = HISTORY_DATA.get(resident_id)

    if resident is None:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    # Remove duplicated household/events from resident object
    resident = resident.copy()
    resident.pop("household", None)
    resident.pop("events", None)

    # Get household
    household = HISTORY_DATA[resident_id]["household"]

    household_with_age = []

    for member in household:
        age = calculate_age(member["date_of_birth"])

        household_with_age.append({
            **member,
            "age": age
        })

    # Get events
    events = HISTORY_DATA[resident_id]["events"]

    # Detect under-18 household member
    has_under_18 = any(
        member["age"] < 18
        for member in household_with_age
    )

    return {
        "referral": referral,
        "resident": resident,
        "household": household_with_age,
        "events": events,
        "has_under_18": has_under_18
    }


@app.get("/api/process-queue")
def process_queue():
    referrals = load_referrals()

    results = []

    for referral in referrals:
        referral_id = referral["referral_id"]

        try:
            # Build the complete case
            case = get_case(referral_id)

            # Apply policy rules
            decision = evaluate_case(case)

            results.append({
                "referral_id": referral_id,
                "resident_ref": referral["resident_ref"],
                "urgency": referral["urgency"],
                "requested_action": referral["requested_action"],
                "status": decision["status"],
                "triage_allowed": decision["triage_allowed"],
                "requires_human": decision["requires_human"],
                "policy_flags": decision["policy_flags"]
            })

        except Exception as e:
            results.append({
                "referral_id": referral_id,
                "status": "ERROR",
                "triage_allowed": False,
                "requires_human": True,
                "reason": str(e),
                "policy_reference": None
            })

    # Calculate summary
    ready = sum(
        1 for r in results
        if r["status"] == "READY_FOR_TRIAGE"
    )

    escalations = sum(
        1 for r in results
        if r["status"] == "ESCALATION"
    )

    handoffs = sum(
        1 for r in results
        if r["status"] == "CASEWORKER_HANDOFF"
    )

    errors = sum(
        1 for r in results
        if r["status"] == "ERROR"
    )

    return {
        "total": len(results),
        "ready_for_triage": ready,
        "escalations": escalations,
        "caseworker_handoffs": handoffs,
        "errors": errors,
        "cases": results
    }

@app.post("/api/cases/{referral_id}/triage")
def generate_case_triage(referral_id: str):

    # 1. Build the complete case
    case = get_case(referral_id)

    # 2. Run policy checks FIRST
    decision = evaluate_case(case)

    # 3. Never allow AI to process blocked cases
    if not decision["triage_allowed"]:
        return {
            "referral_id": referral_id,
            "status": decision["status"],
            "triage_allowed": False,
            "requires_human": decision["requires_human"],
            "policy_flags": decision["policy_flags"],
            "triage_note": None
        }

    # 4. Policy allows AI → generate draft
    triage_note = generate_triage_note(case)

    return {
        "referral_id": referral_id,
        "status": "AI_TRIAGE_COMPLETED",
        "triage_allowed": True,
        "requires_human": False,
        "policy_flags": [],
        "triage_note": triage_note
    }
