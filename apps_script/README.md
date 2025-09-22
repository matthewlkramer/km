# Google Workspace Add-on

This Apps Script project provides the Drive add-on for editing metadata and triggering the indexer.

## Setup

1. Create a new Apps Script project bound to your Workspace domain.
2. Copy the contents of `Code.gs` and `appsscript.json` into the project.
3. Configure script properties:
   - `SUPABASE_URL`: Base URL of the Supabase project.
   - `SERVICE_JWT`: Signed JWT allowing the add-on to call Supabase and the worker.
   - `WORKER_ENDPOINT`: HTTPS endpoint for the Cloud Run worker.
4. Enable the Drive add-on deployment in the Apps Script editor.

## Usage

- Selecting a folder in Drive surfaces its metadata.
- The “Re-index” button manually triggers the Cloud Run worker for the selected item.
