-- Crazy Mason cloud saves: a player name + 4-digit PIN is the account
create table if not exists public.saves (
  name_key text primary key,
  name text not null,
  pin_hash text not null,
  data jsonb not null default '{}'::jsonb,
  t bigint not null default 0,
  fails integer not null default 0,
  lock_until timestamptz,
  updated timestamptz not null default now()
);
alter table public.saves enable row level security;
revoke all on public.saves from anon, authenticated;

create or replace function public.save_key(p_name text) returns text language sql immutable as $$ select lower(btrim(coalesce(p_name, ''))) $$;
create or replace function public.save_hash(p_key text, p_pin text) returns text language sql immutable as $$ select encode(sha256(convert_to(p_key || ':crazy-mason:' || p_pin, 'UTF8')), 'hex') $$;

create or replace function public.cloud_exists(p_name text) returns boolean
language sql security definer set search_path = public as $$ select exists (select 1 from saves where name_key = save_key(p_name)) $$;

-- checks the PIN (8 wrong tries lock the name for 15 minutes); returns null when the PIN is right
create or replace function public.cloud_pin_err(r public.saves, p_pin text) returns text
language plpgsql security definer set search_path = public as $$
begin
  if r.lock_until is not null and r.lock_until > now() then return 'locked'; end if;
  if r.pin_hash <> save_hash(r.name_key, p_pin) then
    update saves set fails = fails + 1, lock_until = case when fails + 1 >= 8 then now() + interval '15 minutes' end where name_key = r.name_key;
    return 'wrong_pin';
  end if;
  if r.fails > 0 then update saves set fails = 0, lock_until = null where name_key = r.name_key; end if;
  return null;
end $$;

create or replace function public.cloud_load(p_name text, p_pin text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare r saves; e text;
begin
  if p_pin is null or p_pin !~ '^[0-9]{4}$' then return jsonb_build_object('err', 'bad_pin'); end if;
  select * into r from saves where name_key = save_key(p_name);
  if not found then return jsonb_build_object('err', 'none'); end if;
  e := cloud_pin_err(r, p_pin); if e is not null then return jsonb_build_object('err', e); end if;
  return jsonb_build_object('ok', true, 'data', r.data, 't', r.t, 'name', r.name);
end $$;

create or replace function public.cloud_save(p_name text, p_pin text, p_data jsonb, p_t bigint) returns jsonb
language plpgsql security definer set search_path = public as $$
declare r saves; e text; k text := save_key(p_name);
begin
  if p_pin is null or p_pin !~ '^[0-9]{4}$' then return jsonb_build_object('err', 'bad_pin'); end if;
  if char_length(k) < 1 or char_length(k) > 24 then return jsonb_build_object('err', 'bad_name'); end if;
  if p_data is null or length(p_data::text) > 30000 then return jsonb_build_object('err', 'too_big'); end if;
  select * into r from saves where name_key = k;
  if not found then
    insert into saves (name_key, name, pin_hash, data, t) values (k, left(btrim(p_name), 24), save_hash(k, p_pin), p_data, coalesce(p_t, 0));
    return jsonb_build_object('ok', true, 'created', true, 't', coalesce(p_t, 0));
  end if;
  e := cloud_pin_err(r, p_pin); if e is not null then return jsonb_build_object('err', e); end if;
  if coalesce(p_t, 0) < r.t then return jsonb_build_object('ok', false, 'err', 'newer', 'data', r.data, 't', r.t); end if;
  update saves set data = p_data, t = p_t, name = left(btrim(p_name), 24), updated = now() where name_key = k;
  return jsonb_build_object('ok', true, 't', p_t);
end $$;

revoke all on function public.save_key(text), public.save_hash(text, text), public.cloud_pin_err(public.saves, text) from public, anon, authenticated;
grant execute on function public.cloud_exists(text), public.cloud_load(text, text), public.cloud_save(text, text, jsonb, bigint) to anon, authenticated;
