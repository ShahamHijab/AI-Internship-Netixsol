# Monitoring & Maintenance Checklist

## Live health
- Track response latency p50/p95; alert if p95 > 3 seconds for 15 minutes.
- Track API 5xx rate; alert at >2% over 15 minutes.
- Track tool/model error rate; alert at >3% daily.
- Track request volume and repeated probing/rate abuse.

## Safety / scope
- Track off-topic leak rate; alert on any confirmed off-topic answer.
- Re-run at least 10 prompt-injection cases after routing/prompt changes.
- Keep refusal and prediction disclaimer centralized.

## Prediction quality
- After each completed round, append actual results and recompute leakage-safe features.
- Track accuracy, macro F1, Brier/calibration and confusion matrix.
- Alert on a rolling accuracy drop >5 percentage points versus the prior evaluation window or material calibration deterioration.

## Weekly refresh loop
1. Ingest completed matches.
2. Validate schema, duplicates, dates and team aliases.
3. Recompute rolling/form/H2H/ladder features using only prior information.
4. Run the 25+ regression suite.
5. Compare candidate model with the ladder baseline.
6. Retrain only if acceptance checks pass.
7. Version model, feature schema and data timestamp.
8. Deploy with rollback available and record the new metrics.
