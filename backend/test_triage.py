from ai.triage_service import generate_triage_note
from main import get_case

case = get_case("RF-2026-0413")

result = generate_triage_note(case)

print("\n===== AI TRIAGE RESULT =====\n")
print(result)