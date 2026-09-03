# C2B Graphical EDA Findings

This report is generated from observed normalized Dataset V1 data.
It contains exploratory associations, not causal treatment effects.

## Observed target heterogeneity
**Finding:** Observed success varies across action_type.
**Evidence:** Highest supported group: RETRY (0.267, n=101514); lowest supported group: SEND_REMINDER (0.125, n=22649); spread=0.142.
**Interpretation:** The logged intervention outcome is heterogeneous across action_type.
**ML implication:** action_type should remain a candidate state/context variable for C3 review if it is decision-time available.
**Caveat:** Observed association; not a causal treatment effect.

## Observed target heterogeneity
**Finding:** Observed success varies across failure_class_at_decision.
**Evidence:** Highest supported group: BANK_TECHNICAL (0.772, n=18475); lowest supported group: MANDATE_PAUSED (0.123, n=13264); spread=0.649.
**Interpretation:** The logged intervention outcome is heterogeneous across failure_class_at_decision.
**ML implication:** failure_class_at_decision should remain a candidate state/context variable for C3 review if it is decision-time available.
**Caveat:** Observed association; not a causal treatment effect.

## Observed target heterogeneity
**Finding:** Observed success varies across rail.
**Evidence:** Highest supported group: CARD_SI (0.285, n=33098); lowest supported group: UPI_AUTOPAY (0.213, n=124325); spread=0.072.
**Interpretation:** The logged intervention outcome is heterogeneous across rail.
**ML implication:** rail should remain a candidate state/context variable for C3 review if it is decision-time available.
**Caveat:** Observed association; not a causal treatment effect.

## Observed target heterogeneity
**Finding:** Observed success varies across value_tier.
**Evidence:** Highest supported group: LOW (0.294, n=84947); lowest supported group: HIGH (0.113, n=19445); spread=0.182.
**Interpretation:** The logged intervention outcome is heterogeneous across value_tier.
**ML implication:** value_tier should remain a candidate state/context variable for C3 review if it is decision-time available.
**Caveat:** Observed association; not a causal treatment effect.

## Observed target heterogeneity
**Finding:** Observed success varies across logging_policy.
**Evidence:** Highest supported group: B2_DOCTRINE (0.305, n=42582); lowest supported group: B1_PSP_PROXY (0.192, n=49915); spread=0.113.
**Interpretation:** The logged intervention outcome is heterogeneous across logging_policy.
**ML implication:** logging_policy should remain a candidate state/context variable for C3 review if it is decision-time available.
**Caveat:** Observed association; not a causal treatment effect.
