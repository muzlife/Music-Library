# Compact Stack Control Height Alignment Design

## Summary
Unify the vertical height of inputs and buttons inside `.compact-stack-actions` by aligning everything to the input field height. Also align paired text-box + button widths to be equal where required. This removes the visual mismatch seen in the “등록 방식” row and similar action rows within the admin shell (including manage subviews).

## Goals
- Make input/select/button heights match within `.compact-stack-actions`.
- Use input field height as the baseline (lower profile).
- Apply consistently across all admin-shell `.compact-stack-actions` blocks.
- Ensure paired text-box + button rows can be displayed with equal widths.

## Non-Goals
- Change global input/button sizing outside `.compact-stack-actions`.
- Redesign spacing or typography globally.

## Design Approach
Introduce a scoped control-height token and apply it only inside `body[data-shell-mode="admin"] .compact-stack-actions` (admin shell) to avoid side effects outside `body[data-shell-mode="admin"]`.

### CSS tokens
- Admin/manage mode: `--compact-control-height: 28px`

### Scoped rules
Within `body[data-shell-mode="admin"] .compact-stack-actions`:
- `input` (excluding checkbox/radio/file/hidden), `select` get `min-height` and consistent padding
- `button`, `.btn` use `min-height` and padding tuned to match input height
- `.compact-line` is vertically centered and uses the same `min-height` for single-line alignment
  - It may grow vertically when content wraps
- `textarea` is out of scope unless a concrete `.compact-stack-actions textarea` use case is identified

### Equal-width modifier
When a row needs equal-width pairing (e.g., text box + button), apply a modifier class:
- `.compact-stack-actions--equal`
This switches the actions container to a 2-column grid and makes both items fill their column widths.

### Layout intent
- Buttons should be visually the same height as adjacent inputs.
- Text-only blocks (`.compact-line`) should align to the same baseline.
- Paired text-box + button rows should be equal width.
- Preserve existing horizontal spacing and alignment.

## Affected Areas
- All admin-shell `.compact-stack-actions` blocks, including:
  - Collector/linked goods registration method row
  - Product relation action rows
  - Collectibles manage mapping/action rows

## Acceptance Criteria
- Within any admin-shell `.compact-stack-actions` container, input/select fields and buttons appear same height.
- `.compact-line` aligns to the same single-line height but can grow with wrapped content.
- No change to control sizes outside `body[data-shell-mode="admin"] .compact-stack-actions`.
- `textarea` and `input[type=checkbox|radio|file|hidden]` remain unaffected by the new alignment rules.
- Rows marked with `.compact-stack-actions--equal` render the text box and button at equal widths.
- 1080px and 760px widths render without overlap or clipping.

## Risks / Mitigations
- **Risk:** Buttons with icons or long labels could appear vertically cramped.
  - **Mitigation:** Allow slight padding adjustments within the scoped rule only.

## Verification
- Add a regression test in `tests/test_admin_density_compaction.py` to assert presence of the new scoped CSS rules.
- Add negative assertions that `textarea` and `input[type=checkbox|radio|file|hidden]` are not targeted by the new scoped selector.
- Add assertions for the `.compact-stack-actions--equal` modifier and its CSS rule.
- Manual visual check at 1080px and 760px on admin/manage views:
  - Linked goods “등록 방식”
  - Product relation action rows
  - Collectibles manage mapping/action rows
  - One long-label/icon-button case
  - One wrapped `.compact-line` case
