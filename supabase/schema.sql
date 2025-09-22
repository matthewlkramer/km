-- Supabase schema for Knowledge Management system

create extension if not exists "uuid-ossp";
create extension if not exists vector;
create extension if not exists ltree;

-- Dimension tables
create table if not exists people (
    id uuid primary key default uuid_generate_v4(),
    email text unique not null,
    full_name text not null,
    created_at timestamptz not null default now()
);

create table if not exists teams (
    id uuid primary key default uuid_generate_v4(),
    name text unique not null,
    created_at timestamptz not null default now()
);

create table if not exists geographies (
    id uuid primary key default uuid_generate_v4(),
    code text unique not null,
    name text not null
);

-- Files table mirrors Drive hierarchy and metadata
create table if not exists files (
    id uuid primary key default uuid_generate_v4(),
    drive_id text not null unique,
    parent_drive_id text,
    path ltree not null,
    mime_type text not null,
    title text not null,
    checksum text,
    modified_at timestamptz,
    last_reviewed_at timestamptz,
    core boolean not null default false,
    audience text[] not null default array[]::text[],
    age_levels text[] not null default array[]::text[],
    geographies text[] not null default array[]::text[],
    governance_models text[] not null default array[]::text[],
    vouchers boolean,
    created_by uuid references people(id),
    maintained_by uuid references teams(id),
    synced_at timestamptz,
    raw_export_path text,
    inserted_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists files_path_idx on files using gist(path);
create index if not exists files_modified_idx on files(modified_at desc);
create index if not exists files_audience_idx on files using gin (audience);
create index if not exists files_age_levels_idx on files using gin (age_levels);
create index if not exists files_geographies_idx on files using gin (geographies);
create index if not exists files_governance_idx on files using gin (governance_models);

-- Chunked text content stored for retrieval
create table if not exists chunks (
    id uuid primary key default uuid_generate_v4(),
    file_id uuid not null references files(id) on delete cascade,
    chunk_index integer not null,
    content text not null,
    tokens integer,
    embedding vector(1536),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(file_id, chunk_index)
);

create index if not exists chunks_embedding_idx on chunks using ivfflat (embedding vector_cosine_ops);
create index if not exists chunks_content_fts_idx on chunks using gin (to_tsvector('english', content));

-- Stored answers and feedback
create table if not exists answers (
    id uuid primary key default uuid_generate_v4(),
    question text not null,
    answer text not null,
    source_file_ids uuid[] not null default array[]::uuid[],
    created_by uuid references people(id),
    created_at timestamptz not null default now(),
    approved boolean not null default false,
    approved_by uuid references people(id),
    approved_at timestamptz
);

create table if not exists feedback (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references people(id),
    question text not null,
    answer_id uuid references answers(id),
    rating text check (rating in ('unhelpful', 'not_bad', 'super_helpful')),
    store_as_knowledge boolean not null default false,
    created_at timestamptz not null default now()
);

-- Utility table for Drive change tokens
create table if not exists drive_sync_state (
    id integer primary key default 1,
    start_page_token text,
    last_synced_at timestamptz
);

-- Triggers to maintain updated_at timestamps
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger files_set_updated_at
    before update on files
    for each row
    execute function set_updated_at();

create trigger chunks_set_updated_at
    before update on chunks
    for each row
    execute function set_updated_at();

-- Helper to extract array claims from JWT
create or replace function get_claim_array(claim text)
returns text[]
language plpgsql
as $$
declare
    claims jsonb;
begin
    begin
        claims := current_setting('request.jwt.claims', true)::jsonb;
    exception when others then
        return array[]::text[];
    end;

    if claims ? claim then
        return array(select jsonb_array_elements_text(claims -> claim));
    end if;
    return array[]::text[];
end;
$$;

-- Row Level Security
alter table files enable row level security;
alter table chunks enable row level security;
alter table answers enable row level security;
alter table feedback enable row level security;

-- Policies
create policy files_read
    on files
    for select
    using (
        (core = true) or
        (audience && get_claim_array('audience'))
    );

create policy files_insert_service
    on files
    for insert
    to authenticated
    with check (true);

create policy files_update_service
    on files
    for update
    to authenticated
    using (true);

create policy chunks_read
    on chunks
    for select
    using (
        exists (
            select 1 from files f
            where f.id = chunks.file_id
              and (f.core = true or f.audience && get_claim_array('audience'))
        )
    );

create policy chunks_mutate_service
    on chunks
    for all
    to authenticated
    using (true)
    with check (true);

create policy feedback_insert
    on feedback
    for insert
    to authenticated
    with check (true);

create policy feedback_read_self
    on feedback
    for select
    using (user_id::text = coalesce((current_setting('request.jwt.claims', true)::json->>'sub'), ''));

create policy answers_read
    on answers
    for select
    using (approved = true or created_by::text = coalesce((current_setting('request.jwt.claims', true)::json->>'sub'), ''));

create policy answers_insert_service
    on answers
    for insert
    to authenticated
    with check (true);

-- Stored procedures
create or replace function upsert_file_metadata(
    p_drive_id text,
    p_parent_drive_id text,
    p_path ltree,
    p_mime_type text,
    p_title text,
    p_checksum text,
    p_modified_at timestamptz,
    p_last_reviewed_at timestamptz,
    p_core boolean,
    p_audience text[],
    p_age_levels text[],
    p_geographies text[],
    p_governance_models text[],
    p_vouchers boolean,
    p_created_by uuid,
    p_maintained_by uuid,
    p_raw_export_path text
)
returns uuid
language plpgsql
as $$
declare
    v_id uuid;
begin
    insert into files as f (
        drive_id,
        parent_drive_id,
        path,
        mime_type,
        title,
        checksum,
        modified_at,
        last_reviewed_at,
        core,
        audience,
        age_levels,
        geographies,
        governance_models,
        vouchers,
        created_by,
        maintained_by,
        raw_export_path
    ) values (
        p_drive_id,
        p_parent_drive_id,
        p_path,
        p_mime_type,
        p_title,
        p_checksum,
        p_modified_at,
        p_last_reviewed_at,
        p_core,
        p_audience,
        p_age_levels,
        p_geographies,
        p_governance_models,
        p_vouchers,
        p_created_by,
        p_maintained_by,
        p_raw_export_path
    )
    on conflict (drive_id) do update
        set parent_drive_id = excluded.parent_drive_id,
            path = excluded.path,
            mime_type = excluded.mime_type,
            title = excluded.title,
            checksum = excluded.checksum,
            modified_at = excluded.modified_at,
            last_reviewed_at = excluded.last_reviewed_at,
            core = excluded.core,
            audience = excluded.audience,
            age_levels = excluded.age_levels,
            geographies = excluded.geographies,
            governance_models = excluded.governance_models,
            vouchers = excluded.vouchers,
            created_by = excluded.created_by,
            maintained_by = excluded.maintained_by,
            raw_export_path = excluded.raw_export_path
        returning id into v_id;
    return v_id;
end;
$$;

create or replace function set_drive_start_page_token(p_token text)
returns void
language plpgsql
as $$
begin
    insert into drive_sync_state (id, start_page_token, last_synced_at)
    values (1, p_token, now())
    on conflict (id) do update
        set start_page_token = excluded.start_page_token,
            last_synced_at = excluded.last_synced_at;
end;
$$;

