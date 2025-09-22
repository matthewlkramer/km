# Knowledge Management System Implementation Plan

## Overview
This document translates the high-level requirements into an actionable plan for building the knowledge management (KM) system that indexes Google Drive content, manages structured metadata, and feeds an AI assistant backed by retrieval augmented generation (RAG).

## Architecture Summary
- **Google Workspace Layer**
  - Drive houses the authoritative documents and folder hierarchy.
  - An Apps Script Workspace Add-on provides in-Drive UI for metadata editing, content review status, and manual re-index triggers.
- **Backend Services**
  - **Supabase** serves as the metadata and operational event store (PostgreSQL + pgvector + Auth + Edge Functions).
  - **Processing Worker (Cloud Run)** handles Drive change notifications, content extraction, embedding generation, and search index updates.
- **AI Assistant**
  - RAG pipeline built atop Supabase pgvector and Postgres full-text search.
  - Feedback capture loop persists ratings and optionally promotes Q&A pairs into curated KM content.

The diagram below summarises the data flows.

```
Drive -> Apps Script Add-on -> Supabase REST/RPC
Drive -> Cloud Run Worker -> Supabase (metadata + embeddings)
Supabase -> AI Assistant (retrieval + chat)
AI Assistant -> Supabase (feedback + Q&A capture)
```

## Folder Hierarchy & `km.page`
- Every Drive folder is treated as a wiki section.
- If a folder contains a `km.page` file, its contents become the overview page.
- If absent, the system auto-generates a listing based on folder metadata.
- Imported `km.page` files should use front matter to declare metadata (see schema below).

## Metadata Schema
Store metadata in front matter within each `km.page` or content file, mirroring the same record inside Supabase for querying.

```yaml
core: true
audience:
  - partners
school_profile:
  age_levels: ["primary", "upper_el"]
  geography: ["us_ma"]
  governance: ["charter"]
  vouchers: false
created_by: person_id
maintained_by: team_id
last_reviewed_at: 2024-02-18
```

### Supabase Tables
1. **files**
   - `id` (UUID) – internal primary key.
   - `drive_id` (text, unique) – Google Drive file ID.
   - `parent_drive_id` (text) – parent folder.
   - `path` (ltree) – hierarchical path constructed from Drive tree.
   - `mime_type` (text).
   - `title` (text).
   - `checksum` (text) – Drive file MD5 or export hash.
   - `modified_at` (timestamptz).
   - `last_reviewed_at` (timestamptz).
   - `core` (boolean).
   - `audience` (text[] check subset of {partners, schools}).
   - `age_levels` (text[] check subset of {infants_toddlers, primary, lower_el, upper_el, adolescent}).
   - `geographies` (text[] referencing `geographies` table).
   - `governance_models` (text[] subset of {charter, independent}).
   - `vouchers` (boolean).
   - `created_by` (uuid references `people`).
   - `maintained_by` (uuid references `teams`).
   - `synced_at` (timestamptz) – when last processed.
2. **chunks**
   - `id`, `file_id` FK, `chunk_index`, `content`, `embedding` (vector), `tokens`.
3. **feedback**
   - `id`, `user_id`, `question`, `answer_id` (FK to stored answers), `rating` enum (unhelpful, not_bad, super_helpful), `store_as_knowledge` (boolean), `created_at`.
4. **answers**
   - Store conversational answers when flagged to persist (with reference to source files/chunks).
5. **people / teams / geographies** dimension tables for normalized references.

Enable Supabase Row Level Security (RLS) to enforce visibility based on audience, school profile, and user roles.

## Drive Indexing Workflow
1. **Bootstrap**
   - Service account with domain-wide delegation enumerates the KM root folder using Drive API `files.list` with `q` filtering by parents.
   - For each file/folder, store metadata in `files` table and enqueue extraction if MIME type is supported.
2. **Change Tracking**
   - Register Drive Changes API watch channel; persist `startPageToken` in Supabase.
   - Worker pulls incremental changes, updating records and re-enqueueing extraction when `md5Checksum` or modified time change.
3. **Content Extraction**
   - Docs/Sheets/Slides: export to Markdown/plain text via Drive `export` endpoint.
   - PDFs/images: send to OCR pipeline when needed.
   - Store raw text for auditing (Supabase storage) and break into semantic chunks (e.g., 800 token windows with 200 token overlaps).
