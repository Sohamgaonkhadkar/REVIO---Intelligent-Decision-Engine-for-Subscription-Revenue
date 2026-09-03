# PHASE 1 — PROBLEM & SOLUTION RESEARCH

**Track 03 — AI Revenue Recovery**
*Status: Foundational research document. This document defines WHAT to build and WHY. It deliberately does NOT design the technical architecture, choose final models, or prescribe a framework. That is Phase 2.*

---

# 1. Executive Summary

**Problem selection, after researching seven candidate directions:**

> Indian subscription businesses lose recurring revenue every month when scheduled auto-debit charges fail — on UPI AutoPay mandates and card e-mandates. NPCI-reported data covered by Livemint shows that in August 2025, **55–90% of UPI AutoPay debit attempts failed across banks** ([Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)). Even in healthy months, UPI AutoPay failure rates run materially higher than card mandates (design research estimates ~8–15% vs ~2–3% — [productgrowth.in](https://productgrowth.in/insights/fintech/upi-autopay-guide/)). Each failed debit risks silent, involuntary subscription churn — churn the customer never chose. Recovery is bounded by hard regulatory constraints: RBI's e-mandate framework (24-hour pre-debit notifications, ₹15,000 per-transaction cap, AFA above it — [Stripe India recurring payments docs](https://docs.stripe.com/india-recurring-payments)) and NPCI's 2025 rules (max 1 execution + 3 retries per cycle, execution only in non-peak windows, rate-limiting — [Paytm/NPCI summary](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/)). Today most merchants either let the gateway's fixed retries run blindly or give up.

**Selected problem (precise):**

Build a **bounded, compliance-first, agentic revenue-recovery system** that takes a *batch of failed recurring-payment cases* (UPI AutoPay + card e-mandates), classifies each failure's root cause, decides and executes a per-case recovery plan within NPCI/RBI limits (when to retry, when to notify, when to offer a manual-pay link, when to stop, when to escalate), observes outcomes event-by-event, and reports **measured ₹ recovered versus named baselines under state-stated assumptions** — with a full audit trail.

**Why this problem:** It is on the company's own list ("failed-subscription recovery", "mandate retry sequencer"), it is demonstrably huge in India (NPCI-reported failure rates; ~175M UPI AutoPay transactions/month by Jan 2026 per [Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)), the global evidence base for involuntary churn is strong (20–40% of subscription churn from failed payments — [Butter](https://www.butterpayments.com/glossary/involuntary-churn/), [Pelcro](https://www.get.pelcro.com/post/involuntary-churn-hidden-revenue-leaks-in-the-subscription-business-model)), it naturally requires *the full evaluation bar the company set* (detection → intervention → bounded execution → measured recovery → compliant escalation → stopping rules → audit), and it can be built credibly by a student using **real processor sandboxes** (Stripe test mode's decline-code test cards; Razorpay subscription test mode's pending/halted lifecycle) plus a transparently calibrated simulation engine — with no pretence of access to private payment infrastructure.

**Why our approach is different from what exists:** The crowded global dunning market (Stripe Smart Retries, Recurly, Chargebee, Slicker, Butter, FlyCode) is built almost entirely for **card rails in Western markets** and optimizes silent card retries + templated emails. Our system is designed for the **Indian mandate stack** (UPI AutoPay + card SI + eNACH context), treats **regulatory constraints as a first-class machine-checkable policy layer**, applies ML *only* where prediction is the honest answer (retry-success propensity / timing selection), uses an agent *only* for what genuinely needs orchestration (multi-day per-case recovery plans reacting to event streams), and makes *measurement against baselines* a core product primitive rather than a marketing claim.

---

# 2. Original Company Challenge

**Track 03 — AI Revenue Recovery:** *"Find revenue that's slipping away and win it back."* Build an agent that:

1. Detects revenue at risk
2. Determines the right intervention
3. Executes a bounded recovery workflow

Suggested problem areas (company-provided menu): payment degradation → root cause → recovery action; checkout drop-off recovery; failed-subscription recovery; B2B receivables chaser; mandate retry sequencer; Hinglish voice recovery; promise-to-pay tracker.

**Company evaluation bar (constraints we must satisfy):**

> *"Don't just identify the problem. Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail."*

Evaluated on: **(1) problem taste**, **(2) build quality** (runs, structured, trustworthy), **(3) AI judgment** (right tool in the right place; no AI theater), **(4) failure recovery** (what broke during development and how it was handled).

**Derived design constraints for our project:**

| Constraint from the bar | Implication |
|---|---|
| "Measured money recovered across a batch" | We need a batch evaluation harness with baselines and ₹ recovered as the headline output. A live demo alone is not enough. |
| "Compliant escalation" | Regulatory/consumer-protection limits must be enforceable rules, not prompt instructions. |
| "Stopping rules" | Every case needs a terminal state machine; agent must know when to quit. Retry bombing is disqualifying, not clever. |
| "Audit trail" | Every decision, action, API call, and outcome must be logged immutably and reviewable. |
| "AI judgment" | Deterministic where determinism suffices (decline mapping, caps), ML where prediction helps, LLM only where language adds value. |

The challenge language ("mandate retry sequencer", "Hinglish voice recovery") plus India-market rails (Razorpay/Cashfree) strongly suggests an **India-facing payments context**. This materially favors the mandate/subscription directions and was treated as context, not as an instruction.

---

# 3. Research Methodology

**Source categories researched (in priority order):**

1. **Tier 1 — Primary/official:** processor & billing-platform documentation (Stripe, Razorpay, Cashfree, Recurly, Chargebee, Paddle ecosystem), regulatory material (RBI e-mandate framework as implemented and documented by Stripe India docs and payer/PSP summaries; NPCI UPI AutoPay rule changes as reported August 2025), academic/arXiv research on receivables prediction.
2. **Tier 2 — Industry research:** Atradius Payment Practices Barometer, Baymard Institute findings (as carried by eMarketer/ContentSquare and benchmark aggregators), Intuit QuickBooks/Xero SMB data, EU Payment Observatory, PCI/payments trade analyses.
3. **Tier 3 — Competitor/market:** vendor product pages and comparisons (Butter, Slicker, FlyCode, Churnkey, FlexPay, Churn Buster, Gravy, HighRadius, Upflow, Skit.ai, Symphonix/Promise-to-Pay vendors). **All vendor recovery-rate claims are explicitly labeled as vendor claims** — these companies market to buyers and their numbers are unaudited.
4. **Dataset sources:** Kaggle, UCI ML Repository, academic dataset pages. Each candidate dataset was checked for: size, schema, license, realism, and fit.

**Fact/inference/hypothesis discipline:** Every quantitative industry claim below carries a citation. Where a number originates from a company's own marketing (Stripe's 55–57% recovery claims; Razorpay's "+8% intelligent retry" claim; Slicker/FlyCode comparison tables), it is labeled as a **vendor claim**. Where I connect evidence to a conclusion, the conclusion is labeled **INFERENCE**. Where I propose something to be tested, it is labeled **HYPOTHESIS**.

**Limitations of this research (stated honestly):**

- No public dataset exists containing per-issuer decline codes with retry outcomes for recovery modelling (evidence: dataset search in §15). All recovery-outcome numbers come from vendor disclosures, which are unaudited and sometimes mutually inconsistent (e.g., Stripe's marketing figure of "55% of failed payments recovered" vs Redux Payments' audit claim of "25–35% across 200+ B2C Stripe accounts" — [Redux](https://www.reduxpayments.com/blog/stripe-smart-retries-explained)).
- NPCI does not publish an open machine-readable AutoPay failure dataset; the best public evidence is reporting of NPCI data by mainstream financial press (Livemint, citing NPCI August 2025 figures).
- Web research cannot establish privately held competitor internals; competitor gaps below are therefore identified only where documentation supports them, or explicitly labeled as inference.

---

# 4. Revenue Recovery Landscape

Revenue leakage investigated splits into **five families**, with meaningfully different mechanics:

1. **Authorization failures at charge time (cards & mandates).** A charge attempt on a stored credential fails: soft declines (temporary — insufficient funds, issuer unavailable) vs hard declines (permanent — stolen card, closed account). Industry reference points: soft declines are commonly cited as a large majority of declines (~80–90% in subscription e-commerce per [Solidgate](https://solidgate.com/blog/how-to-manage-card-declines-and-recover-lost-revenue/), ~40–60% of card-not-present declines per [Tagada](https://www.tagada.io/glossary/soft-decline) — note sources disagree on the exact split; direction is consistent). Card networks cap retries (Mastercard ~10 attempts/24h; Visa ~15/30 days, with per-attempt fees beyond — [Solidgate](https://solidgate.com/blog/how-to-manage-card-declines-and-recover-lost-revenue/); note: figures originate from a processor blog).
2. **Involuntary subscription churn.** Failed recurring payments cause customers to lapse without ever canceling: cited at 20–40% of total subscription churn ([Butter](https://www.butterpayments.com/glossary/involuntary-churn/), [Slicker](https://www.slickerhq.com/resources/blog/subscription-churn-rate-guide), [Pelcro](https://www.get.pelcro.com/post/involuntary-churn-hidden-revenue-leaks-in-the-subscription-business-model)); initial recurring-payment failure rates of 5–15% depending on vertical ([Finsi benchmarks table](https://www.finsi.ai/blog/involuntary-churn-hidden-revenue-leak/) — vendor-curated benchmarks).
3. **Indian mandate-stack failures (UPI AutoPay / e-NACH / card standing instructions).** UPI AutoPay failure rates reported at 55–90% across banks in August 2025 (NPCI data via [Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)); NPCI classifies failures as "business declines" (insufficient balance, invalid PIN etc.) vs "technical declines" (bank system/network issues). UPI AutoPay scaled to ~175M transactions/month (Jan 2026) despite this — the pain is real and growing.
4. **Checkout drop-off (pre-authorization abandonment).** ~70% of carts abandoned globally (Baymard meta-analysis of ~50 studies — carried by [ContentSquare](https://contentsquare.com/guides/cart-abandonment/reasons/) and [benchmark compilations](https://christopholivierconsulting.com/cart-abandonment-statistics/)); the single largest *fixable* reason is extra costs (48% of abandoners, Baymard 2024 US survey via [eMarketer](https://www.emarketer.com/content/extra-costs-are-the-top-reason-consumers-abandon-online-carts)). Most abandonment is not payment failure — it is price-shock, friction, or mere browsing.
5. **Receivables & commitments (B2B invoices; promise-to-pay).** 55% of US B2B invoiced sales overdue (Atradius, via [Upflow](https://upflow.io/blog/ar-collections/13-accounts-receivable-cash-collection-statistics-2024)); 47% in Western Europe ([Atradius WE 2025](https://atradiuscollections.com/us/knowledge-and-research/reports/b2b-payment-practices-trends-western-europe-2025)); EU businesses spend ~9.85 hours/week chasing payments (EU Payment Observatory, via [eInvoiceGenerator compilation](https://www.einvoicegenerator.com/blog/late-payment-statistics)). Collections also rely on *promise-to-pay* commitments, which are typically tracked manually (Oracle's enterprise collections suite has long had promise-reconciliation jobs — [Oracle docs](https://docs.oracle.com/cd/E18727_01/doc.121/e13451/T379880T379887.htm)).
6. **Contact/channel layer.** Voice-agent vendors (Skit.ai claims $1B+ resolved across 53,000+ creditors — [profile](https://yespress.io/skit-ai)) automate collection conversations in Indian vernacular contexts; email/SMS dunning is the standard recovery channel for card rails.

**Landscape conclusion (FACT + synthesis):** There are (at least) three distinct battlefields: (a) *card-rail recovery* — mature, crowded, Western-centric; (b) *mandate-rail recovery in India* — acute, under-served, constraint-rich, fast-growing; (c) *receivables/voice collections* — enterprise-served (HighRadius) and voice-served (Skit). Our opportunity assessment follows in §5–6.

---

# 5. Candidate Problem Exploration

## A. Payment degradation / failed-card-payment recovery (generic, global)

**Problem.** Card authorizations degrade and fail; soft declines are recoverable with correctly classified retry strategy; hard declines must not be retried (scheme fines, MID damage — [Solidgate](https://solidgate.com/blog/how-to-manage-card-declines-and-recover-lost-revenue/), [Tagada](https://www.tagada.io/glossary/soft-decline)).

**Importance.** Very high — [PayMID](https://paymid.com/soft-declines-vs-hard-declines-in-payments/) cites multi-trillion-dollar declined volume estimates (vendor figure; treat as directional). Decline-code–aware handling matters: insufficient funds recovers best 3–7 days later (pay-cycle alignment), processing errors recover 60–80% with immediate retry (vendor-published heuristics — [PayMID](https://paymid.com/soft-declines-vs-hard-declines-in-payments/)).

**Current approaches.** Processor-native smart retries (Stripe Smart Retries — ML-chosen retry timing across Stripe's network; Stripe marketing claims ~55–57% average failed-payment recovery for Billing overall; independent audit claims 25–35% for B2C — [Redux](https://www.reduxpayments.com/blog/stripe-smart-retries-explained), [Churnward](https://churnward.com/blog/stripe-smart-retries/)); overlay tools (Slicker, Butter, FlexPay, FlyCode) promising 2–4× static retries (vendor claims — [Slicker comparison](https://www.slickerhq.com/resources/blog/stripe-smart-retries-vs-third-party-ai-retry-engines-2025-data-driven-comparison)).

**Data availability.** No public decline-code/outcome dataset found (§15). Stripe test mode provides *ground-truth API behavior* per decline code via test cards ([Stripe docs](https://docs.stripe.com/testing)).

**AI opportunity.** Genuine but bounded: classification is a lookup table (rules). The ML-live question is *when/if to retry per context* (propensity & timing), and propensity of customer-initiated update. Vendor evidence suggests timing matters (Stripe claims Smart Retries beat fixed schedules, variously quoted ~9–14%).

**Execution feasibility.** Excellent via sandbox (Stripe test cards: `4000 0000 0000 9995` → insufficient_funds; `…9995`-family covers lost/stolen/expired/processing error).

**Risks.** Extremely crowded Western market; differentiation requires more than "me too dunning". **Verdict: strong mechanics, weak differentiation alone — fold into the India mandate-stack problem as the card rail (standing instructions under RBI e-mandate rules).**

## B. Checkout drop-off recovery

**Problem.** ~70% cart abandonment; fixable causes skew to UX/price-shock (Baymard via [ContentSquare](https://contentsquare.com/guides/cart-abandonment/reasons/)).

**Current approaches.** Email/SMS/browser re-marketing flows. Benchmarks: Klaviyo's abandoned-cart flow placed-order rate ≈ 3.33% across 143,000+ flows, $3.65 revenue-per-recipient — the highest-RPR flow (Klaviyo benchmark data via [Darkroom](https://www.darkroomagency.com/observatory/abandoned-cart-email)); Omnisend-cited timing decay (1-hour emails ≈ 5.2% conversion vs 24-hour ≈ 2.8% — via [US Tech Automations](https://ustechautomations.com/resources/blog/ecommerce-cart-abandonment-automation-comparison), vendor-aggregated).

**Data availability.** Good: REES46 e-commerce event datasets (view/cart/purchase streams — [cosmetics, 20M events](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop), [electronics, 900K](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-electronics-store)); UCI Online Shoppers Intention (12,330 sessions, academic, real — [Kaggle/UCI](https://www.kaggle.com/datasets/henrysue/online-shoppers-intention)).

**AI opportunity.** Thin: mostly timing/personalization of reminders. Much abandonment is browsing (unrecoverable by definition); recoverable wedge is dominated by checkout-UX fixes, not AI messaging.

**Execution feasibility.** Actions = emails/notifications only; you cannot *verify* conversion against simulated shoppers (the "buyer" is a log line), so measured recovery reduces to assumed response rates — **weaker satisfaction of the evaluation bar** (INFERENCE).

**Risks.** Every ESP does this; high risk of becoming "another abandoned-cart email product"; measurement is unverifiable. **Verdict: deprioritized.**

## C. Failed-subscription / involuntary churn recovery (global card context)

**Problem.** Failed recurring charges silently lapse active subscribers: 20–40% of total churn ([Butter](https://www.butterpayments.com/glossary/involuntary-churn/) — Butter's estimate; [Slicker](https://www.slickerhq.com/resources/blog/subscription-churn-rate-guide) cites ~48% of churn from failed payments, vendor figure). Expired cards ≈25–30% of failures, insufficient funds ≈20–25% ([Finsi](https://www.finsi.ai/blog/involuntary-churn-hidden-revenue-leak/) — vendor-curated).

**Current approaches.** Billing-platform dunning (Stripe defaults: up to ~4 retries/3–4 weeks — [GetChurnShield](https://getchurnshield.com/blog/stripe-smart-retries-vs-custom-retry-logic.html), vendor analysis; Recurly product pages cite 49% annual dunning-recovery rate, 72% at-risk subscriber saves — vendor stats, [Recurly](https://recurly.com/product/churn-management/); Chargebee Smart Dunning — [Chargebee blog](https://www.chargebee.com/blog/dunning-management-for-saas-business/)). Specialist overlays (Churn Buster, Gravy human-assisted, etc. — [FintechSpecs comparison](https://fintechspecs.com/blog/best-dunning-tools-saas/)).

**Known structure (well-evidenced).** "Soft declines → retry-first; hard declines → card-update/dunning-first; never retry stolen/lost" is the canonical routing doctrine ([RecovaMRR](https://recovamrr.com/blog/stripe-failed-payment-recovery), [RecoverStripe](https://recoverstripe.com/blog/stripe-failed-payment-recovery.html) — vendor guides).

**Data availability.** Same gap as A: no public per-attempt outcome data; but *behavioral ground truth* exists in sandbox state machines (Stripe billing test clocks/subscription states; Razorpay `subscription.pending` → `halted` after repeated failures — [Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)).

**AI opportunity.** Real but narrow-palette: (i) retry-timing/success propensity; (ii) which customer needs nudging vs silent retry; (iii) channel/message choice. Orchestration across days (events, state, escalation, stopping) is the natural agentic surface.

**Verdict: This IS the company's problem; global-card incarnation is crowded (score 68/85 in §6). Its Indian mandate-stack incarnation (§E) is the differentiated form of the same problem — the final selection combines them (§7).**

## D. B2B overdue receivables chaser

**Problem.** 55% of US B2B invoiced sales overdue (Atradius via [Upflow](https://upflow.io/blog/ar-collections/13-accounts-receivable-cash-collection-statistics-2024)); SMBs carry ~$17.5K avg unpaid balances ([Intuit QuickBooks 2025, compiled](https://www.einvoicegenerator.com/blog/late-payment-statistics)); collectors manually chase via spreadsheet aging reports and dunning emails.

**Current approaches.** Enterprise order-to-cash (HighRadius: AI collections, claims DSO −10%, past-dues −20% — vendor claims, [HighRadius](https://www.highradius.com/product/accounts-receivable-software/)); AR automation for mid-market (Upflow). Promise-to-pay tracking exists as a *feature* (Oracle; Symphonix — [Symphonix](https://symphonix.com/blog/automating-collections-with-promise-to-pay-in-digital-lending-2.0); IRIS Promise Keeper — [IRIS](https://www.irisinsights.ai/promise-keeper)).

**Data availability.** Best-in-class among candidates: IBM late-payment factoring dataset ([Kaggle](https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data)); H2O/HighRadius-style invoice payment-date dataset (~50K invoices; **CC BY-NC** license — [Kaggle](https://www.kaggle.com/datasets/pradumn203/payment-date-prediction-for-invoices-dataset)); academic validation that ML predicts late payment well (XGBoost/RF on invoice features — [arXiv:1912.10828](https://arxiv.org/pdf/1912.10828)).

**AI opportunity.** Strong ML (payment-date/lateness; escalation propensity) + strong agent fit (multi-touch, relationship-aware chaser with human approval). **But:** feedback horizon is 15–90+ days (you wait for an invoice to be paid), execution actions are only messages, and "money recovered" attribution is fuzzier — the customer paying ten days late did so for many possible reasons. Harder to demonstrate tight causal ₹-recovered-per-policy within a student project timeline (INFERENCE).

**Verdict: Strong runner-up (60/85). Documented thoroughly; not selected because measurement attribution and horizon are weaker than recurring-payment recovery, and its action surface is mostly messaging (drifts toward "AI that sends emails").**

## E. Mandate / autopay retry sequencing (India: UPI AutoPay + card standing instructions)

**Problem.** Indian recurring debits run under a rules-heavy mandate regime: RBI e-mandate framework — AFA at setup, 24-hour pre-debit notification, ₹15,000 general cap (₹1L for specified categories) ([Stripe India docs](https://docs.stripe.com/india-recurring-payments); [RocketPay summary](https://www.rocketpay.co.in/blog/what-is-upi-autopay-mandate)); NPCI 2025 execution rules — 1 attempt + max 3 retries per mandate cycle, execution in non-peak windows, moderated TPS, rate limiters ([Paytm/NPCI summary](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/); [integration analysis](https://vistarkriya.com/website/blog/post.php?slug=upi-autopay-integration-for-business-what-you-need-to-know-before-building-2026)). Failures are acute: 55–90% AutoPay failure rates (Aug 2025, NPCI data via Livemint); typical-month estimates 8–15% ([productgrowth.in](https://productgrowth.in/insights/fintech/upi-autopay-guide/) — practitioner estimate). Cashfree's built-in policy is mechanical: UPI AutoPay charges retry "1+3 at hourly intervals"; eNACH/cards get *no* automatic retries ([Cashfree docs](https://www.cashfree.com/docs/payments/subscription/charge)). Razorpay test mode: after 4 consecutive failures the subscription is **halted** ([Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)). Claimed uplift from intelligent retries exists but is vendor-marketed ("+8% collections" — [Razorpay blog](https://razorpay.com/blog/cheapest-payment-gateway-for-recurring-billing-e-nach-upi-autopay-and-subscription/), vendor claim).

**Importance.** In India, extremely high: the entire subscription economy (OTT, SaaS, insurance, SIPs) depends on this rail; failure directly triggers *involuntary cancellations* (Livemint).

**Data availability.** No public mandate-attempt dataset. But: (a) the **rule surface is fully public and machine-checkable** (RBI/NPCI/PSP docs); (b) **sandbox behavior is public** (Razorpay test-mode subscription lifecycle; Stripe India e-mandate preview); (c) calibration anchors exist (NPCI-via-press failure magnitudes; business vs technical decline taxonomy — Livemint; per-rail failure-rate practitioner estimates). Simulation must be transparent and sensitivity-tested (§15).

**AI opportunity.** Ideal "judgment sandwich": hard compliance constraints (rules engine) wrap a genuine prediction problem (which case recovers via which retry timing/channel — salary-cycle alignment for insufficient-balance business declines is the canonical example; Razorpay itself markets post-salary timing) inside a genuinely multi-step orchestration problem (plan per case over days; react to webhooks; stop/escalate). 

**Execution feasibility.** Good: Razorpay/Cashfree/Stripe sandboxes; failure semantics documented.

**Risks.** Simulation realism hinges on assumptions (no ground-truth outcome labels) — mitigations specified in §15. NPCI rules evolve (drift monitoring needed; actually a *feature* of a policy-as-config design). Scope must exclude eNACH/paper-NACH to stay tractable.

**Verdict: Highest-scoring candidate (71/85). Differentiated, acute, constraint-rich — and, per §C, the mandate case IS how subscription payment failure manifests in India.**

## F. Hinglish voice recovery

**Assessment.** Research confirms this direction is a **voice/telephony-and-ASR product** more than a revenue-intelligence product: the hard problems are vernacular call quality, consent/calling-hour compliance, and telephony infrastructure — which is exactly the market Skit.ai (Bangalore/NY) dominates with a dedicated seven-agent collections platform and claims of $1B+ resolved (vendor claims — [profile](https://yespress.io/skit-ai); [case study](https://skit.ai/resource/case-studies/ai-debt-collection-auto-loan-delinquency/)). There is no sandbox for live debtor conversations; outcome simulation would be entirely synthetic and unverifiable; and "agent" complexity collapses into dialogue management rather than revenue-decision quality. The *valuable* kernel (compliant, empathetic, vernacular message content) can be absorbed into our selected problem as an LLM-generated communication layer without voice infrastructure (INFERENCE). **Verdict: deprioritized (37/85) — right industry, wrong project shape for our constraints.**

## G. Promise-to-pay tracker

**Assessment.** PTP tracking is a *feature* inside collections platforms (Oracle's promise-reconciliation jobs; Symphonix tolerance rules; IRIS Promise Keeper). As a standalone product it lacks: (a) measurable causality (a kept promise may have paid anyway), (b) a detect→intervene→execute arc (it is mostly status bookkeeping), (c) available data (no public PTP datasets found). Its concept — *honor a commitment, pause chasing while promise is live, re-engage instantly when broken* — is genuinely smart escalation logic and will be adopted as a component of our escalation design (e.g., a customer who says "I get paid on the 1st"). **Verdict: absorbed as a feature (40/85), not a product.**

---

# 6. Candidate Comparison Matrix

**Scoring:** 1–5 per criterion, **5 = most favorable**. For risk criteria marked *, 5 = *lowest risk*. Raw sums, no weighting (documented so the reader can reweight). Max 85.

| # | Criterion | A: Card recovery (global) | B: Checkout drop-off | C: Failed-subscription (global) | D: B2B receivables | E: Mandate retry seq. (India) | F: Hinglish voice | G: Promise-to-pay |
|---|---|---|---|---|---|---|---|---|
| 1 | Real industry importance | 5 | 4 | 5 | 5 | 5 | 4 | 3 |
| 2 | Strength of available evidence | 5 | 5 | 5 | 4 | 4 | 3 | 3 |
| 3 | Availability of public data | 2 | 4 | 2 | 4 | 2 | 1 | 1 |
| 4 | Realistic simulation feasibility | 4 | 3 | 4 | 3 | 4 | 2 | 2 |
| 5 | ML relevance | 4 | 3 | 4 | 4 | 4 | 3 | 2 |
| 6 | Agentic AI relevance | 4 | 2 | 4 | 5 | 4 | 3 | 3 |
| 7 | Meaningful AI-judgment opportunity | 4 | 3 | 4 | 4 | 4 | 3 | 2 |
| 8 | Ability to execute actions | 5 | 2 | 5 | 3 | 5 | 2 | 2 |
| 9 | Ability to measure recovered revenue | 4 | 2 | 4 | 3 | 4 | 2 | 2 |
| 10 | Batch-processing fit | 5 | 3 | 5 | 4 | 5 | 2 | 3 |
| 11 | End-to-end product impressiveness | 4 | 3 | 5 | 3 | 5 | 3 | 2 |
| 12 | Technical feasibility (student) | 4 | 4 | 4 | 3 | 4 | 1 | 4 |
| 13 | Differentiation from existing solutions | 2 | 2 | 3 | 3 | 5 | 2 | 2 |
| 14 | Generic-chatbot risk (5=low)* | 4 | 2 | 4 | 3 | 5 | 1 | 2 |
| 15 | Private-data dependency (5=low)* | 2 | 3 | 2 | 3 | 2 | 1 | 1 |
| 16 | Scope risk (5=low)* | 3 | 3 | 4 | 2 | 4 | 1 | 4 |
| 17 | Portfolio value (AI Engineer profile) | 4 | 3 | 4 | 4 | 5 | 3 | 2 |
| | **Total (max 85)** | **65** | **51** | **68** | **60** | **71** | **37** | **40** |

**How to read the scores (key rationale, not just numbers):**

- **Criteria 3 & 15 are everyone's weakness.** No candidate except B and D has real public datasets with the semantics needed; B and D have data but lose on criteria 8–9 (execution and measurement). This trade-off is the central tension of the whole problem space: *where data exists, actionability is weak; where actionability is strong, data must be sandbox-derived or simulated.* We resolve it via sandbox APIs + transparent simulation (§15), and the matrix shows A/C/E dominate under that resolution because they score where the challenge bar actually scores (criteria 1, 5–10, 13, 17).
- **E beats C (71 vs 68)** on differentiation (13: 5 vs 3 — the global dunning market is crowded; nothing visible targets India's mandate stack as the product core), impressiveness (11), and portfolio value (17), while C wins slightly on evidence depth (2). C and E are the same failure phenomenon on different rails; the mandate sequencer *is* India's failed-subscription-recovery problem. **The selection merges them (§7).**
- **A trails C/E** because generic card recovery without subscription context is precisely what Stripe/Recurly/Butter/Slicker already commoditize (13: 2).
- **D scores well but loses on 9 and 12** (measurement attribution over 15–90-day horizons; enterprise integration expectations).
- **B, F, G are structurally mismatched** to the evaluation bar ("measured money recovered"): B can't observe conversion of simulated shoppers; F can't simulate conversations credibly; G lacks a detection→execution arc.
- **Honest check against score-rigging:** criteria 13, 14, 16, 17 (where E wins) are arguably aspirational; criteria 1, 2, 3, 12 (where B/D do better) are conservative. Under a purely conservative weighting, C and D look best. **That is why the final problem merges C's evidence base with E's constraints — the decision survives both weightings.**

---

# 7. Selected Problem

**We are solving:**

> **Failed recurring-payment recovery on Indian subscription rails.** For a subscription merchant (OTT, SaaS, D2C subscriptions, insurance premium, SIP-like products) whose scheduled auto-debit fails — on UPI AutoPay or card standing instructions under RBI's e-mandate framework — the system must, for each failed-debit case: determine the root cause (business vs technical decline; insufficient funds vs mandate paused vs bank-side outage vs card expired), select a recovery plan that is provably inside NPCI/RBI limits (attempt budget 1+3 per cycle, non-peak execution windows, pre-debit notification rules, contact limits), execute that plan as a bounded multi-day workflow against payment-rail APIs (sandbox), react to outcome events, stop when stopping rules trigger, escalate to human/compliant channels where required, and produce a measured report: **₹ recovered per policy versus named baselines across the batch**, with a complete audit trail.

**What this is not:** Not a chatbot. Not a dashboard. Not a copy of Stripe Smart Retries (we do not re-derive card retry heuristics as our core). Not a voice platform. Not a collections suite.

---

# 8. Target Users and Stakeholders

- **Primary user (the operating user of our product):** a **Growth/Billing-Ops or Founder's-office operator** at an Indian subscription business (₹1L–₹1Cr MRR range) who today watches `subscription.pending` → `halted` webhooks and loses customers silently.
- **Secondary users:** finance/revenue ops (needs recovery numbers and auditability), compliance/risk (needs proof of NPCI/RBI adherence), customer support (needs case context).
- **Affected end-customers:** subscribers whose debits fail; they experience compliant notifications, a self-serve manual-pay link, and *no spam* — and their subscription survives when it should.
- **Business stakeholders:** the merchant's CFO (MRR retention; involuntary churn is 20–40% of churn per cited sources) and, de facto, the PSP/gateway whose rails are used.

---

# 9. Current Workflow (as commonly handled today)

Indian subscription merchant's status quo, reconstructed from processor documentation and practitioner reporting:

1. Renewal date arrives → PSP executes mandate debit during allowed window (Razorpay/Cashfree/NPCI windows; non-peak hours).
2. Charge fails → PSP applies **its own fixed policy**: e.g., Cashfree "1+3 retries at hourly intervals" for UPI AutoPay ([Cashfree docs](https://www.cashfree.com/docs/payments/subscription/charge)); Razorpay retries daily until attempt exhaustion, then **halts the subscription** ([Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)).
3. Merchant receives webhook events (`subscription.pending`, `subscription.halted`, payment-failed events).
4. **Friction points (FACTS from docs + INFERENCES labeled):**
   - *Per-case intelligence is absent.* The PSP's retry cadence is the same template for an "insufficient balance" debit on a salary-account customer on the 28th (recoverable post-salary) as for a mandate silently paused by the user in their UPI app (unrecoverable by retry — retrying is pure waste) — INFERENCE from failure taxonomy (NPCI business vs technical declines — [Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)) plus fixed PSP retry mechanics (Cashfree/Razorpay docs).
   - *Hand-off is manual and silent.* Most merchants have no workflow between "halted" and "lost customer": an email may or may not fire; no manual pay-link orchestration; no escalation owner — INFERENCE from the absence of these features in PSP subscription docs and from practitioner guidance that recovery flows "must be built" ([productgrowth.in](https://productgrowth.in/insights/fintech/upi-autopay-guide/)).
   - *No measurement.* Merchants cannot answer "what did our retry policy recover vs doing nothing?" — marketing uplifts are the PSP's claim, not the merchant's number — INFERENCE.
   - *Compliance is on the merchant.* Attempt caps, windows, and pre-debit notifications must be respected; violations risk PSP/rail penalties — FACT ([NPCI/Paytm summary](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/); [Stripe India docs](https://docs.stripe.com/india-recurring-payments)).

---

# 10. Existing Solutions and Market Landscape

| Solution class | Who | What they verifiably do | Established limits / stated observations (no invented weaknesses) |
|---|---|---|---|
| Global billing platforms w/ recovery | Stripe Billing (Smart Retries, ML timing across network; marketing claims ~55–57% avg recovery; [Churnward](https://churnward.com/blog/stripe-smart-retries/), [Redux audit claim 25–35% B2C](https://www.reduxpayments.com/blog/stripe-smart-retries-explained)); Recurly (ML retries + account updater + dunning analytics; 49%/72% vendor stats — [Recurly](https://recurly.com/product/churn-management/)); Chargebee Smart Dunning; Paddle Retain | Card-rail retry timing, dunning emails, account updater, analytics. Recurly explicitly supports UPI AutoPay via gateway with UPI-specific static retries ([Recurly docs](https://docs.recurly.com/recurly-subscriptions/docs/upi-autopay)) | Built for Western card rails as core; vendor-controlled black-box policies; per-case reasoning/audit not exposed; India support positioned as gateway-mediated, not as a mandate-native product. **(FACT for capabilities; gap claim = INFERENCE from scope of public docs)** |
| Card-recovery overlays | Slicker, Butter, FlexPay, FlyCode, Churnkey Precision, Vindicia, Gravy (human-assisted) | ML retry timing across gateways, invisible recovery, dunning; claims 2–4× static retries (vendor claims — [Slicker](https://www.slickerhq.com/resources/blog/stripe-smart-retries-vs-third-party-ai-retry-engines-2025-data-driven-comparison), [FlyCode](https://www.flycode.com/blog/top-payment-recovery-platforms-2026-comparison-chart-success-rate-stats)) | Cardrs/UPI-AutoPay-in-India is absent from all surveyed product surfaces; pricing is %-of-recovered revenue; policies not transparent — (FACT re: surveyed product pages). None expose a compliance-checkable policy layer or a batch baseline-comparison experiment harness — INFERENCE from product documentation and pricing pages. |
| Indian PSP subscription engines | Razorpay Subscriptions (intelligent retries claim +8% — vendor, [Razorpay](https://razorpay.com/blog/cheapest-payment-gateway-for-recurring-billing-e-nach-upi-autopay-and-subscription/)), Cashfree (1+3 hourly UPI retry, none for cards/eNACH — [Cashfree docs](https://www.cashfree.com/docs/payments/subscription/charge)) | Execute mandates, fixed-cadence retries, webhooks, pre-debit notifications, halt lifecycle | Merchant-side per-case policy, measurement, and escalation are the merchant's problem — FACT in the sense that PSPs recover within their engine and halt after exhaustion; merchant experiences a binary (recovered | halted) with no experiment interface (INFERENCE from API surface). |
| AR/collections suites (B2B) | HighRadius, Upflow | Collections prioritization, dunning, agentic AR claims (vendor) | Enterprise-priced, ERP-integrated, invoice-centric; not mandate-native — FACT (positioning). |
| Collection-conversation agents | Skit.ai (7-agent collections platform, $1B+ claim), eDAS voicebots | Vernacular voice/SMS collection conversations | Voice/telephony-first; debtor-collections (lending) context rather than subscription billing ops — FACT (positioning). |

**Market conclusion (INFERENCE):** No surveyed solution markets itself as a **merchant-side, mandate-native, compliance-verifiable, experiment-measured recovery orchestrator for India's subscription rails**. That phrasing describes an intersection — it is our differentiation hypothesis to test, not a claim that no one ever tried adjacent features.

---

# 11. The Specific Gap We Intend to Address

**FACT (research-supported):**
1. UPI AutoPay failure rates are structurally high (NPCI-reported 55–90% in Aug 2025 — [Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html); typical-month practitioner estimates 8–15% — [productgrowth.in](https://productgrowth.in/insights/fintech/upi-autopay-guide/)) and each unrecovered failure risks involuntary subscription churn.
2. Recovery is constrained by hard rules: 1+3 attempts/cycle, non-peak execution windows, pre-debit notification timing, ₹15K caps, rate limits (RBI/NPCI/PSP docs).
3. PSP default recovery is template-based and terminates in a halt; merchant visibility is webhook events and a binary outcome.
4. Global recovery tooling categories (smart retries, dunning overlays) demonstrably work on cards — multiple independent vendor claims and audits — but are engineered around card networks, not India's mandate stack.

**INFERENCE (reasonable conclusions from the above):**
5. Treating per-case failure reason + customer context (salary-cycle timing, rail, bank, attempt history, mandate state) as inputs to a *per-case* recovery plan should beat fixed PSP cadences, *the same way* decline-code routing beats dumb retries on cards (doctrine well-documented in §A). This transfer of doctrine to mandate rails is the core opportunity — plausible, not proven.
6. Because recovery outcomes can't be learned from public data, the only credible project stance is: transparent simulation + sandbox actuation + baseline experiment harness, with assumptions exposed for sensitivity testing.

**HYPOTHESIS (what our project intends to demonstrate):**
7. On calibrated batches of failed recurring-debit cases, a per-case policy engine (rule constraints × propensity-driven timing × bounded agentic orchestration) recovers measurably more ₹ than (i) no intervention, (ii) the PSP-default 1+3/fixed cadence, and (iii) naive interval heuristics — *at equal or lower contact volume and zero compliance violations*.
8. The margin comes disproportionately from (a) salary-window-aware timing for insufficient-balance business declines, (b) not wasting attempts on paused/revoked mandates, and (c) timely manual-pay-link nudges where retries are useless. (Testable in simulation; honest bounds stated in §15–16.)

---

# 12. Our Proposed Solution (product/system behavior — not architecture)

**Working name (placeholder): "RecoveryDesk"** — a merchant-side recovery operations platform for Indian subscription businesses. (Final naming deferred to Phase 2.)

**What enters the system:**
- A *revenue case*: a failed recurring-debit event with context — mandate/customer pseudo-identity, rail (UPI AutoPay | card SI), PSP-reported failure reason/error class, amount, plan, tenure, customer region/locale, prior attempt & payment history, upcoming NPCI/RBI constraint windows.
- Case sources: (a) **live sandbox** (Razorpay subscription test mode / Stripe test mode generating genuine API events via documented test cards), (b) the **simulation engine** generating batches with explicitly versioned assumptions.

**What the system detects:** revenue at risk per case (₹ amount × propensity of loss), classified root cause (from the failure-reason taxonomy: business vs technical decline; insufficient balance; mandate paused/revoked; bank outage window; card expired/lost/stolen; authentication required), and case state over time (a terminal state machine: `at_risk → in_recovery → {recovered | halted_after_exhaustion | escalated | written_off}`).

**What intelligence is applied (behavioral level):**
- Rule layer computes what is *permitted* (attempt budget, windows, notification requirements, contact caps, channel constraints).
- Predictive layer estimates *what will work* (recovery propensity & time-to-recover given timing/channel choices).
- Orchestration layer (the agent) plans and runs the *case-level sequence*: which retries to schedule in which compliant windows, whether/when to send which notification (with self-serve manual-pay link), when to stop silently, when to escalate to human/compliant outreach, when to open the grace-period state vs mark write-off proposed.

**Actions the system can execute (bounded):** schedule/trigger retry via PSP API in sandbox within policy limits; send a compliant customer notification (email/SMS/WhatsApp-style message via simulated or least-risk real channel) with manual-payment link; mark case state transitions; write audit records; create an escalation ticket for a human.

**Actions the system is blocked from:** exceeding NPCI attempt budgets or windows (enforced by policy engine + a second independent "circuit breaker" check); charging a customer without a live mandate; inventing discounts/offers; contacting a customer beyond frequency caps or outside permitted hours; modifying amounts; auto-cancelling a subscription without policy authorization; deleting audit entries.

**Stopping rules:** attempt budget exhausted; mandate reported paused/revoked; hard-decline equivalent (lost/stolen/expired card) → stop retrying, switch to update-payment-method path; customer opt-out; grace window expired → escalate or propose write-off with human approval.

**Escalation:** value-tiered (small amounts: fully automated; large amounts/high-value customer: human approval required for anything beyond standard retry+notify); compliance escalation if any rule-check fails; repeated broken promise-to-pay → re-engagement path (adopted from §G research).

**Auditability:** append-only event log per case (inputs, rule evaluations, model scores + rationale codes, actions, API responses, timestamps, decision versions), replayable; batch-level experiment record (policy version vs baseline version, outcomes, assumptions version).

**Outcome tracking:** per-case recovery and time-to-recover; per-batch ₹ recovered by policy incl. baseline comparison; contact/attempt cost accounting; compliance violation count (target exactly 0).

---

# 13. Why Each Type of Intelligence Exists

| Component | Purpose in product | Why this method is appropriate (and why alternatives are not) |
|---|---|---|
| **Deterministic rules engine** (decline/failure-reason taxonomy; NPCI/RBI attempt budgets, windows, caps, notification timing; contact frequency caps; kill-switch) | Hard constraints and routing doctrine ("insufficient balance → wait for balance-likely window; paused mandate → don't retry, notify") | These are *published, verifiable, enforceable* rules. Using an LLM or ML for compliance would be unverifiable and dangerous — a category error. |
| **Classical ML** (gradient-boosted propensity models; possibly survival analysis for time-to-recover) | P(case recovers \| rail, bank, failure reason, attempt history, day-of-month, amount, tenure, channel); ranking candidate compliant windows | This is a genuine prediction problem with sparse, noisy, confounded signals — exactly where ML earns its place over heuristics. (Model choice deferred to Phase 2.) |
| **Statistical analysis / experiment harness** | Baseline comparison (vs no-intervention, fixed cadence, naive heuristics); uplift intervals; assumption sensitivity analysis | The evaluation bar is *measurement*. Statistics is the tool for measurement, not more AI. |
| **Agentic orchestration** (bounded planner-executor-observer loop per case; tools = PSP API, scheduler, notification service, policy checker, audit log, escalation queue) | Multi-day, event-driven plans that must react to webhooks, respect state, and stop correctly — beyond a cron of fixed retries | The workflow is genuinely sequential and contingent: after attempt 2 fails with reason X, allowed next actions change. This is where a bounded agent is the honest fit — and the failure mode of NOT having one is exactly "same template for every case," the gap in §9. Bounded means: finite action vocabulary, policy-gated tool calls, terminal states, human gates — *not* open-ended autonomy. |
| **LLM (constrained, optional-but-valuable)** | (a) Generate compliant, empathetic customer messages in the customer's locale (incl. Hinglish) from validated templates with placeholders for amount/plan/date; (b) case summaries for humans reviewing escalation queues | Language quality is the actual bottleneck for customer communication efficacy and for operator trust. All non-language decisions (amounts, counts, windows) are never exposed to the LLM; template fallback must always exist. This is also the disciplined answer to the challenge's "Hinglish" flavor without building a telephony product. |
| **Human approval (in the loop)** | High-value cases, write-offs, any policy bypass | Money-moving and relationship-risk actions need accountability; also exactly what the challenge's "compliant escalation" asks for. |
| **Explicitly NOT used:** multi-agent swarms; LLM for classification/limits/arithmetic; RL from day one | — | One orchestrator with tools is sufficient (no evidence more agents add value); deterministic verifiable logic must not be probabilified; online RL needs more outcome data than any student project can ethically gather (bandit policy adaptation is a *stretch extension* once simulated outcome streams exist, not a dependency). |

---

# 14. Differentiation

- **vs simple ML classifiers:** the model's score is a *planning input*, not the product; the product executes bounded actions and measures ₹ outcomes against baselines.
- **vs simple retry systems / PSP defaults:** per-case policies under compliance constraints with experiment-measured uplift — the PSP template is our *baseline to beat*, not our design.
- **vs rule-only dunning workflows:** pure rules cannot rank timing/priority under scarce attempt budgets (3 retries/cycle); the propensity layer is what allocates attempts intelligently.
- **vs generic AI agents:** ours has a closed-world action vocabulary, machine-checked constraints, terminal states, and audit-first logging — by construction it cannot "creatively" violate a banking rule.
- **vs ReasonFlow (previous project):** ReasonFlow answers *"what happened and what governed decision is safe"* — a generic decision-intelligence spine. This system answers *"this specific case is failing — execute the best permitted intervention now, watch what happens next on the payment rail, and account for the recovered money."* Differences are structural: **(1) Execution on external rails** with real API events (sandbox), not in-memory option evaluation; **(2) outcome-observing feedback** (webhook → re-plan) vs decision recommendation; **(3) measured ₹-recovered economics** (baseline experiments) vs governed-decision quality; **(4) domain-native constraint layer** (NPCI/RBI as enforceable policy) vs generic guardrail policies. If any future design review shows ReasonFlow's general pipeline resurfacing unchanged, that is a design smell to eliminate in Phase 2.

---

# 15. Data Strategy

**Headline finding (FACT):** *No public dataset exists with per-attempt recurring-debit outcomes, decline/reason codes, and recovery labels for India (or cards).* Confirmed across Kaggle, UCI, GitHub, and academic search. Closest available resources and their assessments:

| Dataset | Source / License | Scale | Supports | Missing / verdict |
|---|---|---|---|---|
| eCommerce events history (cosmetics ~20M events; electronics ~900K) | Kaggle/REES46 — [link](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop) | Very large real event streams | In-session behavior (was used to evaluate candidate B) | Not payment-failure data; kept as fallback only |
| UCI Online Shoppers Purchasing Intention | UCI/Kaggle — [link](https://www.kaggle.com/datasets/henrysue/online-shoppers-intention) | 12,330 sessions, real, academic | Purchase-intention propensity (candidate B) | Not usable for mandate recovery |
| UPI Transactions 2024 (synthetic, CC0) | [Kaggle](https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset) | ~30MB synthetic | Shape reference for Indian payment demographics/temporal patterns | Synthetic; no mandate semantics; use only as external prior for realism checks |
| Digital Wallet Transactions (synthetic, MIT) | [Kaggle](https://www.kaggle.com/datasets/harunrai/digital-wallet-transactions/data) | 5,000 records | Same caution as above | Success/fail labels exist but no recovery semantics |
| Financial Transactions Analytics (Caixabank hackathon, Apache 2.0) | [Kaggle](https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets/data) | 1.4GB, cards+users+MCC | Rich card/user realism reference | Fraud-centric; no recurring/mandate semantics |
| IBM Finance Factoring — Late Payment Histories | [Kaggle](https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data) | ~2.4K invoices, real-ish sample | (Candidate D) invoice lateness | Small; license unclear; not our selected problem |
| Invoice payment-date prediction (H2O-style) | [Kaggle](https://www.kaggle.com/datasets/pradumn203/payment-date-prediction-for-invoices-dataset), **CC BY-NC 4.0** | ~50K invoices | (Candidate D) payment-date modelling proven feasible ([arXiv:1912.10828](https://arxiv.org/pdf/1912.10828)) | Non-commercial license; B2B invoices, not mandates |

**Strategy: REAL SANDBOX BEHAVIOR + TRANSPARENT SIMULATION ENGINE + CALIBRATED EXTERNAL ANCHORS.**

1. **What is real:** API semantics, event sequences, decline/reason-code taxonomies, and state machines from processor sandboxes (Stripe test cards incl. `…0341` "attaches but declines on charge" for subscription-failure realism — [Creem test-card reference](https://www.creem.io/blog/stripe-test-cards) / [Stripe testing docs](https://docs.stripe.com/testing); Razorpay test-mode subscription lifecycle with pending/halted transitions and 1-day retry spacing — [Razorpay test docs](https://razorpay.com/docs/payments/subscriptions/test/)).
2. **What is simulated (and why it must be):** the *external world that answers* — customer balances over time (salary-cycle structure), bank outage windows, mandate pauses, card expiries, message-open/pay behavior, and thus retry/message outcomes. No public ground truth exists; simulation is the only legal/ethical route.
3. **Calibration anchors (all cited, versioned):** NPCI-reported failure magnitudes and business/technical decline taxonomy (Livemint); typical-month failure-rate ranges 8–15% AutoPay / 2–3% cards (productgrowth.in practitioner estimate); cause mix priors (expired cards 25–30%, insufficient funds 20–25% for subscriptions — vendor-curated [Finsi](https://www.finsi.ai/blog/involuntary-churn-hidden-revenue-leak/), used as priors to be sensitivity-tested, not as truth); recovery-by-attempt decay shapes (vendor-published scenario tables — [Slicker CFO guide](https://www.slickerhq.com/blog/soft-decline-retry-strategies-saas-cfos-q3-2025-guide), labeled vendor-modeled); RBI/NPCI rule values from §E.
4. **Anti-fake-recovery protocol:** (a) every simulation parameter is a versioned, documented assumption with a source or "assumed" label; (b) results are reported *per assumption scenario* with pessimistic/base/optimistic bands (sensitivity analysis is part of the deliverable, not a footnote); (c) headline reports cite **incremental recovery vs baselines under stated assumptions**, never absolute claims of real-world production recovery; (d) the live sandbox batch proves *system behavior end-to-end* (real API calls, real webhooks, real audit), while the simulator proves *policy economics* — the two are never conflated in reporting.

---

# 16. Measurement and Success Criteria (preliminary)

**Primary metric:** ₹ recovered per 1,000 failed-debit cases within the allowed recovery window, per policy, benchmarked against: (0) **no intervention**, (1) **PSP-default cadence proxy** (1+3 hourly / daily-until-halt), (2) **naive daily retry heuristic**, (3) (stretch) oracle bound of solvable cases.

**Supporting metrics (chosen, not exhaustive):** recovery rate by failure-reason class; incremental ₹ vs baseline 1 with uncertainty intervals; attempts consumed per recovered case (attempt-efficiency under the 1+3 budget); customer-contact volume per case; median time-to-recover; unnecessary-contact rate (contacts to cases that would have self-recovered — measurable only in simulation, which is also why simulation must be conservative); compliance-violation count (must equal 0 across all runs — a hard gate, not an average); policy-vs-baseline divergence explainability (audit reviewability score via sampled case walkthroughs).

**Demonstration format (target):** *"Across batch B of N failed cases over window W, under assumptions vX (report), policy RecoveryDesk recovered ₹Y (Z%) vs ₹Y₀ for no-intervention and ₹Y₁ for the PSP-default proxy, sent C contacts/case, average D days-to-recover, 0 rule violations; sensitivity across pessimistic/optimistic scenarios: [band]."* Sandbox actuation proof provided separately as system-truth evidence.

---

# 17. Boundaries and Safety

- **Allowed:** schedule/trigger retries inside policy-verified windows/budgets; send rate-limited templated/LLM-drafted compliant notifications with self-serve pay links; state transitions; audit writes; escalation tickets; recommend (not execute) subscription pause/cancel offers beyond policy, pending human approval.
- **Not allowed:** exceeding attempt budgets/windows (double-checked independently of the agent); charges without a live mandate; changing amounts; unsolicited discounts; contact outside permitted windows/frequency caps; honoring no opt-out; deleting/altering audit events; acting on live payment credentials (sandbox-only scope for this project).
- **Escalation rules:** amount/customer-tier thresholds → human approval node; any failed rule-check → immediate halt + compliance escalations; k consecutive broken promise-to-pay → re-engagement workflow then human.
- **Data handling:** synthetic/simulated customers by construction; no PANs, no real VPAs, no real card numbers anywhere; least-privilege test keys; DPDP-Act-aligned minimization posture documented even though data is synthetic.
- **Audit requirements:** append-only, versioned, replayable logs for inputs/rule evaluations/model scores/actions/API responses; batch experiment records with assumption-set versions.

---

# 18. Risks and Open Questions (no hidden uncertainty)

1. **Simulation realism** — the entire economics story rests on calibrated assumptions; mitigated by source-anchored priors, sensitivity bands, and honest reporting (§15). Residual risk: medium-high; this is the #1 threat to credibility and must be engineered in Phase 2 (assumption registry, scenario runner).
2. **PSP sandbox fidelity** — test modes may not reproduce production timing/failure distributions (e.g., Razorpay test tokens valid 3 days, 4-failure halt; Cashfree cut-off tables); sandbox proves *mechanics*, not *frequencies*.
3. **Rule drift** — NPCI/RBI rules change (yet again); policy-as-config mitigates; needs a documented rule-version registry.
4. **LLM value vs cost** — message generation must demonstrably beat strictly templated messages on a review rubric, or the LLM is dropped (right-tool test).
5. **Evaluation validity** — simulation-grade "measured recovery" could be read as theater if not framed rigorously; the frame in §16 is mandatory.
6. **Scope creep** — eNACH/paper-NACH, real WhatsApp Business API onboarding, real SMS DLT registration (India), currency above ₹15K with AFA — all explicitly out of v1 scope; card SI covered only within the e-mandate ≤₹15K regime, mirroring UPI cap.
7. **Single-builder timeline** — batch-first design (no real-time SLOs) keeps it feasible; real-time is a stretch goal.

---

# 19. Final Problem Definition

- **Problem:** When a scheduled recurring debit fails on UPI AutoPay or a card e-mandate for an Indian subscription merchant, default PSP retry templates waste the strictly limited retry budget (NPCI: 1+3 per cycle), ignore per-case root cause, and end in silent subscription halts — producing involuntary churn the customer never chose, under regulatory constraints most merchants cannot operationalize.
- **Target user:** Billing/growth-ops owner at an Indian subscription business.
- **Revenue leakage addressed:** failed recurring debits → involuntary subscription churn (rail-level scale: up to 55–90% AutoPay debit failures in a poor month per NPCI-reported data; ~175M AutoPay txns/month national volume).
- **Core system objective:** per-case, compliance-first recovery planning and bounded execution with measured outcomes.
- **Key measurable outcome:** incremental ₹ recovered per case-batch vs named baselines, at zero compliance violations, with full audit trail.
- **Boundaries:** sandbox-executed; simulation-grounded economics with stated assumptions; cards/UPI ≤₹15K e-mandate regime only; no voice; no lending collections; no live production credentials.

---

# 20. Proposed Solution Summary (input to Phase 2)

**RecoveryDesk** (working name) = ingestion of failed-debit cases (sandbox events + simulated batches) → rule-based constraint & root-cause layer (RBI/NPCI/PSP policy engine + failure taxonomy) → ML propensity/timing layer → **bounded agentic orchestrator** executing multi-day recovery plans through payment-rail APIs and compliant notifications (LLM-assisted, locale-aware messaging incl. Hinglish, template-guardrailed) with **stopping rules, tiered escalation, human gates, and append-only audit** → **batch experiment harness** reporting ₹ recovered vs baselines under versioned assumptions, plus a live sandbox actuation proof. Phase 2 must now produce the architecture that delivers exactly this and nothing more.

---

# 21. Phase 2 Research Questions (prerequisites to architecture)

1. **Exact case/event schema:** union of Razorpay `subscription.*`/payment-failed webhooks, Stripe PaymentIntent/invoice failure payloads, and our simulator's case format — define the canonical `RecoveryCase` event/state model.
2. **Canonical failure taxonomy:** map PSP-specific reason codes (Razorpay/Cashfree/Stripe + NPCI business/technical classes) into one typed taxonomy that drives the rule layer.
3. **Exact ML objective:** per-case recovery propensity under candidate (window, channel) interventions — classification vs ranking vs survival formulation; label strategy in simulator-first regime; how live-sandbox events can later fine-tune without leakage.
4. **Policy model design:** attempt budget/window check as pure functions + config (versioned rule packs); the independent circuit-breaker design.
5. **Agent boundaries:** closed action vocabulary; per-case plan horizons; how the orchestrator suspends/resumes across days (persistence model); what triggers re-planning.
6. **Tools/actions inventory:** PSP sandbox API clients; scheduler semantics; notification channel adapters (simulated email/SMS/WhatsApp with audit payloads — DLT/sender-ID realities); manual pay-link generator; escalation queue; audit log store.
7. **Simulation engine spec v1:** entity generators (customers, mandates, rails, banks), failure-reason mixture priors w/ citations, salary-cycle balance model, bank-outage windows, response hazards per intervention; assumption registry; scenario runner; seeds/reproducibility; validation checks against anchor statistics.
8. **Experiment design:** batch sizes, window lengths, baseline policy implementations, uplift estimation method, violation gating, sensitivity analysis protocol.
9. **DB requirements:** append-only audit (consider immutable event store), case state store, policy/registry versioning, experiment tables.
10. **Latency targets:** batch/near-batch scheduling (minutes-ok), no real-time payment-path SLO in v1.
11. **Frontend requirements:** case workbench (reasoning trace + audit), batch experiment reports (₹ vs baselines, bands), policy config viewer, escalation inbox. (React/TS per existing skills.)
12. **Deployment constraints:** single VPS/docker-compose target; secrets handling; timezone correctness (IST windows).
13. **Kill/ship criteria:** minimum sandbox actuation proof; minimum simulator realism checks vs anchors; LLM-vs-template review rubric pass threshold; timeline checkpoints with failure-recovery log (challenge criterion 4).

---

# Research Self-Audit (internal checklist required by brief)

1. Multiple candidates investigated → 7, each with sourced evidence. ✔
2. Research changed initial assumptions → global "failed payment agent" was the a-priori favorite; evidence pushed selection toward the India mandate-stack instance merged with C; candidate D remained a close runner-up on data grounds but lost on measurement. ✔
3. Facts vs hypotheses → labeled inline; vendor claims flagged as such. ✔
4. Measurability → explicit metrics, baselines, and demonstration format. ✔
5. Batch recovery demonstration → experiment harness + sandbox actuation. ✔
6. Data strategy realistic → verified no public outcome data; simulation declared, anchored, and sensitivity-bounded. ✔
7. AI necessary somewhere → propensity/timing under scarce attempt budget; orchestration over event streams; message language. ✔
8. No unnecessary AI → rules for compliance/taxonomy; statistics for measurement; explicit anti-decisions in §13. ✔
9. Not a generic ML project → executes, measures, audits on rails. ✔
10. Differentiated from ReasonFlow → structural analysis in §14. ✔
11. Buildable by a student → sandbox APIs, batch-first, scoped-out piles listed. ✔
12. Phase-2 foundation → §21 enumerates the questions architecture must answer. ✔

---

# Sources

**Official documentation / primary surface**
- Stripe Testing & decline simulation — https://docs.stripe.com/testing
- Stripe India recurring payments / RBI e-mandates — https://docs.stripe.com/india-recurring-payments
- Razorpay Subscriptions test mode & retry/halt lifecycle — https://razorpay.com/docs/payments/subscriptions/test/
- Cashfree Subscription charge & retry policy — https://www.cashfree.com/docs/payments/subscription/charge
- Recurly UPI AutoPay integration — https://docs.recurly.com/recurly-subscriptions/docs/upi-autopay
- Recurly churn management product claims — https://recurly.com/product/churn-management/
- Chargebee dunning guide — https://www.chargebee.com/blog/dunning-management-for-saas-business/
- Oracle Advanced Collections (promise-to-pay processing) — https://docs.oracle.com/cd/E18727_01/doc.121/e13451/T379880T379887.htm
- HighRadius AR software — https://www.highradius.com/product/accounts-receivable-software/
 
**Academic / research**
- Cash-collection ML on invoices (Itaú; XGBoost/RF) — https://arxiv.org/pdf/1912.10828
- Akerkar et al. context via UCI Online Shoppers (Sakar et al., Neural Comput & Applic 2018) — https://www.kaggle.com/datasets/henrysue/online-shoppers-intention

**Industry reports & news**
- NPCI UPI AutoPay failure reporting (Aug 2025 data) — https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html (also HT Syndication copy)
- NPCI Aug 2025 rule summary — https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/
- RBI e-mandate framework summaries — https://www.rocketpay.co.in/blog/what-is-upi-autopay-mandate ; https://upstox.com/learning-center/personal-finance/rbi-s-new-e-mandate-rules/article-1569/
- UPI AutoPay integration reality (2018–2026 rules) — https://vistarkriya.com/website/blog/post.php?slug=upi-autopay-integration-for-business-what-you-need-to-know-before-building-2026
- UPI AutoPay design/failure guidance — https://productgrowth.in/insights/fintech/upi-autopay-guide/
- Atradius Payment Practices Barometer (Western Europe 2025) — https://atradiuscollections.com/us/knowledge-and-research/reports/b2b-payment-practices-trends-western-europe-2025
- AR statistics compilation — https://upflow.io/blog/ar-collections/13-accounts-receivable-cash-collection-statistics-2024 ; https://www.einvoicegenerator.com/blog/late-payment-statistics
- Involuntary churn evidence — https://www.butterpayments.com/glossary/involuntary-churn/ ; https://www.get.pelcro.com/post/involuntary-churn-hidden-revenue-leaks-in-the-subscription-business-model ; https://www.slickerhq.com/resources/blog/subscription-churn-rate-guide (vendor)
- Soft/hard decline doctrine — https://solidgate.com/blog/how-to-manage-card-declines-and-recover-lost-revenue ; https://www.tagada.io/glossary/soft-decline ; https://paymid.com/soft-declines-vs-hard-declines-in-payments/ (vendor trade content)
- Stripe recovery performance claims/audits — https://www.reduxpayments.com/blog/stripe-smart-retries-explained ; https://churnward.com/blog/stripe-smart-retries/ ; https://recovamrr.com/blog/stripe-failed-payment-recovery ; https://recoverstripe.com/blog/stripe-failed-payment-recovery.html ; https://getchurnshield.com/blog/stripe-smart-retries-vs-custom-retry-logic.html ; https://revova.io/blog/stripe-smart-retries-explained (all vendor/adjacent — labeled)
- Cart abandonment evidence — https://contentsquare.com/guides/cart-abandonment/reasons/ ; https://www.emarketer.com/content/extra-costs-are-the-top-reason-consumers-abandon-online-carts ; https://christopholivierconsulting.com/cart-abandonment-statistics/
- Cart-recovery benchmarks — https://www.darkroomagency.com/observatory/abandoned-cart-email ; https://ustechautomations.com/resources/blog/ecommerce-cart-abandonment-automation-comparison ; https://www.geysera.com/blog/abandoned-cart-email/ (benchmark carriers; Klaviyo/Omnisend underlying data)
- Retry ROI scenario modeling — https://www.slickerhq.com/blog/soft-decline-retry-strategies-saas-cfos-q3-2025-guide (vendor-modeled)
- Razorpay recovery claims — https://razorpay.com/blog/cheapest-payment-gateway-for-recurring-billing-e-nach-upi-autopay-and-subscription (vendor)

**Dataset sources**
- REES46 cosmetics events (~20M) — https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop
- REES46 electronics events (~900K) — https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-electronics-store
- UCI Online Shoppers Intention — https://www.kaggle.com/datasets/henrysue/online-shoppers-intention
- UPI Transactions 2024 (synthetic, CC0) — https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset
- Digital Wallet Transactions (synthetic, MIT) — https://www.kaggle.com/datasets/harunrai/digital-wallet-transactions/data
- Financial Transactions Analytics (Apache 2.0) — https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets/data
- IBM Late Payment Histories — https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data
- Invoice payment-date dataset (CC BY-NC 4.0) — https://www.kaggle.com/datasets/pradumn203/payment-date-prediction-for-invoices-dataset

**Competitor / market**
- Dunning tool landscape — https://fintechspecs.com/blog/best-dunning-tools-saas/
- Recovery platform comparisons — https://www.slickerhq.com/resources/blog/stripe-smart-retries-vs-third-party-ai-retry-engines-2025-data-driven-comparison ; https://www.flycode.com/blog/top-payment-recovery-platforms-2026-comparison-chart-success-rate-stats ; https://www.slickerhq.com/resources/blog/best-payment-recovery-platforms-saas (vendor-authored comparisons — biased-source caveat applies)
- Voice/collections AI — https://yespress.io/skit-ai ; https://skit.ai/resource/case-studies/ai-debt-collection-auto-loan-delinquency/ ; https://edas.tech/debt-collection-voice-bot/
- Promise-to-pay products — https://symphonix.com/blog/automating-collections-with-promise-to-pay-in-digital-lending-2.0 ; https://www.irisinsights.ai/promise-keeper

*End of Phase 1 document. Phase 2 (architecture, schema, model and system design) must not begin until the questions in §21 are answered in writing.*
