# Dark Mode Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Night theme에서 패널 깊이 차를 더 분명하게 만들어 가독성을 높인다.

**Architecture:** 기존 theme token 구조를 유지한 채 night token만 조정하고, shell/admin/dashboard가 토큰을 통해 함께 개선되도록 한다. 토큰만으로 부족한 경우에만 국소 surface 스타일을 보강한다.

**Tech Stack:** Static HTML/CSS, pytest snapshot/string assertions

---

### Task 1: Lock Depth A Expectations

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
- Test: `/Volumes/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Add/adjust assertions for night theme token values and night surface expectations in the shell/admin/dashboard theme tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_ops_shell_bootstrap.py -k 'index_theme_tokens_define_day_and_night_surface_modes or shell_utility_and_tabs_use_theme_tokens or dashboard_slot_and_shelf_surfaces_use_theme_tokens'`

Expected: FAIL because current night values still match the flatter depth set.

- [ ] **Step 3: Write minimal implementation**

Update only the relevant night theme token values and any necessary token-fed surface rules in `/Volumes/Works/07.hahahoho/app/static/index.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_ops_shell_bootstrap.py -k 'index_theme_tokens_define_day_and_night_surface_modes or shell_utility_and_tabs_use_theme_tokens or dashboard_slot_and_shelf_surfaces_use_theme_tokens'`

Expected: PASS

### Task 2: Verify Adjacent Night Surfaces

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/app/static/index.html`
- Test: `/Volumes/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write the failing regression expectation**

Ensure adjacent shell/admin result surface tests reflect the new night depth without changing semantics.

- [ ] **Step 2: Run targeted test selection**

Run: `pytest -q tests/test_ops_shell_bootstrap.py -k 'gallery_and_album_result_surfaces_use_theme_tokens or manage_lookup_and_goods_surfaces_use_theme_tokens or index_header_utility_hierarchy_uses_meta_and_action_modifier_groups'`

Expected: FAIL if any surface still uses the flatter tone.

- [ ] **Step 3: Minimal CSS adjustment**

Adjust only the minimal night token-fed surfaces required for visual consistency.

- [ ] **Step 4: Re-run the targeted tests**

Run: `pytest -q tests/test_ops_shell_bootstrap.py -k 'gallery_and_album_result_surfaces_use_theme_tokens or manage_lookup_and_goods_surfaces_use_theme_tokens or index_header_utility_hierarchy_uses_meta_and_action_modifier_groups'`

Expected: PASS

### Task 3: Final Verification

**Files:**
- Test: `/Volumes/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Run the final grouped verification**

Run: `pytest -q tests/test_ops_shell_bootstrap.py -k 'index_theme_tokens_define_day_and_night_surface_modes or shell_utility_and_tabs_use_theme_tokens or dashboard_slot_and_shelf_surfaces_use_theme_tokens or gallery_and_album_result_surfaces_use_theme_tokens or manage_lookup_and_goods_surfaces_use_theme_tokens or index_header_utility_hierarchy_uses_meta_and_action_modifier_groups'`

Expected: PASS with only existing deprecation warnings.

- [ ] **Step 2: Summarize actual scope**

Report which token groups changed and any residual visual areas intentionally left untouched.
