# ML Dataset Audit
    
**Row Unit:** A single recovery attempt/action taken at a specific timestamp.
**Prediction Target:** `recovered_flag` (Probability of recovery given state and action).

### Excluded Columns (Leakage Risks)
['response_kind']

### Features Available
['logging_policy', 'decision_seq', 'failure_class_at_decision', 'first_failure_class', 'rail', 'bank_name', 'segment', 'plan_tier', 'amount_inr', 'value_tier', 'retries_used_before', 'contacts_sent_before', 'hours_since_open', 'instrument_fixed', 'age_band', 'state', 'locale_pref', 'customer_tenure_days', 'subscription_age_days', 'sub_billing_day', 'prior_cycles_seen', 'prior_successes', 'prior_success_rate', 'prior_failed_cases_before', 'prior_recovered_cases_before', 'day_of_month', 'day_of_week', 'hour_of_day', 'in_salary_cluster', 'hours_to_next_cluster_slot', 'salary_day_proxy_dom', 'action_type', 'channel', 'exec_delay_hours', 'exec_hour_of_day', 'exec_day_of_month', 'exec_in_salary_cluster', 'y', 'censored']

### Recommendations
1. **Formulation:** Predict `P(recovered_flag | state, action)`.
2. **Splitting:** Group by `case_id` to prevent retry-leakage across train/val/test sets.
