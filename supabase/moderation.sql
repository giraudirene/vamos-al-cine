-- Vamos al cine: replies and moderation. The site owner can delete any comment or reply and block members.
-- Run AFTER schema.sql, and after the owner has created an account on the site.
-- Paste into Supabase → SQL Editor → New query → Run. Safe to run again.

alter table public.profiles add column if not exists is_admin boolean not null default false;
alter table public.profiles add column if not exists blocked boolean not null default false;
-- Members may only change their own name and alert switch (granted in schema.sql), never these two columns.

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and is_admin);
$$;

create or replace function public.is_blocked(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select blocked from public.profiles where id = uid), false);
$$;

-- Reviews of blocked members are hidden (the admin still sees them); blocked members cannot write;
-- everyone can delete their own review and the admin can delete any.
drop policy if exists "reviews are public" on public.reviews;
create policy "reviews are public" on public.reviews for select
  using (not public.is_blocked(user_id) or public.is_admin());
drop policy if exists "write own review" on public.reviews;
create policy "write own review" on public.reviews for insert
  with check (auth.uid() = user_id and not public.is_blocked(auth.uid()));
drop policy if exists "edit own review" on public.reviews;
create policy "edit own review" on public.reviews for update
  using (auth.uid() = user_id) with check (auth.uid() = user_id and not public.is_blocked(auth.uid()));
drop policy if exists "delete own review" on public.reviews;
drop policy if exists "delete own review or moderate" on public.reviews;
create policy "delete own review or moderate" on public.reviews for delete
  using (auth.uid() = user_id or public.is_admin());

-- Blocking goes through this function, which checks that the caller is the admin.
create or replace function public.set_blocked(target uuid, value boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then raise exception 'only the site admin can block members'; end if;
  if target = auth.uid() then raise exception 'you cannot block yourself'; end if;
  update public.profiles set blocked = value where id = target;
end $$;

revoke all on function public.set_blocked(uuid, boolean) from public, anon;
grant execute on function public.set_blocked(uuid, boolean) to authenticated;
grant execute on function public.is_admin() to anon, authenticated;
grant execute on function public.is_blocked(uuid) to anon, authenticated;

-- Replies to a review. Same rules: public to read, members write their own, blocked members are hidden,
-- everyone deletes their own, the admin deletes any. Deleting a review deletes its replies.
create table if not exists public.replies (
  id bigint generated always as identity primary key,
  review_id bigint not null references public.reviews (id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  body text not null check (char_length(trim(body)) between 1 and 1000),
  created_at timestamptz not null default now()
);
create index if not exists replies_review on public.replies (review_id);
alter table public.replies enable row level security;
drop policy if exists "replies are public" on public.replies;
create policy "replies are public" on public.replies for select
  using (not public.is_blocked(user_id) or public.is_admin());
drop policy if exists "write own reply" on public.replies;
create policy "write own reply" on public.replies for insert
  with check (auth.uid() = user_id and not public.is_blocked(auth.uid()));
drop policy if exists "delete own reply or moderate" on public.replies;
create policy "delete own reply or moderate" on public.replies for delete
  using (auth.uid() = user_id or public.is_admin());
grant select on public.replies to anon, authenticated;
grant insert, delete on public.replies to authenticated;

-- The site owner is the admin (the account must already exist).
update public.profiles set is_admin = true
where id = (select id from auth.users where email = 'giraudirene@gmail.com');

-- Check: this should list one row, the owner, with is_admin = true.
select p.display_name, u.email, p.is_admin from public.profiles p join auth.users u on u.id = p.id where p.is_admin;
