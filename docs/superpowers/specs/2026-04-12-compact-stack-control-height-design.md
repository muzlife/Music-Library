# Compact Stack Control Height Alignment Design

## Summary
Unify the vertical height of inputs and buttons inside `.compact-stack-actions` by aligning everything to the input field height. This removes the visual mismatch seen in the “등록 방식” row and similar action rows across the admin/manage UI.

## Goals
- Make input/select/button heights match within `.compact-stack-actions`.
- Use input field height as the baseline (lower profile).
- Apply consistently across all `.compact-stack-actions` blocks.

## Non-Goals
- Change global input/button sizing outside `.compact-stack-actions`.
- Redesign spacing or typography globally.

## Design Approach
Introduce a scoped control-height token and apply it only inside `.compact-stack-actions` to avoid side effects.

### CSS tokens
- Default: `--compact-control-height: 30px`
- Admin mode: `--compact-control-height: 28px`

### Scoped rules
Within `.compact-stack-actions`:
- `input`, `select`, `textarea` get `min-height` and consistent padding
- `button`, `.btn` use `min-height` and padding tuned to match input height
- `.compact-line` is vertically centered and uses the same `min-height`

### Layout intent
- Buttons should be visually the same height as adjacent inputs.
- Text-only blocks (`.compact-line`) should align to the same baseline.
- Preserve existing horizontal spacing and alignment.

## Affected Areas
- All `.compact-stack-actions` blocks, including:
  - Collector/linked goods registration method row
  - Product relation action rows
  - Any other compact-stack action groups

## Acceptance Criteria
- Within any `.compact-stack-actions` container, input fields and buttons appear same height.
- No change to control sizes outside `.compact-stack-actions`.
- 1080px and 760px widths render without overlap or clipping.

## Risks / Mitigations
- **Risk:** Buttons with icons or long labels could appear vertically cramped.
  - **Mitigation:** Allow slight padding adjustments within the scoped rule only.

## Verification
- Add a regression test in `tests/test_admin_density_compaction.py` to assert presence of the new scoped CSS rules.
- Manual visual check at 1080px and 760px on admin/manage views.
