-- Vamos al cine: accounts, saved choices, public reviews.
-- Paste the whole file into Supabase → SQL Editor → New query → Run. Safe to run again.

-- Public profile: the name shown next to comments, and the email-alert switch.
create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 40),
  email_alerts boolean not null default true,
  created_at timestamptz not null default now()
);

-- Everything a member saves: favourite cinemas, followed films, Letterboxd watchlist, discounts, preferences.
create table if not exists public.user_state (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  favs jsonb not null default '[]',
  track jsonb not null default '[]',
  wl jsonb not null default '[]',
  discounts jsonb not null default '[]',
  prefs jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

-- One review per member and film: stars (1-5) and/or a comment. Readable by everyone.
create table if not exists public.reviews (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  film_key text not null check (char_length(film_key) <= 80),
  film_title text not null check (char_length(film_title) <= 200),
  stars smallint check (stars between 1 and 5),
  comment text check (char_length(comment) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, film_key),
  check (stars is not null or char_length(trim(coalesce(comment, ''))) > 0)
);
create index if not exists reviews_film_key on public.reviews (film_key);

-- New sign-up → profile + empty saved state (display name chosen in the sign-up form).
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, left(coalesce(nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''), 'Cinéfilo'), 40))
  on conflict (id) do nothing;
  insert into public.user_state (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Row-level security: everyone reads names and reviews; members change only their own rows.
alter table public.profiles enable row level security;
alter table public.user_state enable row level security;
alter table public.reviews enable row level security;

drop policy if exists "names are public" on public.profiles;
create policy "names are public" on public.profiles for select using (true);
drop policy if exists "edit own profile" on public.profiles;
create policy "edit own profile" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "own saved state" on public.user_state;
create policy "own saved state" on public.user_state for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "reviews are public" on public.reviews;
create policy "reviews are public" on public.reviews for select using (true);
drop policy if exists "write own review" on public.reviews;
create policy "write own review" on public.reviews for insert with check (auth.uid() = user_id);
drop policy if exists "edit own review" on public.reviews;
create policy "edit own review" on public.reviews for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "delete own review" on public.reviews;
create policy "delete own review" on public.reviews for delete using (auth.uid() = user_id);

grant select on public.profiles, public.reviews to anon, authenticated;
grant update (display_name, email_alerts) on public.profiles to authenticated;
grant select, insert, update on public.user_state to authenticated;
grant insert, update, delete on public.reviews to authenticated;
