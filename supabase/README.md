# Supabase Configuration

Run the SQL in `schema.sql` inside your Supabase project's SQL editor. The script enables required extensions, creates metadata tables, defines helper functions, and sets up row-level security policies aligned with the KM design plan.

## Applying the schema

1. Open the Supabase dashboard and navigate to **SQL** > **New query**.
2. Paste the contents of `schema.sql` and execute it.
3. Review the tables in the database explorer to verify creation.
4. Seed `people`, `teams`, and `geographies` tables with your organisation-specific data.

## Environment variables for Edge Functions / Workers

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `OPENAI_API_KEY` (optional for embeddings)

These variables should also be provided to the Cloud Run worker and Apps Script integrations.
