-- Crazy Mason public leaderboard + coin gifts
create table if not exists public.board (
  id uuid primary key,
  name text not null check (char_length(name) between 1 and 24),
  best integer not null default 0 check (best >= 0),
  stage integer not null default 1,
  dist integer not null default 0,
  t timestamptz not null default now()
);
create index if not exists board_best_idx on public.board (best desc);
create table if not exists public.player_keys (id uuid primary key, secret text not null);
create table if not exists public.gifts (
  id text primary key,
  name text not null,
  coins integer not null check (coins > 0),
  note text,
  created timestamptz not null default now()
);
create table if not exists public.gift_claims (
  gift_id text not null references public.gifts(id) on delete cascade,
  pid uuid not null,
  primary key (gift_id, pid)
);

alter table public.board enable row level security;
alter table public.player_keys enable row level security;
alter table public.gifts enable row level security;
alter table public.gift_claims enable row level security;
revoke all on public.board, public.player_keys, public.gifts, public.gift_claims from anon, authenticated;
grant select on public.board, public.gifts to anon, authenticated;
drop policy if exists "board readable" on public.board;
create policy "board readable" on public.board for select to anon, authenticated using (true);
drop policy if exists "gifts readable" on public.gifts;
create policy "gifts readable" on public.gifts for select to anon, authenticated using (true);

-- a player proves who they are with the random secret their device made the first time
create or replace function public.check_player(p_id uuid, p_secret text) returns void
language plpgsql security definer set search_path = public as $$
declare k text;
begin
  if p_secret is null or char_length(p_secret) < 32 then raise exception 'bad secret'; end if;
  select secret into k from player_keys where id = p_id;
  if k is null then insert into player_keys (id, secret) values (p_id, p_secret);
  elsif k <> p_secret then raise exception 'not your record';
  end if;
end $$;

create or replace function public.submit_score(p_id uuid, p_secret text, p_name text, p_best integer, p_stage integer, p_dist integer)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform check_player(p_id, p_secret);
  p_name := left(btrim(coalesce(p_name, '')), 24);
  if p_name = '' then p_name := 'Player'; end if;
  if p_best < 0 or p_best > 50000000 then raise exception 'bad score'; end if;
  insert into board (id, name, best, stage, dist) values (p_id, p_name, p_best, greatest(p_stage, 1), greatest(p_dist, 0))
  on conflict (id) do update set
    name = excluded.name, t = now(),
    stage = case when excluded.best > board.best then excluded.stage else board.stage end,
    dist  = case when excluded.best > board.best then excluded.dist  else board.dist  end,
    best  = greatest(board.best, excluded.best);
end $$;

create or replace function public.my_claims(p_id uuid, p_secret text) returns setof text
language plpgsql security definer set search_path = public as $$
begin
  perform check_player(p_id, p_secret);
  return query select gift_id from gift_claims where pid = p_id;
end $$;

create or replace function public.claim_gifts(p_id uuid, p_secret text, p_ids text[]) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform check_player(p_id, p_secret);
  insert into gift_claims (gift_id, pid) select g.id, p_id from gifts g where g.id = any(p_ids) on conflict do nothing;
end $$;

revoke all on function public.check_player(uuid, text) from public, anon, authenticated;
grant execute on function public.submit_score(uuid, text, text, integer, integer, integer) to anon, authenticated;
grant execute on function public.my_claims(uuid, text) to anon, authenticated;
grant execute on function public.claim_gifts(uuid, text, text[]) to anon, authenticated;

-- carry over the two unclaimed gifts for 戴俊龙
insert into public.gifts (id, name, coins, note) values
  ('g-20261026-daijunlong', '戴俊龙', 30000, 'Gift from the Workshop'),
  ('g-20261026-daijunlong-2', '戴俊龙', 30000, 'Gift from the Workshop')
on conflict (id) do nothing;
