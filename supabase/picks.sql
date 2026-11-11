-- Vamos al cine: Irene's picks. Films the site owner recommends, with a one-line note.
-- Run AFTER moderation.sql (it uses public.is_admin()).
-- Paste into Supabase → SQL Editor → New query → Run. Safe to run again.

-- film_key identifies the film across days and sources: "tt…" (IMDb id) when known, else "ec:<eCartelera page>",
-- else "fa:<Filmaffinity id>". The other columns let the page match the pick again if the key changes
-- (e.g. a film picked while upcoming, before it had an IMDb id).
create table if not exists public.picks (
  film_key   text primary key check (char_length(film_key) between 1 and 200),
  film_title text not null check (char_length(film_title) between 1 and 300),
  film_orig  text,
  film_year  int,
  imdb       text,
  ec         text,
  note       text check (note is null or char_length(note) <= 300),
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.picks enable row level security;

-- everyone (signed in or not) can read the picks; only the admin can add, edit or remove them
drop policy if exists "picks are public" on public.picks;
create policy "picks are public" on public.picks for select using (true);
drop policy if exists "admin adds picks" on public.picks;
create policy "admin adds picks" on public.picks for insert with check (public.is_admin());
drop policy if exists "admin edits picks" on public.picks;
create policy "admin edits picks" on public.picks for update using (public.is_admin()) with check (public.is_admin());
drop policy if exists "admin removes picks" on public.picks;
create policy "admin removes picks" on public.picks for delete using (public.is_admin());

grant select on public.picks to anon, authenticated;
grant insert, update, delete on public.picks to authenticated;
