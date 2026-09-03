# Revenue Recovery Reference Guidance

## Quiet hours
To comply with telecom regulations and ensure a respectful customer experience, all automated recovery outreach is subject to strict quiet hours. No payment notifications, reminders, or contact attempts may be dispatched between 21:00 (9:00 PM) and 08:00 (8:00 AM) IST. Any scheduled actions falling within this window are automatically deferred to the next legal window. 

## Mandate pause
When a mandate (such as UPI AutoPay or Card Standing Instruction) is flagged as paused by the issuing bank, it signifies a temporary suspension by the customer or bank, not a hard revocation. In these cases, the system should not aggressively retry the mandate but instead send a specific notification guiding the user to unpause or update their mandate. The failure class is marked as MANDATE_PAUSED.

## Cooldowns
Between consecutive payment retry attempts on the same mandate, a mandatory minimum cooldown period of 20 hours is enforced. This prevents aggressive polling which could result in bank-side blocking or rate-limiting of the merchant identifier. Rule engines explicitly deny retry actions proposed before this cooldown expires.

## Contact limits
To prevent customer fatigue and spam complaints, the global constraint engine enforces strict contact limits per recovery case. A maximum of 2 customer contacts (e.g., SMS, email, push notifications) are permitted per case lifecycle. Once this threshold is reached, any further contact intents are structurally denied.

## Escalation policy
Cases are escalated to human agents (Support/Ops) under specific triggering conditions. The primary escalation policy triggers when the total amount at risk exceeds ₹15,000 and automated retries have failed, or when the rule engine determines that the maximum Expected Value (EV) of any available automated action falls below the escalation threshold. Escalated cases are frozen for automated actions until human intervention occurs.

## PSP reasons
Payment Service Providers (PSPs) and gateways return specific reason codes on failure. These raw codes are mapped into normalized failure classes. 
- `INSUFFICIENT_FUNDS`: The account lacks the balance required.
- `RATE_LIMIT`: The gateway or bank has temporarily throttled requests.
- `BANK_TECHNICAL`: The issuer bank is experiencing downtime.
- `MANDATE_CLOSED`: The customer has permanently revoked the mandate.
Understanding PSP reasons is critical for the ML models to predict recovery probability correctly.
