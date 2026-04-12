# Compact Stack Control Height Alignment Design

## Summary
Unify the vertical height of inputs and buttons inside `.compact-stack-actions` by aligning everything to the input field height. This removes the visual mismatch seen in the “등록 방식” row and similar action rows across admin/manage views only.

## Goals
- Make input/select/button heights match within `.compact-stack-actions`.
- Use input field height as the baseline (lower profile).
- Apply consistently across all `.compact-stack-actions` blocks.

## Non-Goals
- Change global input/button sizing outside `.compact-stack-actions`.
- Redesign spacing or typography globally.

## Design Approach
Introduce a scoped control-height token and apply it only inside `body[data-shell-mode="admin"] .compact-stack-actions` to avoid side effects outside admin/manage views.

### CSS tokens
- Admin/manage mode: `--compact-control-height: 28px`

### Scoped rules
Within `body[data-shell-mode="admin"] .compact-stack-actions`:
- `input` (excluding checkbox/radio/file/hidden), `select` get `min-height` and consistent padding
- `button`, `.btn` use `min-height` and padding tuned to match input height
- `.compact-line` is vertically centered and uses the same `min-height` for single-line alignment
  - It may grow vertically when content wraps

### Layout intent
- Buttons should be visually the same height as adjacent inputs.
- Text-only blocks (`.compact-line`) should align to the same baseline.
- Preserve existing horizontal spacing and alignment.

## Affected Areas
- All admin/manage `.compact-stack-actions` blocks, including:
  - Collector/linked goods registration method row
  - Product relation action rows
  - Collectibles manage mapping/action rows

## Acceptance Criteria
- Within any admin/manage `.compact-stack-actions` container, input fields and buttons appear same height.
- `.compact-line` aligns to the same single-line height but can grow with wrapped content.
- No change to control sizes outside `body[data-shell-mode="admin"] .compact-stack-actions`.
- 1080px and 760px widths render without overlap or clipping.

## Risks / Mitigations
- **Risk:** Buttons with icons or long labels could appear vertically cramped.
  - **Mitigation:** Allow slight padding adjustments within the scoped rule only.

## Verification
- Add a regression test in `tests/test_admin_density_compaction.py` to assert presence of the new scoped CSS rules.
- Add a negative assertion that global input/button sizing is unchanged (no unscoped selector).
- Manual visual check at 1080px and 760px on admin/manage views:
  - Linked goods “등록 방식”
  - Product relation action rows
  - Collectibles manage mapping/action rows
