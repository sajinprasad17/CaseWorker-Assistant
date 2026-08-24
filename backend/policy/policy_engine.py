def evaluate_case(case):
    referral = case["referral"]
    requested_action = referral["requested_action"].lower()
    summary = referral["summary"].lower()

    policy_flags = []

    # --------------------------------------------------
    # SURPRISE CHALLENGE: UNDER-18 HOUSEHOLD
    # --------------------------------------------------
    if case["has_under_18"]:
        policy_flags.append({
            "rule": "ACA-2026/2 §3.9",
            "reason": (
                "Household contains a person under 18. "
                "AI triage note generation is not permitted."
            )
        })

    # --------------------------------------------------
    # §3.2 — Suspend / terminate / reinstate award
    # --------------------------------------------------
    if any(word in requested_action for word in [
        "suspend",
        "terminate",
        "reinstate"
    ]):
        policy_flags.append({
            "rule": "ACA-2026/1 §3.2",
            "reason": (
                "Suspending, terminating, or reinstating "
                "an award requires supervisor approval."
            )
        })

    # --------------------------------------------------
    # §3.4 — Change payment details
    # --------------------------------------------------
    if "payment details" in requested_action:
        policy_flags.append({
            "rule": "ACA-2026/1 §3.4",
            "reason": (
                "Changing payment details requires "
                "supervisor approval."
            )
        })

    # --------------------------------------------------
    # §3.1 — Change entitlement / award / eligibility
    # --------------------------------------------------
    if any(word in requested_action for word in [
        "change award",
        "change entitlement",
        "change eligibility",
        "alter award",
        "increase award",
        "decrease award"
    ]):
        policy_flags.append({
            "rule": "ACA-2026/1 §3.1",
            "reason": (
                "Changing entitlement, award amount, "
                "or eligibility requires supervisor approval."
            )
        })

    # --------------------------------------------------
    # §3.7 — Findings about resident conduct
    # --------------------------------------------------
    conduct_keywords = [
        "fraud",
        "undeclared employment",
        "misrepresentation",
        "false information",
        "false statement"
    ]

    if any(
        keyword in summary or keyword in requested_action
        for keyword in conduct_keywords
    ):
        policy_flags.append({
            "rule": "ACA-2026/1 §3.7",
            "reason": (
                "Making a factual finding about resident "
                "conduct requires human review."
            )
        })

    # --------------------------------------------------
    # Determine overall status
    # --------------------------------------------------

    if any(flag["rule"] == "ACA-2026/2 §3.9" for flag in policy_flags):
        status = "CASEWORKER_HANDOFF"
        triage_allowed = False
        requires_human = True

    elif policy_flags:
        status = "ESCALATION"
        triage_allowed = False
        requires_human = True

    else:
        status = "READY_FOR_TRIAGE"
        triage_allowed = True
        requires_human = False

    return {
        "status": status,
        "triage_allowed": triage_allowed,
        "requires_human": requires_human,
        "policy_flags": policy_flags
    }