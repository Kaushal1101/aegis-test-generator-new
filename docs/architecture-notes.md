# Architecture Notes

## Residual Risks

### 2026-04-22 - Evaluation extraction

- `EvaluationResult` and `DiffResult` currently duplicate the same field shape.
- This is acceptable during migration but creates a drift risk if one type changes and the other is not updated.
- Mitigation later: designate one canonical result type (or shared base) and keep compatibility adapters at boundaries only.
