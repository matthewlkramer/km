# Cloud Run Worker

This package provides the Drive change processor that orchestrates metadata sync, text extraction, chunking, embedding generation, and Supabase updates.

## Local development

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Export the required environment variables:

   ```bash
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_SERVICE_ROLE_KEY="service-role-key"
   export KM_ROOT_DRIVE_ID="<drive-folder-id>"
   export GOOGLE_SERVICE_ACCOUNT='{"type": "service_account", ...}'
   # optional
   export OPENAI_API_KEY="sk-..."
   export MANUAL_TRIGGER_TOKEN="super-secret"
   ```

3. Start the API locally:

   ```bash
   uvicorn worker.app:app --reload --port 8080
   ```

4. Trigger a bootstrap crawl:

   ```bash
   curl -X POST http://localhost:8080/bootstrap -H "Authorization: Bearer $MANUAL_TRIGGER_TOKEN"
   ```

## Deployment

Deploy the service to Cloud Run using a container image. The worker expects the environment variables above to be provided via Cloud Run service configuration or Secret Manager.
