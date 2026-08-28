-- Supabase / Postgres migration.
--
-- Supabase is NOT the warehouse — DuckDB stays the analytical store, because
-- every query the engine runs is a group-by over hundreds of thousands of rows
-- and Postgres over a network would be strictly worse at it. What lives here is
-- the state that must outlive a session and be shared between people: what the
-- engine said, what an analyst thought of it, and what it learned as a result.
--
--   psql "$SUPABASE_DB_URL" -f feedback/schema.sql
--   -- or paste into the Supabase SQL editor
--
-- The engine runs fine without any of this; the local DuckDB store is the
-- default and the demo never depends on the network.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- audit --
-- Every insight served, with the evidence behind it. This is the audit trail
-- the brief asks for: a decision can be reconstructed months later, including
-- what the model was shown and whether its output passed the numeric guard.

create table if not exists insight_audit (
  id                uuid primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),

  kpi               text not null,
  iso_week          text not null,
  persona           text not null,
  scope             jsonb,                    -- the row filter actually applied

  gap               numeric,
  coverage          numeric,
  confidence_score  numeric,
  confidence_band   text check (confidence_band in ('confident','qualified','abstain')),
  causes            jsonb,                    -- the full evidence object

  narrative         text,
  narrative_source  text,                     -- llm | llm (retry) | template | abstention
  llm_called        boolean not null default false,
  figures_checked   integer default 0,
  guard_passed      boolean,
  drafts_rejected   integer default 0,

  model             text,
  input_tokens      integer,
  output_tokens     integer,
  cost_usd          numeric,
  latency_ms        numeric
);

create index if not exists insight_audit_week_idx on insight_audit (kpi, iso_week);
create index if not exists insight_audit_created_idx on insight_audit (created_at desc);

-- ------------------------------------------------------------- feedback --
-- Structured, not free text. A thumbs-down teaches nothing; "the driver was
-- wrong and it was actually X" updates a prior.

create table if not exists feedback (
  id                uuid primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),
  audit_id          uuid references insight_audit(id) on delete set null,

  kpi               text not null,
  iso_week          text not null,
  persona           text not null,

  verdict           text not null check (verdict in (
                      'correct',        -- the explanation held up
                      'wrong_driver',   -- right movement, wrong cause
                      'known_cause',    -- real, but we already knew why
                      'not_material',   -- true, and not worth flagging to me
                      'unclear'         -- could not tell
                    )),
  driver            text,               -- the driver the engine credited
  correct_driver    text,               -- what it should have credited
  confidence_shown  numeric,            -- what the engine claimed at the time
  impact_shown      numeric,            -- and what it said the movement was worth
  comment           text,
  author            text
);

create index if not exists feedback_kpi_idx on feedback (kpi, verdict);

-- ---------------------------------------------------------- annotations --
-- Known events. A planned campaign is not an anomaly, and an engine that
-- re-flags it every week teaches people to ignore it.

create table if not exists annotations (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),

  kpi           text,                   -- null = applies to any KPI
  dimension     text,                   -- region | category | sku | null
  value         text,
  starts_on     date not null,
  ends_on       date,
  label         text not null,
  cause         text,
  expected      boolean not null default true,   -- planned, so not a surprise
  author        text
);

create index if not exists annotations_window_idx on annotations (starts_on, ends_on);

-- -------------------------------------------------------- learned state --
-- What the loop has actually learned, kept as data so it can be inspected,
-- overridden and rolled back rather than hiding inside a pickle.

create table if not exists learned_params (
  id             uuid primary key default gen_random_uuid(),
  updated_at     timestamptz not null default now(),
  kind           text not null check (kind in ('driver_prior','materiality','calibration')),
  key            text not null,
  value          jsonb not null,
  n_observations integer not null default 0,
  unique (kind, key)
);

-- ------------------------------------------------------- row-level security --
-- Entitlements are enforced in the analytics layer before any maths runs; this
-- is the second gate, so a leaked publishable key cannot read another region's
-- feedback. `persona` on the row is matched against the caller's JWT claim.

alter table insight_audit  enable row level security;
alter table feedback       enable row level security;
alter table annotations    enable row level security;
alter table learned_params enable row level security;

drop policy if exists insight_audit_read on insight_audit;
create policy insight_audit_read on insight_audit
  for select using (
    coalesce(auth.jwt() ->> 'persona', '') = persona
    or coalesce(auth.jwt() ->> 'role', '') in ('analyst', 'service_role')
  );

drop policy if exists feedback_read on feedback;
create policy feedback_read on feedback
  for select using (
    coalesce(auth.jwt() ->> 'persona', '') = persona
    or coalesce(auth.jwt() ->> 'role', '') in ('analyst', 'service_role')
  );

drop policy if exists feedback_write on feedback;
create policy feedback_write on feedback
  for insert with check (coalesce(auth.jwt() ->> 'persona', '') = persona);

-- annotations and learned parameters are shared context: everyone reads,
-- only an analyst writes
drop policy if exists annotations_read on annotations;
create policy annotations_read on annotations for select using (true);

drop policy if exists annotations_write on annotations;
create policy annotations_write on annotations
  for insert with check (coalesce(auth.jwt() ->> 'role', '') in ('analyst','service_role'));

drop policy if exists learned_read on learned_params;
create policy learned_read on learned_params for select using (true);
