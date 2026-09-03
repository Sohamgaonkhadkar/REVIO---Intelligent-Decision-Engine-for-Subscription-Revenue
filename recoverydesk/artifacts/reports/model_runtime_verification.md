# Runtime model verification — supplied XGBoost artifact

| check | evidence |
|---|---|
| PASS | 1. artifact path (app resolver) | resolved=/home/user/uploads/xgboost_native_categorical_c5.json (registered=artifacts/models/c5/xgboost_native_categorical_c5.json) |
| PASS | 2. artifact exists | 25,407,466 bytes |
| PASS | 3. SHA-256 matches registry | 9434606cd1e443e3e2c4967e… |
| PASS | 4a. independent Booster loads (native JSON) | num_features=32, trees=1256, booster=gbtree, objective=binary:logistic |
| PASS | 4b. booster is the app scorer's booster class | app bundle carries an xgboost.Booster (not a stub) |
| PASS | 5. activation gate passes | 16/16 checks; reason='' |
| PASS | 6. feature contract matches artifact schema (names+order) | 32 features, identical order |
| PASS | 7. categorical config matches | 12 'c'-typed columns in model == 12 in schema |
| PASS | 8. real inference executed (app scorer, live case) | case=sim:tc:4299ea1a83 · 2 legal candidates scored · model=c5-xgboost-native-categorical v1.0.0 |
| PASS | 9. independent Booster prediction == app scorer output | max |Δp̂| = 0.00e+00 over 2 candidates; p̂ range [0.0199, 0.0199] |
| PASS | 10. scorer p̂ appears in decision record (chosen + all scored atoms) | chosen=STOP_CASE p̂=policy action · policy=ml-ev-v1 · fallback=False |
| PASS | 11. EV layer consumes scorer p̂ (scored atom) | atom=RETRY@W11_14 expected_gain=4.47 ev=-1.53 |
| PASS | 11b. journaled atoms: EV == p̂·₹·margin − costs (production records) | 180 scored journaled atoms re-verified; max|Δgain|=0.0000 max|Δev|=0.0000; e.g. sim:upi_autopay:22ba4a992d2d SEND_REMINDER@email p̂=0.0674 ev=₹4.90 |
| PASS | 12. PostgreSQL decision records carry the real model id; fallback explicitly distinct | c5-xgboost-native-categorical ×28 (fallback-flagged 0); none ×6 (fallback-flagged 0) |

## Failure path — gate refuses, fallback is explicit, constraints hold

| check | evidence |
|---|---|
| PASS | F1a. mismatched artifact fails the gate | failed: ['feature_names_compatible', 'feature_order_compatible'] |
| PASS | F1b. scorer falls back, explicitly flagged | model_id=doctrine-fallback reason='failed checks: feature_names_compatible, feature_order_compatible' |
| PASS | F1c. fallback decision is flagged (policy=doctrine-b2, fallback=true) | policy=doctrine-b2 |
| PASS | F2. unavailable artifact blocks activation | failed: ['model_loaded'] |
| PASS | F3. constraints enforced under fallback (retry-budget-exhausted still denied) | engine verdict: ['R-BUDGET-RETRY-1P3'] · pipeline atoms denied: 3 |

**Result: 0 failures.** Scorer identity: the supplied `xgboost_native_categorical_c5.json` (sha256 `9434606cd1e443e3…`) loaded through the application's resolver, gate-passed, producing the p̂ values in live decision records and the EV inputs.
