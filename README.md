# Music Library Management Console

Internal console focused on library management: metadata editing, placement operations, and source enrichment in one workflow.

## Core Management Workflows

- Media search, manage, and register flows for owned items.
- Cabinet/slot placement workflow with operational dashboard views.
- Source enrichment and candidate replacement (Discogs, ManiaDB, Aladin).

## Data & Quality Operations

- Master grouping and metadata correction.
- Exception handling for missing fields or source mismatches.
- Consistent QA vs Production separation to protect data integrity.

## Ops Notes (Minimal)

- Services are intended to auto-start via macOS `launchd`.
- Cloudflare tunnel templates live under `deploy/templates/cloudflare/`.
- Use separate runtime paths per environment (QA vs Production).

## Quick Links

- Management Tool Manual: `docs/management_tool_manual.md`
- macOS QA/Prod Runbook: `docs/macos_qa_prod_runbook.md`
- ERD Summary: `docs/library_erd_operator.md`
- ERD Detail: `docs/library_erd.md`
- Go-live Checklist: `docs/go_live_checklist.md`
- Purchase Mail Import: `docs/purchase_mail_import.md`
