# Knowledge Management System Implementation

This repository contains assets for deploying the Knowledge Management (KM) platform described in `docs/knowledge_management_plan.md`.

## Contents

- `docs/knowledge_management_plan.md` – Architectural blueprint and roadmap.
- `supabase/` – Database schema and instructions for Supabase.
- `worker/` – Cloud Run worker that processes Google Drive changes, generates embeddings, and updates Supabase.
- `apps_script/` – Google Workspace Add-on for editing metadata and manually triggering re-indexing from Drive.

## Getting Started

1. Apply the Supabase schema using the SQL script.
2. Configure and deploy the Cloud Run worker (see `worker/README.md`).
3. Deploy the Apps Script project to surface metadata controls inside Google Drive.

These components work together to ingest Drive content, enrich it with metadata, and expose it to retrieval-augmented applications.
