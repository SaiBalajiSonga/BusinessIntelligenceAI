-- DEMO POLICIES — apply only if you want the prototype writing to Supabase
-- with the publishable (anon) key.
--
-- Why this file exists, separately from schema.sql:
--
-- The policies in schema.sql are the ones a real deployment wants. They match
-- rows against a `persona` claim in the caller's JWT, so a category manager
-- reads their own feedback and nobody else's. That is correct, and it is also
-- why the prototype cannot write a single row: a publishable key carries no
-- JWT claims at all, so `auth.jwt() ->> 'persona'` is null, matches nothing,
-- and every insert is refused. Reads are worse than refused — they return
-- HTTP 200 with an empty array, so the connection looks healthy while the
-- table is invisible.
--
-- Applying this file relaxes that to "anyone with the anon key may read and
-- write". That is fine for a prototype on synthetic retail data and NOT fine
-- for anything real. The engine's own entitlement model is unaffected — that
-- runs in SQL before any analysis, and it is the gate the demo actually
-- demonstrates. This is the second gate, deliberately opened.
--
-- To close it again: drop these policies. schema.sql's originals remain in
-- place underneath and take over.
--
--   Supabase dashboard -> SQL Editor -> paste -> Run

drop policy if exists feedback_demo_all on feedback;
create policy feedback_demo_all on feedback
  for all using (true) with check (true);

drop policy if exists annotations_demo_all on annotations;
create policy annotations_demo_all on annotations
  for all using (true) with check (true);

drop policy if exists insight_audit_demo_all on insight_audit;
create policy insight_audit_demo_all on insight_audit
  for all using (true) with check (true);

drop policy if exists learned_demo_all on learned_params;
create policy learned_demo_all on learned_params
  for all using (true) with check (true);

-- A row this leaves behind on purpose: proof the table is writable, which the
-- engine's health check looks for instead of trusting an empty 200.
insert into learned_params (kind, key, value, n_observations)
values ('calibration', '__writable_probe__', '{"ok": true}'::jsonb, 0)
on conflict (kind, key) do update set updated_at = now();
