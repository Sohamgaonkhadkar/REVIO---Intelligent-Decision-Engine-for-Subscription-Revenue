"""ML datamart builder: decision-point rows with leakage-safe features + labels.

Row unit: one row per action_log entry whose action is label-bearing
(RETRY / SEND_REMINDER / SEND_PAYMENT_LINK / REQUEST_PM_UPDATE).

Label semantics (documented in DATASET_CARD):
  RETRY    -> y=1 iff that attempt succeeded
  CONTACT  -> y=1 iff a qualifying positive response (SELF_PAY_OK / REACTIVATED /
              CARD_UPDATED) arrived within response_window_hours of execution
Censored rows (response window truncated by the case horizon) keep
`censored=True` and must be excluded from training.

Leakage rule (enforced + unit-tested): every feature column is a function of
information with ts < decision_ts_h, or of static case/customer context. Latent
sidecar fields are never referenced here; salary day appears only as the
merchant-observable noisy proxy `salary_day_proxy_dom`.
"""

from bisect import bisect_left

import polars as pl

DAYS_PER_MONTH = 30
SALARY_CLUSTER_DOM = set(range(1, 8)) | {28, 29, 30}
LABELED = ("RETRY", "SEND_REMINDER", "SEND_PAYMENT_LINK", "REQUEST_PM_UPDATE")


def _hours_to_cluster(t_h: int, renewal_hour: int) -> int:
    c = t_h
    while True:
        if (c // 24) % DAYS_PER_MONTH + 1 in SALARY_CLUSTER_DOM and c % 24 == renewal_hour \
                and c >= t_h:
            return c - t_h
        c += 1
        if c - t_h > 24 * 40:
            return 24 * 40


def build_datamart(actions: pl.DataFrame, cases: pl.DataFrame,
                   base_attempts: pl.DataFrame, customers: pl.DataFrame,
                   subs: pl.DataFrame, sim: dict,
                   salary_proxy_dom: dict[int, int]) -> pl.DataFrame:
    """base_attempts: canonical BASE first-attempt renewals only."""
    labeled = actions.filter(pl.col("action_type").is_in(list(LABELED)))
    if labeled.height == 0:
        return pl.DataFrame()

    # strictly-prior history index: sub_id -> (sorted ts list, success prefix sums)
    hist: dict[int, tuple[list[int], list[int]]] = {}
    grp = (base_attempts.sort("ts_h")
              .group_by("subscription_id")
              .agg([pl.col("ts_h"), (pl.col("outcome") == "SUCCESS").alias("succ")]))
    for sid, ts_list, succ in grp.iter_rows():
        pref, run = [], 0
        for s in succ:
            run += int(s)
            pref.append(run)
        hist[sid] = (list(ts_list), pref)

    case_cols = cases.select([
        "policy_id", "case_id", "subscription_id", "customer_id", "opened_ts_h",
        "closed_ts_h", "amount_at_risk_inr", "recovered_flag",
    ])
    cust_cols = customers.select(["customer_id", "age_band", "state", "locale_pref",
                                  "signed_up_day_idx"])
    sub_cols = subs.select(["subscription_id", "segment", "plan_tier", "plan_amount_inr",
                            "billing_day_of_month", "bank_name", "start_day_idx"])

    m = (labeled.join(case_cols, on=["policy_id", "case_id"], how="left")
                .join(cust_cols, on="customer_id", how="left")
                .join(sub_cols, on="subscription_id", how="left"))
    case_open_by_sid = (cases.group_by(["policy_id", "subscription_id"])
                             .agg([pl.col("opened_ts_h"), pl.col("recovered_flag")]))
    past = {(pid, sid): (list(opens), list(recs))
            for pid, sid, opens, recs in case_open_by_sid.iter_rows()}

    horizon = sim["case_horizon_hours"]
    renewal_hour = sim["renewal_hour"]
    win = 24  # contact label window (must equal costs.response_window_hours; asserted in runner)

    rows = []
    for r in m.iter_rows(named=True):
        t = int(r["decision_ts_h"])
        day = t // 24
        sid = r["subscription_id"]
        cid = r["customer_id"]
        # prior BASE history strictly before this case opened
        ts_list, pref = hist.get(sid, ([], []))
        idx = bisect_left(ts_list, r["opened_ts_h"])
        prior_cycles, prior_succ = idx, (pref[idx - 1] if idx else 0)
        # prior failed cases of this (policy, sub) strictly before this case
        opens, recs = past.get((r["policy_id"], sid), ([], []))
        j = bisect_left(opens, r["opened_ts_h"])
        prior_failed = j
        prior_recovered = int(sum(1 for x in recs[:j] if x))
        exec_h = int(r["exec_ts_h"])
        exec_dom = (exec_h // 24) % DAYS_PER_MONTH + 1
        rows.append({
            # identifiers / provenance
            "logging_policy": r["policy_id"], "case_id": r["case_id"],
            "subscription_id": sid, "customer_id": cid,
            "decision_seq": r["decision_seq"], "decision_ts_h": t,
            # payment/failure context
            "failure_class_at_decision": r["failure_class_at_decision"],
            "first_failure_class": r["first_failure_class"],
            "rail": r["rail"], "bank_name": r["bank_name"], "segment": r["segment"],
            "plan_tier": r["plan_tier"], "amount_inr": r["amount_at_risk_inr"],
            "value_tier": r["value_tier"],
            # case progress
            "retries_used_before": r["retries_used_before"],
            "contacts_sent_before": r["contacts_sent_before"],
            "hours_since_open": r["hours_since_open"],
            "instrument_fixed": r["instrument_fixed"],
            # customer/subscription context
            "age_band": r["age_band"], "state": r["state"], "locale_pref": r["locale_pref"],
            "customer_tenure_days": max(0, day - int(r["signed_up_day_idx"])),
            "subscription_age_days": max(0, day - int(r["start_day_idx"])),
            "sub_billing_day": r["billing_day_of_month"],
            "prior_cycles_seen": prior_cycles,
            "prior_successes": prior_succ,
            "prior_success_rate": (prior_succ / prior_cycles) if prior_cycles else None,
            "prior_failed_cases_before": prior_failed,
            "prior_recovered_cases_before": prior_recovered,
            # calendar context (from ts alone)
            "day_of_month": day % DAYS_PER_MONTH + 1,
            "day_of_week": day % 7,
            "hour_of_day": t % 24,
            "in_salary_cluster": (day % DAYS_PER_MONTH + 1) in SALARY_CLUSTER_DOM,
            "hours_to_next_cluster_slot": _hours_to_cluster(t, renewal_hour),
            "salary_day_proxy_dom": salary_proxy_dom.get(cid),
            # action contextuals
            "action_type": r["action_type"], "channel": r["channel"],
            "exec_ts_h": exec_h, "exec_delay_hours": r["exec_delay_hours"],
            "exec_hour_of_day": exec_h % 24,
            "exec_day_of_month": exec_dom,
            "exec_in_salary_cluster": exec_dom in SALARY_CLUSTER_DOM,
            # label + censoring
            "y": int(bool(r["label_success"])),
            "response_kind": r["response_kind"],
            "censored": bool(r["action_type"] != "RETRY"
                             and exec_h + win > r["opened_ts_h"] + horizon),
        })
    return pl.DataFrame(rows).sort(["logging_policy", "case_id", "decision_seq"])
