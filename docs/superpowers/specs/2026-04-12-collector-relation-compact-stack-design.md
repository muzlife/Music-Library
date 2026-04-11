# Collector/Relation Compact Stack Design

## Summary
Tighten the “Collector/Relation” areas in the admin manage view by restructuring them into compact two-column stacks with action clusters on the right. The goal is to eliminate large vertical gaps while keeping all information visible and reducing scanning time for operators.

## Goals
- Eliminate empty vertical space in collector/relationship blocks without hiding fields.
- Preserve all existing fields, labels, and actions (no data loss).
- Increase scannability by aligning labels/inputs into two-column layouts.
- Keep consistent density with the recent admin compaction changes.

## Non-Goals
- No change to underlying data, APIs, or validation.
- No new features or workflows beyond layout and spacing adjustments.
- No changes to non-admin pages.

## Scope
Applies to the following areas in the admin manage view (as shown in the screenshot):
- Collector relation block (연계 컬렉터블)
- Master-linked collector relation block (마스터 연계 컬렉터블)
- Product relationship block (상품 관계: series / boxset / related releases)

## Layout Direction (Compact Stack)
### High-level structure
- Each block becomes a 2-column grid:
  - **Left column:** text/description + main input(s)
  - **Right column:** action buttons and short helper fields (e.g., “등록 방식”)
- Visual separators should be tightened: reduce padding and margin between block header, description, and fields.

### Content placement rules
- Keep the block title and short description at top-left.
- Place the primary input line(s) directly below the description.
- Keep action buttons aligned to the right, vertically centered relative to the inputs.
- Where there are multiple action buttons, stack them horizontally within the right column.

## Density Rules
- Reduce vertical spacing between:
  - Section title → description
  - Description → inputs
  - Inputs → action buttons
- Maintain readable label size and input size (no reduction beyond current admin density tokens).
- All fields must remain visible without collapsing/accordion behavior.

## UX Considerations
- The right-column action cluster should be visually grouped so operators can immediately see “what to do next.”
- No button should appear detached from its related input.
- Preserve existing helper text but allow it to wrap or align beneath the input if needed.

## Success Criteria
- The collector/relation section height is reduced by ~30–40% on desktop without hiding content.
- All fields and actions remain visible and operable.
- Layout remains readable at 1080px width (no overlap or overflow).

## Testing / Verification
- Visual inspection at 1080px and 760px (ensure no overflow).
- No functional regression in button actions or input editing.