4. **Embedding Generation**
   - Call embeddings provider (OpenAI, Vertex AI, or Cohere) for each chunk.
   - Upsert chunk embeddings into `pgvector` column.
   - Index chunk text with Postgres full-text search (tsvector) for fallback keyword retrieval.

## AI Retrieval & Chat
- Retrieval pipeline queries pgvector using similarity, filters by metadata (audience, age level, geography, governance, vouchers) matching the user’s context.
- Combine with keyword search for hybrid scoring; re-rank results using metadata weights (e.g., prefer `core=true`).
- Assemble context windows for LLM prompt, including breadcrumbs and `last_reviewed_at`.

### Feedback Capture
- Chat UI prompts for rating after each answer.
- Submit rating to Supabase `feedback` table.
- If user selects “Store as knowledge”, create an `answers` record and notify maintainers (via email/Slack using Supabase Edge Function) for review.
- Upon approval, automation writes a new `km.page` draft into appropriate Drive folder and triggers re-index.

## Apps Script Workspace Add-on
- **Functions**
  - Folder navigator: lists child items, displays overview (rendered from `km.page`).
  - Metadata editor: form bound to Supabase REST endpoints to read/write metadata fields.
  - Review workflow: buttons for “Mark as Reviewed” updating `last_reviewed_at`.
  - Manual re-index trigger: sends POST to Cloud Run worker for a specific Drive file ID.
- **Authentication**
  - Use Apps Script’s OAuthScopes for Drive read/write and fetch to Supabase (via service account or OAuth service).
  - For service account access, store signed JWT in Apps Script Properties and exchange for Supabase service-role key via Edge Function.

## Supabase Configuration Steps
1. Create project and enable `pgvector` extension.
2. Define tables and RLS policies.
3. Configure Storage buckets for raw exports and archived answers.
4. Implement Edge Functions:
   - `drive-webhook`: receives Change notifications, validates tokens, enqueues tasks (e.g., publishes to Cloud Tasks or Supabase queue).
   - `metadata-sync`: invoked by Apps Script to update metadata with validations.
   - `feedback-handler`: ingests feedback submissions.

## Cloud Run Worker
- Node.js or Python service that exposes endpoints to handle webhook events and manual re-index requests.
- Uses Supabase service-role key to read/write tables, fetches Drive content with service account credentials, and calls embedding API.
- Maintains idempotent processing by comparing checksums before updating chunks.

## Security & Compliance
- Restrict Drive access to specific shared drive or folder with least privilege.
- Use Supabase RLS + JWT to ensure only authorized users can view sensitive content.
- Log all sync operations and feedback events for auditing.

## Implementation Roadmap
1. **Foundation**
   - Setup Supabase project, tables, and RLS policies.
   - Build Cloud Run worker skeleton with Drive auth and Supabase connectivity.
2. **Indexing MVP**
   - Implement bootstrap crawler, text extraction, chunking, embeddings, and search endpoints.
3. **Apps Script Add-on MVP**
   - Navigation UI using `km.page` overview, metadata display.
   - Edit metadata and mark as reviewed.
4. **AI Assistant Integration**
   - Build retrieval API (hybrid search) and chat front-end.
   - Capture feedback and optional knowledge promotion.
5. **Feedback Promotion Workflow**
   - Edge Function + Drive write-back to create draft `km.page` from high-rated Q&A.
6. **Polish & Monitoring**
   - Add analytics dashboards (e.g., Supabase + Metabase).
   - Implement alerting for failed syncs or outdated content (last reviewed > threshold).

## Open Questions
- Decide on embedding provider and throughput vs. cost trade-offs.
- Define geographies taxonomy and governance model enumerations.
- Determine review SLAs for knowledge promotion workflow.

## Repository Deliverables
- [`supabase/schema.sql`](../supabase/schema.sql) – executable SQL creating tables, helper functions, and RLS policies described above.
- [`worker/`](../worker) – FastAPI-based Cloud Run worker implementing Drive webhooks, manual re-indexing, and content processing.
- [`apps_script/`](../apps_script) – Google Workspace Add-on manifest and scripts for folder navigation and manual sync triggers.

