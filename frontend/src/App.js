import React, { useEffect, useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function App() {
  const [queue, setQueue] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [triage, setTriage] = useState(null);

  const [loadingQueue, setLoadingQueue] = useState(true);
  const [loadingCase, setLoadingCase] = useState(false);
  const [loadingTriage, setLoadingTriage] = useState(false);
  const [error, setError] = useState("");

  // Load all referrals
  useEffect(() => {
    loadQueue();
  }, []);

  async function loadQueue() {
    try {
      setLoadingQueue(true);
      setError("");

      const response = await fetch(`${API_BASE}/process-queue`);

      if (!response.ok) {
        throw new Error("Failed to load referral queue");
      }

      const data = await response.json();
      setQueue(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingQueue(false);
    }
  }

  // Load a complete case
  async function selectCase(referralId) {
    try {
      setSelectedId(referralId);
      setCaseData(null);
      setTriage(null);
      setLoadingCase(true);
      setError("");

      const response = await fetch(
        `${API_BASE}/cases/${referralId}`
      );

      if (!response.ok) {
        throw new Error("Failed to load case");
      }

      const data = await response.json();
      setCaseData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingCase(false);
    }
  }

  // Ask Gemini to generate a triage note
  async function generateTriage() {
    if (!selectedId) return;

    try {
      setLoadingTriage(true);
      setTriage(null);
      setError("");

      const response = await fetch(
        `${API_BASE}/cases/${selectedId}/triage`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to generate triage");
      }

      const data = await response.json();
      setTriage(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingTriage(false);
    }
  }

  function statusClass(status) {
    if (status === "READY_FOR_TRIAGE") return "ready";
    if (status === "ESCALATION") return "escalation";
    if (status === "CASEWORKER_HANDOFF") return "handoff";
    return "";
  }

  function statusLabel(status) {
    if (status === "READY_FOR_TRIAGE") return "READY";
    if (status === "CASEWORKER_HANDOFF") return "HANDOFF";
    if (status === "ESCALATION") return "ESCALATION";
    return status;
  }

  if (loadingQueue) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Loading referral queue...</p>
      </div>
    );
  }

  return (
    <div className="app">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">C</div>
          <div>
            <h1>CaseGuard</h1>
            <span>AI Casework Assistant</span>
          </div>
        </div>

        <div className="sidebar-section">
          <span className="sidebar-label">WORKSPACE</span>

          <button className="nav-item active">
            <span>▦</span>
            Referral Queue
          </button>
        </div>

        <div className="sidebar-bottom">
          <div className="human-badge">
            <div className="status-dot"></div>
            Human oversight active
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main">
        <header className="topbar">
          <div>
            <h2>Referral Queue</h2>
            <p>
              Review incoming cases and AI-assisted triage.
            </p>
          </div>

          <button className="refresh-button" onClick={loadQueue}>
            ↻ Refresh
          </button>
        </header>

        {error && (
          <div className="error-banner">
            ⚠ {error}
          </div>
        )}

        {/* STAT CARDS */}
        {queue && (
          <section className="stats">
            <div className="stat-card">
              <span className="stat-label">TOTAL REFERRALS</span>
              <strong>{queue.total}</strong>
            </div>

            <div className="stat-card ready-card">
              <span className="stat-label">READY FOR TRIAGE</span>
              <strong>{queue.ready_for_triage}</strong>
            </div>

            <div className="stat-card escalation-card">
              <span className="stat-label">ESCALATIONS</span>
              <strong>{queue.escalations}</strong>
            </div>

            <div className="stat-card handoff-card">
              <span className="stat-label">HUMAN HANDOFFS</span>
              <strong>{queue.caseworker_handoffs}</strong>
            </div>
          </section>
        )}

        <div className="content-grid">
          {/* QUEUE */}
          <section className="queue-panel">
            <div className="panel-header">
              <div>
                <h3>Incoming Referrals</h3>
                <span>{queue?.total || 0} cases</span>
              </div>
            </div>

            <div className="case-list">
              {queue?.cases.map((item) => (
                <button
                  key={item.referral_id}
                  className={`case-row ${
                    selectedId === item.referral_id
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => selectCase(item.referral_id)}
                >
                  <div className="case-main">
                    <strong>{item.referral_id}</strong>
                    <span>{item.requested_action}</span>
                  </div>

                  <div className="case-meta">
                    <span
                      className={`urgency ${item.urgency.toLowerCase()}`}
                    >
                      {item.urgency}
                    </span>

                    <span
                      className={`status ${statusClass(
                        item.status
                      )}`}
                    >
                      {statusLabel(item.status)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* CASE DETAILS */}
          <section className="details-panel">
            {!selectedId && (
              <div className="empty-state">
                <div className="empty-icon">⌁</div>
                <h3>Select a referral</h3>
                <p>
                  Choose a case from the queue to view its
                  details and triage status.
                </p>
              </div>
            )}

            {loadingCase && (
              <div className="empty-state">
                <div className="spinner"></div>
                <p>Loading case...</p>
              </div>
            )}

            {caseData && !loadingCase && (
              <CaseDetails
                caseData={caseData}
                triage={triage}
                loadingTriage={loadingTriage}
                generateTriage={generateTriage}
              />
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function CaseDetails({
  caseData,
  triage,
  loadingTriage,
  generateTriage,
}) {
  const referral = caseData.referral;
  const resident = caseData.resident;

  const isRestricted =
    caseData.has_under_18 ||
    triage?.triage_allowed === false;

  return (
    <div className="case-details">
      <div className="case-header">
        <div>
          <span className="detail-label">REFERRAL</span>
          <h2>{referral.referral_id}</h2>
        </div>

        <span
          className={`urgency large ${referral.urgency.toLowerCase()}`}
        >
          {referral.urgency} priority
        </span>
      </div>

      {/* REFERRAL */}
      <div className="detail-section">
        <span className="detail-label">REQUESTED ACTION</span>
        <h3>{referral.requested_action}</h3>

        <p className="referral-summary">
          {referral.summary}
        </p>

        <div className="source-row">
          <span>Source</span>
          <strong>{referral.source}</strong>
        </div>
      </div>

      {/* RESIDENT */}
      <div className="detail-section">
        <span className="detail-label">RESIDENT</span>

        <div className="resident-card">
          <div className="avatar">
            {resident.resident_ref.slice(-2)}
          </div>

          <div>
            <strong>{resident.resident_ref}</strong>
            <span>
              {resident.status} · {resident.benefit_code}
            </span>
          </div>

          <div className="award">
            <span>Monthly award</span>
            <strong>
              £{Number(resident.award_monthly).toFixed(2)}
            </strong>
          </div>
        </div>
      </div>

      {/* HOUSEHOLD */}
      <div className="detail-section">
        <div className="section-title-row">
          <span className="detail-label">HOUSEHOLD</span>

          {caseData.has_under_18 && (
            <span className="warning-pill">
              ⚠ Under 18 detected
            </span>
          )}
        </div>

        <div className="household-list">
          {caseData.household.map((member) => (
            <div className="household-member" key={member.name}>
              <div>
                <strong>{member.name}</strong>
                <span>{member.relationship}</span>
              </div>

              <span>{member.age} yrs</span>
            </div>
          ))}
        </div>
      </div>

      {/* EVENTS */}
      <div className="detail-section">
        <span className="detail-label">CASE HISTORY</span>

        <div className="timeline">
          {caseData.events.map((event, index) => (
            <div className="timeline-item" key={index}>
              <div className="timeline-dot"></div>

              <div>
                <strong>{event.type}</strong>
                <span>{event.date}</span>
                <p>{event.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* AI ACTION */}
      <div className="ai-section">
        <div className="ai-header">
          <div>
            <span className="detail-label">AI TRIAGE</span>
            <h3>CaseGuard AI Assistant</h3>
          </div>

          {!triage && !isRestricted && (
            <button
              className="ai-button"
              onClick={generateTriage}
              disabled={loadingTriage}
            >
              {loadingTriage
                ? "Generating..."
                : "✦ Generate Triage Note"}
            </button>
          )}
        </div>

        {/* POLICY BLOCK */}
        {isRestricted && !triage?.triage_allowed && (
          <div className="policy-warning">
            <div className="warning-icon">!</div>

            <div>
              <strong>Human review required</strong>

              <p>
                AI triage is not available for this case.
                The case must remain with a caseworker or
                supervisor.
              </p>

              {triage?.policy_flags?.map((flag, index) => (
                <div className="policy-flag" key={index}>
                  <strong>{flag.rule}</strong>
                  <span>{flag.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI RESULT */}
        {triage?.triage_note && (
          <div className="triage-result">
            <div className="ai-completed">
              ✓ AI draft generated — caseworker review required
            </div>

            <div className="result-block">
              <span className="detail-label">SUMMARY</span>
              <p>{triage.triage_note.summary}</p>
            </div>

            <div className="result-block">
              <span className="detail-label">KEY FACTS</span>

              <ul>
                {triage.triage_note.key_facts.map(
                  (fact, index) => (
                    <li key={index}>{fact}</li>
                  )
                )}
              </ul>
            </div>

            <div className="result-block">
              <span className="detail-label">
                REASON FOR REFERRAL
              </span>
              <p>
                {triage.triage_note.reason_for_referral}
              </p>
            </div>

            <div className="result-block suggestion">
              <span className="detail-label">
                SUGGESTED NEXT STEP
              </span>
              <p>
                {triage.triage_note.suggested_next_step}
              </p>
            </div>

            <div className="result-block">
              <span className="detail-label">
                QUESTIONS FOR CASEWORKER
              </span>

              <ul>
                {triage.triage_note.questions_for_caseworker.map(
                  (question, index) => (
                    <li key={index}>{question}</li>
                  )
                )}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;