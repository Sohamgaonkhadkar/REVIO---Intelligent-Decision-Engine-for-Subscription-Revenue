"""Dataset V1 validation suite: the contract checks, executed for real.
Returns (results, all_passed). run_dataset_v1 refuses to ship on failure."""

import polars as pl

EXPECTED_FAILURE_CLASSES = {
    "INSUFFICIENT_FUNDS", "BANK_TECHNICAL", "RATE_LIMIT", "MANDATE_PAUSED",
    "MANDATE_CLOSED", "CARD_EXPIRED", "CARD_LOST_STOLEN",
}
LABELED = ("RETRY", "SEND_REMINDER", "SEND_PAYMENT_LINK", "REQUEST_PM_UPDATE")


def _ok(results, name, passed, detail=""):
    results.append({"check": name, "passed": bool(passed), "detail": str(detail)[:500]})


def validate(frames: dict[str, pl.DataFrame], sim: dict) -> tuple[list[dict], bool]:
    R: list[dict] = []
    customers = frames["customers"]
    subs = frames["subscriptions"]
    attempts = frames["payment_attempts"]
    cases = frames["recovery_cases"]
    events = frames["recovery_events"]
    actions = frames["action_log"]
    mart = frames["ml_datamart"]

    # --- identity & referential integrity -----------------------------------
    _ok(R, "1.customer_id_unique", bool(customers["customer_id"].is_unique().all()))
    _ok(R, "2.subscription_id_unique", bool(subs["subscription_id"].is_unique().all()))
    _ok(R, "3.attempt_id_unique", bool(attempts["attempt_id"].is_unique().all()))

    cust_ids = set(customers["customer_id"].to_list())
    sub_ids = set(subs["subscription_id"].to_list())
    _ok(R, "4.subscriptions_reference_customers",
        set(subs["customer_id"].to_list()) <= cust_ids)
    _ok(R, "5.attempts_reference_subscriptions",
        set(attempts["subscription_id"].to_list()) <= sub_ids)
    _ok(R, "6.cases_reference_subscriptions_and_customers",
        set(cases["subscription_id"].to_list()) <= sub_ids
        and set(cases["customer_id"].to_list()) <= cust_ids)
    _ok(R, "7.events_reference_cases",
        set(events["case_id"].to_list()) <= set(cases["case_id"].to_list()))

    # --- 8. state-transition / lifecycle validity -----------------------------
    closes = events.filter(pl.col("event_type") == "CASE_CLOSED")
    close1 = closes.group_by(["policy_id", "case_id"]).agg(pl.col("ts_h").first().alias("ct"))
    _ok(R, "8a.exactly_one_close_per_case", close1.height == cases.height,
        f"cases={cases.height} closes={close1.height}")
    post_close = (events.join(close1, on=["policy_id", "case_id"], how="left")
                        .filter((pl.col("event_type") != "CASE_CLOSED")
                                & (pl.col("ts_h") > pl.col("ct"))))
    _ok(R, "8b.no_events_after_close", post_close.height == 0,
        f"violations={post_close.height}")
    valid_resolutions = {"RECOVERED", "EXPIRED_WINDOW", "STOPPED_POLICY",
                         "STOPPED_OPT_OUT", "ESCALATED_UNRESOLVED"}
    _ok(R, "8c.resolutions_valid",
        set(cases["resolution"].unique().to_list()) <= valid_resolutions)

    # --- 9. no actions after terminal -----------------------------------------
    actions_post = (actions.join(close1, on=["policy_id", "case_id"], how="left")
                           .filter(pl.col("decision_ts_h") > pl.col("ct")))
    _ok(R, "9.no_actions_after_terminal", actions_post.height == 0,
        f"violations={actions_post.height}")

    # --- 10. hard-rule budgets --------------------------------------------------
    _ok(R, "10a.retry_budget_respected(<=3, NPCI 1+3)",
        bool((cases["retries_used"] <= 3).all()))
    per_case_retries = (actions.filter(pl.col("action_type") == "RETRY")
                               .group_by(["policy_id", "case_id"]).len())
    _ok(R, "10b.retried_attempts_match", bool((per_case_retries["len"] <= 3).all()))
    _ok(R, "10c.contact_budget_respected(<=2)",
        bool((cases["contacts_sent"] <= 2).all()))

    # --- 11. money conservation -------------------------------------------------
    _ok(R, "11a.recovered_le_at_risk",
        bool((cases["recovered_amount_inr"] <= cases["amount_at_risk_inr"]).all()))
    succ = events.filter(pl.col("event_type") == "PAYMENT_SUCCEEDED") \
                 .group_by(["policy_id", "case_id"]).len()
    _ok(R, "11b.at_most_one_success_event_per_case", bool((succ["len"] <= 1).all()))
    rec_no_event = cases.filter(pl.col("recovered_flag")).join(
        succ, on=["policy_id", "case_id"], how="anti").height
    _ok(R, "11c.recovered_implies_success_event", rec_no_event == 0,
        f"missing={rec_no_event}")

    # --- 11d. case ids unique per policy -------------------------------------------
    dup = (cases.group_by(["policy_id", "case_id"]).len()
                .filter(pl.col("len") > 1).height)
    _ok(R, "11d.case_id_unique_per_policy", dup == 0, f"dupes={dup}")

    # --- 12. per-case timestamps ordered -----------------------------------------
    ordered = events.sort(["policy_id", "case_id", "ts_h", "event_id"]) \
                    .group_by(["policy_id", "case_id"]).agg(pl.col("ts_h"))
    bad = sum(1 for ts in ordered["ts_h"].to_list()
              if any(a > b for a, b in zip(ts, ts[1:])))
    _ok(R, "12.timestamps_monotone_per_case", bad == 0, f"bad={bad}")

    # --- 13. required columns ----------------------------------------------------
    required = {
        "customers": {"customer_id", "age_band", "state", "locale_pref", "signed_up_date"},
        "subscriptions": {"subscription_id", "customer_id", "plan_amount_inr", "rail",
                          "bank_name", "billing_day_of_month", "status"},
        "payment_attempts": {"attempt_id", "subscription_id", "ts_h", "outcome",
                             "failure_class", "amount_inr"},
        "recovery_cases": {"case_id", "policy_id", "resolution", "recovered_flag",
                           "recovered_amount_inr", "amount_at_risk_inr"},
        "recovery_events": {"event_id", "case_id", "ts_h", "event_type"},
        "action_log": {"action_id", "case_id", "action_type", "decision_ts_h",
                       "exec_ts_h", "label_success"},
        "ml_datamart": {"failure_class_at_decision", "action_type", "exec_delay_hours",
                        "y", "logging_policy", "censored"},
    }
    for name, cols in required.items():
        _ok(R, f"13.required_columns_{name}", cols <= set(frames[name].columns))

    # --- 14. value ranges / enums -------------------------------------------------
    _ok(R, "14a.amounts_in_range",
        bool(subs["plan_amount_inr"].is_between(1, 15_000).all()
             and attempts["amount_inr"].is_between(1, 15_000).all()))
    seen = set(attempts["failure_class"].drop_nulls().unique().to_list())
    _ok(R, "14b.failure_classes_in_taxonomy", seen <= EXPECTED_FAILURE_CLASSES,
        str(sorted(seen)))
    _ok(R, "14c.hours_within_sim",
        bool(attempts["ts_h"].is_between(0, sim["sim_days"] * 24 + 400).all()))
    # no new decisions past horizon; final decision's response/escalation tail
    # may extend closure — documented bound horizon+72 (see DATASET_CARD)
    _ok(R, "14d.cases_within_horizon+72h_tail",
        bool((cases["closed_ts_h"] - cases["opened_ts_h"]
              <= sim["case_horizon_hours"] + 72).all()))

    # --- 15. mart leakage guards ---------------------------------------------------
    guards = []
    g = True
    if mart.height:
        g &= bool((mart["decision_ts_h"] <= mart["exec_ts_h"]).all()); guards.append("decision<=exec")
        g &= not any(("latent" in c or "intent_archetype" in c or c == "salary_day_of_month")
                     for c in mart.columns); guards.append("no latent/feature-of-truth cols")
        g &= bool(mart["y"].is_in([0, 1]).all()); guards.append("y binary")
        g &= bool((mart["hours_since_open"] >= 0).all()); guards.append("nonnegative history")
    _ok(R, "15.mart_leakage_and_range_guards", g, ";".join(guards))

    # --- 16. calibration anchors (bands; registry sources) --------------------------
    f = attempts.filter(pl.col("outcome") == "FAILED").height / max(attempts.height, 1)
    upi = attempts.join(subs.filter(pl.col("rail") == "UPI_AUTOPAY")
                          .select("subscription_id"), on="subscription_id")
    f_upi = upi.filter(pl.col("outcome") == "FAILED").height / max(upi.height, 1)
    card = attempts.join(subs.filter(pl.col("rail") == "CARD_SI")
                           .select("subscription_id"), on="subscription_id")
    f_card = card.filter(pl.col("outcome") == "FAILED").height / max(card.height, 1)
    _ok(R, "16a.upi_first_failure_band[0.05,0.18]", 0.05 <= f_upi <= 0.18, f"upi={f_upi:.3f}")
    _ok(R, "16b.card_first_failure_band[0.01,0.08]", 0.01 <= f_card <= 0.08,
        f"card={f_card:.3f}")
    mix = attempts.filter(pl.col("outcome") == "FAILED") \
                  .group_by("failure_class").len().sort("len", descending=True)
    _ok(R, "16c.failure_mix_diverse(>=4 classes)", mix.height >= 4,
        ", ".join(f"{r['failure_class']}:{r['len']}" for r in mix.head(6).iter_rows(named=True)))

    all_passed = all(x["passed"] for x in R)
    return R, all_passed
