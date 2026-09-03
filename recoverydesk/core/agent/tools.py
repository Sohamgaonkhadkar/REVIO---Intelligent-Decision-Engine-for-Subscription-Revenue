from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from db.engine import make_engine, make_sessionmaker, session_tx
import json

engine = make_engine()
session_maker = make_sessionmaker(engine)

def get_case(case_id: int, policy_id: Optional[str] = None, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retrieves the complete structured case context for a given recovery case.
    Requires policy_id to disambiguate historical simulations.
    Masks future fields (resolution, recovered_flag) if queried before the case is closed.
    Payment attempts are scoped to the subscription_id, not case_id.
    """
    # Use the first policy found if not provided (fallback)
    if not policy_id:
        with session_tx(session_maker) as session:
            p_res = session.execute(text("SELECT policy_id FROM history.recovery_cases WHERE case_id = :case_id LIMIT 1"), {"case_id": case_id})
            p_row = p_res.first()
            if p_row:
                policy_id = p_row[0]
            else:
                return {}

    case_query = text("""
        SELECT 
            c.case_id,
            c.policy_id,
            c.opened_ts_h,
            c.closed_ts_h,
            c.first_failure_class,
            c.current_failure_class,
            c.amount_at_risk_inr,
            c.value_tier,
            c.n_decisions,
            c.retries_used,
            c.contacts_sent,
            c.cost_total_inr,
            c.resolution,
            c.recovered_flag,
            u.customer_id,
            u.age_band,
            u.state,
            u.locale_pref,
            s.subscription_id,
            s.segment,
            s.plan_tier,
            s.plan_amount_inr,
            s.cadence,
            s.status as subscription_status
        FROM history.recovery_cases c
        LEFT JOIN history.customers u ON c.customer_id = u.customer_id
        LEFT JOIN history.subscriptions s ON c.subscription_id = s.subscription_id
        WHERE c.case_id = :case_id AND c.policy_id = :policy_id
        LIMIT 1
    """)
    
    with session_tx(session_maker) as session:
        case_result = session.execute(case_query, {"case_id": case_id, "policy_id": policy_id})
        case_row = case_result.mappings().first()
        
        if not case_row:
            return {}
            
        case_data = dict(case_row)
        
        # Check if case was closed before as_of
        if as_of:
            close_event = session.execute(text("""
                SELECT 1 FROM history.recovery_events 
                WHERE case_id = :case_id AND policy_id = :policy_id AND event_type = 'CASE_CLOSED' 
                  AND ts_iso <= CAST(:as_of AS TIMESTAMPTZ)
            """), {"case_id": case_id, "policy_id": policy_id, "as_of": as_of}).first()
            
            if not close_event:
                # Mask future outcome fields to prevent temporal leakage
                case_data["resolution"] = None
                case_data["recovered_flag"] = None
                # cost_total_inr, retries_used, contacts_sent might be partially accumulated, but masking them entirely is safest
                case_data["cost_total_inr"] = None
                case_data["n_decisions"] = None
                
        
        # Payment attempts are linked to subscription_id
        payments_query = text("""
            SELECT attempt_id, ts_iso, amount_inr, outcome, failure_class, is_recovery_attempt
            FROM history.payment_attempts
            WHERE subscription_id = :sub_id
              AND (CAST(:as_of AS TIMESTAMPTZ) IS NULL OR ts_iso <= CAST(:as_of AS TIMESTAMPTZ))
            ORDER BY ts_iso ASC
        """)
        payments_result = session.execute(payments_query, {"sub_id": case_data["subscription_id"], "as_of": as_of})
        case_data["payment_attempts"] = [dict(r) for r in payments_result.mappings().fetchall()]
        
        return case_data

def get_timeline(case_id: int, policy_id: Optional[str] = None, as_of: Optional[datetime] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieves the chronological historical timeline combining recovery_events and payment_attempts.
    Strictly bounded by `as_of`. Needs policy_id. Payment attempts join on subscription_id.
    """
    if not policy_id:
        with session_tx(session_maker) as session:
            p_res = session.execute(text("SELECT policy_id FROM history.recovery_cases WHERE case_id = :case_id LIMIT 1"), {"case_id": case_id})
            p_row = p_res.first()
            if p_row:
                policy_id = p_row[0]
            else:
                return []

    query = text("""
        WITH sub AS (
            SELECT subscription_id FROM history.recovery_cases WHERE case_id = :case_id AND policy_id = :policy_id LIMIT 1
        ),
        combined AS (
            SELECT 
                ts_iso as timestamp,
                'EVENT' as record_type,
                event_type as type,
                detail_json as detail
            FROM history.recovery_events
            WHERE case_id = :case_id AND policy_id = :policy_id
              AND (CAST(:as_of AS TIMESTAMPTZ) IS NULL OR ts_iso <= CAST(:as_of AS TIMESTAMPTZ))
              
            UNION ALL
            
            SELECT
                pa.ts_iso as timestamp,
                'PAYMENT' as record_type,
                'PAYMENT_ATTEMPT' as type,
                json_build_object('outcome', pa.outcome, 'amount_inr', pa.amount_inr, 'failure_class', pa.failure_class)::text as detail
            FROM history.payment_attempts pa
            JOIN sub ON pa.subscription_id = sub.subscription_id
            WHERE (CAST(:as_of AS TIMESTAMPTZ) IS NULL OR pa.ts_iso <= CAST(:as_of AS TIMESTAMPTZ))
        )
        SELECT timestamp, record_type, type, detail
        FROM combined
        ORDER BY timestamp ASC
        LIMIT :limit OFFSET :offset
    """)
    
    with session_tx(session_maker) as session:
        result = session.execute(query, {"case_id": case_id, "policy_id": policy_id, "as_of": as_of, "limit": limit, "offset": offset})
        rows = result.mappings().fetchall()
        timeline = []
        for r in rows:
            record = dict(r)
            try:
                record["detail"] = json.loads(record["detail"]) if record["detail"] else {}
            except Exception:
                pass
            timeline.append(record)
        return timeline

def get_decision_record(case_id: int, decision_seq: int, policy_id: Optional[str] = None, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retrieves the historical decision context by semantic identity: (case_id, decision_seq).
    Bounded by `as_of`.
    """
    if not policy_id:
        with session_tx(session_maker) as session:
            p_res = session.execute(text("SELECT policy_id FROM history.action_log WHERE case_id = :case_id LIMIT 1"), {"case_id": case_id})
            p_row = p_res.first()
            if p_row:
                policy_id = p_row[0]
            else:
                return {}

    query = text("""
        SELECT 
            al.action_id as internal_action_id,
            al.case_id,
            al.policy_id,
            al.decision_seq,
            al.decision_ts_h,
            al.action_type,
            al.channel,
            al.exec_delay_hours,
            al.failure_class_at_decision,
            al.value_tier,
            al.retries_used_before,
            al.contacts_sent_before,
            re.ts_iso as event_timestamp,
            re.detail_json as decision_event_detail
        FROM history.action_log al
        LEFT JOIN history.recovery_events re 
            ON al.case_id = re.case_id 
            AND al.policy_id = re.policy_id
            AND re.event_type = 'DECISION_MADE'
            AND (re.detail_json::jsonb->>'seq')::bigint = al.decision_seq
        WHERE al.case_id = :case_id AND al.decision_seq = :decision_seq AND al.policy_id = :policy_id
          AND (CAST(:as_of AS TIMESTAMPTZ) IS NULL OR (re.ts_iso IS NOT NULL AND re.ts_iso <= CAST(:as_of AS TIMESTAMPTZ)))
    """)
    
    with session_tx(session_maker) as session:
        result = session.execute(query, {"case_id": case_id, "decision_seq": decision_seq, "policy_id": policy_id, "as_of": as_of})
        row = result.mappings().first()
        
        if not row:
            return {}
            
        record = dict(row)
        try:
            record["decision_event_detail"] = json.loads(record["decision_event_detail"]) if record["decision_event_detail"] else {}
        except Exception:
            pass
        return record

def explain_verdict(case_id: int, decision_seq: int, candidate: str, policy_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses the recorded decision/verdict evidence to explain why a specific action was historically chosen
    (or rejected) in favor of the given candidate. Relies entirely on historical evidence without recomputation.
    """
    record = get_decision_record(case_id=case_id, decision_seq=decision_seq, policy_id=policy_id)
    if not record:
        return {"error": "Decision not found"}
        
    actual_action = record.get("action_type")
    decision_detail = record.get("decision_event_detail", {})
    feasible_candidates = decision_detail.get("feasible", {})
    
    explanation = {
        "semantic_identity": {"case_id": case_id, "decision_seq": decision_seq, "policy_id": record.get("policy_id")},
        "actual_action_taken": actual_action,
        "candidate_queried": candidate,
        "was_candidate_feasible": feasible_candidates.get(candidate, False),
        "historical_context": {
            "failure_class_at_decision": record.get("failure_class_at_decision"),
            "retries_used_before": record.get("retries_used_before"),
            "contacts_sent_before": record.get("contacts_sent_before")
        }
    }
    
    if actual_action == candidate:
        explanation["verdict"] = f"Candidate '{candidate}' WAS the chosen historical action."
    else:
        explanation["verdict"] = f"Candidate '{candidate}' was NOT chosen. Historical action was '{actual_action}'."
        
    return explanation
