from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import json
import os
from datetime import date
from policy.policy_engine import evaluate_case
from ai.triage_service import generate_triage_note


app = FastAPI(title="CaseGuard AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_API = "http://127.0.0.1:8083"

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


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/referrals")
def get_referrals():
    referrals = load_referrals()

    return {
        "count": len(referrals),
        "referrals": referrals
    }


@app.get("/referrals/{referral_id}")
def get_referral(referral_id: str):
    referrals = load_referrals()

    for referral in referrals:
        if referral["referral_id"] == referral_id:
            return referral

    raise HTTPException(
        status_code=404,
        detail="Referral not found"
    )


@app.get("/residents/{resident_id}")
def get_resident(resident_id: str):
    response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}"
    )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return response.json()


@app.get("/residents/{resident_id}/household")
def get_household(resident_id: str):
    response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}/household"
    )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return response.json()


@app.get("/residents/{resident_id}/events")
def get_events(resident_id: str):
    response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}/events"
    )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    return response.json()


@app.get("/cases/{referral_id}/decision")
def get_case_decision(referral_id: str):

    # Get the complete case
    case = get_case(referral_id)

    # Evaluate policy
    decision = evaluate_case(case)

    return {
        "referral_id": referral_id,
        "decision": decision
    }


@app.get("/cases/{referral_id}")
def get_case(referral_id: str):
    # Find the referral
    referrals = load_referrals()

    referral = next(
        (r for r in referrals if r["referral_id"] == referral_id),
        None
    )

    if referral is None:
        raise HTTPException(
            status_code=404,
            detail="Referral not found"
        )

    # Get the resident ID from the referral
    resident_id = referral["resident_ref"]

    # Get resident information
    resident_response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}"
    )

    if resident_response.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    resident = resident_response.json()
    resident.pop("household", None)
    resident.pop("events", None)

    # Get household information
    household_response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}/household"
    )

    if household_response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve household information"
        )

    household = household_response.json()["household"]
    # Calculate age for every household member
    household_with_age = []

    for member in household:
        age = calculate_age(member["date_of_birth"])

        household_with_age.append({
            **member,
            "age": age
        })
    # Check whether household contains anyone under 18
    has_under_18 = any(
    member["age"] < 18
    for member in household_with_age
    )
    

    # Get previous case events
    events_response = requests.get(
        f"{HISTORY_API}/residents/{resident_id}/events"
    )

    if events_response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve case events"
        )

    events = events_response.json()["events"]

    # Return the complete digital case
    return {
        "referral": referral,
        "resident": resident,
        "household": household_with_age,
        "events": events,
        "has_under_18": has_under_18
    }

@app.get("/process-queue")
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

@app.post("/cases/{referral_id}/triage")
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
