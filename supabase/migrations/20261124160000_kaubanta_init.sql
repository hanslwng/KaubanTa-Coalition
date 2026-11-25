-- KaubanTa Coalition
-- Run this whole file in the Supabase SQL Editor (or with `supabase db push`).
-- Safe to run again: it will not duplicate the sample activities or newsletters.

create extension if not exists pgcrypto;

create table if not exists public.activities (
  id bigint generated always as identity primary key,
  title text not null check (char_length(btrim(title)) between 2 and 160),
  starts_label text not null check (char_length(starts_label) between 2 and 80),
  venue text not null check (char_length(venue) between 2 and 160),
  cause text not null check (char_length(cause) between 2 and 40),
  slots integer not null default 0 check (slots >= 0 and slots <= 10000),
  details text not null check (char_length(details) between 2 and 1000),
  is_current boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.newsletters (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('weekly', 'monthly')),
  title text not null check (char_length(btrim(title)) between 2 and 180),
  date_label text not null check (char_length(date_label) between 2 and 80),
  summary text not null check (char_length(summary) between 2 and 400),
  featured text check (featured is null or char_length(featured) <= 400),
  body jsonb not null default '[]'::jsonb,
  cover text not null check (char_length(cover) between 2 and 40),
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.site_stats (
  id integer primary key default 1 check (id = 1),
  volunteers integer not null check (volunteers >= 0),
  events integer not null check (events >= 0),
  communities integer not null check (communities >= 0)
);

create table if not exists public.members (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (char_length(btrim(full_name)) between 2 and 120),
  email text not null check (
    email = lower(email)
    and email ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    and char_length(email) <= 160
  ),
  mobile text not null check (mobile ~ '^[0-9+() .\-]{7,20}$'),
  birthday date not null,
  school text check (school is null or char_length(school) <= 160),
  city text not null check (char_length(btrim(city)) between 2 and 120),
  interests text[] not null default '{}' check (
    interests <@ array['Education', 'Environment', 'Health', 'Disaster response', 'Advocacy', 'Relief']::text[]
  ),
  availability text[] not null default '{}' check (
    availability <@ array['Weekdays', 'Weekends']::text[]
  ),
  heard_from text not null check (
    heard_from in ('Friend or classmate', 'Social media', 'School event', 'Other')
  ),
  created_at timestamptz not null default now(),
  constraint members_email_key unique (email)
);

create table if not exists public.rsvps (
  id uuid primary key default gen_random_uuid(),
  activity_id bigint not null references public.activities (id),
  full_name text not null check (char_length(btrim(full_name)) between 2 and 120),
  email text not null check (
    email = lower(email)
    and email ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    and char_length(email) <= 160
  ),
  mobile text not null check (mobile ~ '^[0-9+() .\-]{7,20}$'),
  created_at timestamptz not null default now(),
  constraint rsvps_activity_email_key unique (activity_id, email)
);

create table if not exists public.subscribers (
  id uuid primary key default gen_random_uuid(),
  email text not null check (
    email = lower(email)
    and email ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    and char_length(email) <= 160
  ),
  created_at timestamptz not null default now(),
  constraint subscribers_email_key unique (email)
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (char_length(btrim(full_name)) between 2 and 120),
  email text not null check (
    email = lower(email)
    and email ~ '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    and char_length(email) <= 160
  ),
  subject text not null check (
    subject in ('General inquiry', 'Partnership', 'Volunteer', 'Media', 'Other')
  ),
  body text not null check (char_length(btrim(body)) between 2 and 4000),
  created_at timestamptz not null default now()
);

create index if not exists activities_current_idx on public.activities (is_current, sort_order);
create index if not exists newsletters_kind_idx on public.newsletters (kind, sort_order);
create index if not exists members_created_idx on public.members (created_at desc);
create index if not exists messages_created_idx on public.messages (created_at desc);

create or replace function public.reserve_activity_slot()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  reserved integer;
begin
  update public.activities
     set slots = slots - 1
   where id = new.activity_id
     and is_current
     and slots > 0;
  get diagnostics reserved = row_count;
  if reserved = 0 then
    raise exception 'This activity is full';
  end if;
  return new;
end;
$$;

drop trigger if exists rsvps_reserve_slot on public.rsvps;
create trigger rsvps_reserve_slot
  before insert on public.rsvps
  for each row execute function public.reserve_activity_slot();

revoke all on function public.reserve_activity_slot() from public, anon, authenticated;

alter table public.activities enable row level security;
alter table public.newsletters enable row level security;
alter table public.site_stats enable row level security;
alter table public.members enable row level security;
alter table public.rsvps enable row level security;
alter table public.subscribers enable row level security;
alter table public.messages enable row level security;

drop policy if exists "Anyone can read activities" on public.activities;
create policy "Anyone can read activities"
  on public.activities for select
  to anon, authenticated
  using (true);

drop policy if exists "Anyone can read newsletters" on public.newsletters;
create policy "Anyone can read newsletters"
  on public.newsletters for select
  to anon, authenticated
  using (true);

drop policy if exists "Anyone can read stats" on public.site_stats;
create policy "Anyone can read stats"
  on public.site_stats for select
  to anon, authenticated
  using (true);

drop policy if exists "Anyone can sign up" on public.members;
create policy "Anyone can sign up"
  on public.members for insert
  to anon, authenticated
  with check (true);

drop policy if exists "Anyone can rsvp" on public.rsvps;
create policy "Anyone can rsvp"
  on public.rsvps for insert
  to anon, authenticated
  with check (true);

drop policy if exists "Anyone can subscribe" on public.subscribers;
create policy "Anyone can subscribe"
  on public.subscribers for insert
  to anon, authenticated
  with check (true);

drop policy if exists "Anyone can send a message" on public.messages;
create policy "Anyone can send a message"
  on public.messages for insert
  to anon, authenticated
  with check (true);

grant usage on schema public to anon, authenticated, service_role;

revoke all on table public.activities from anon, authenticated;
revoke all on table public.newsletters from anon, authenticated;
revoke all on table public.site_stats from anon, authenticated;
revoke all on table public.members from anon, authenticated;
revoke all on table public.rsvps from anon, authenticated;
revoke all on table public.subscribers from anon, authenticated;
revoke all on table public.messages from anon, authenticated;

grant select on public.activities, public.newsletters, public.site_stats to anon, authenticated;
grant insert on public.members, public.rsvps, public.subscribers, public.messages to anon, authenticated;
grant all on public.activities, public.newsletters, public.site_stats, public.members, public.rsvps, public.subscribers, public.messages to service_role;

insert into public.site_stats (id, volunteers, events, communities)
values (1, 1200, 85, 30)
on conflict (id) do nothing;

insert into public.activities (title, starts_label, venue, cause, slots, details, is_current, sort_order)
select * from (values
  ('Lakeshore Clean-up'::text, 'Wed, Nov 4, 3:00 PM'::text, 'Los Baños Lakeshore'::text, 'Environment'::text, 14, 'Bring gloves and a refillable bottle. Bags and snacks are on us.'::text, true, 1),
  ('Reading Buddies', 'Thu, Nov 5, 4:00 PM', 'Barangay Library, Calamba', 'Education', 8, 'Read with grade school kids and help with homework.', true, 2),
  ('Community Pantry Packing', 'Sat, Nov 7, 8:00 AM', 'Santa Rosa Gym', 'Relief', 20, 'Sort and pack goods for 150 households.', true, 3),
  ('Youth Voter Info Booth', 'Sun, Nov 8, 10:00 AM', 'Plaza, San Pablo', 'Advocacy', 6, 'Help first-time voters check their registration.', true, 4),
  ('Tree planting, 600 seedlings', 'Completed', 'Laguna', 'Environment', 0, 'A weekend planting with partner schools.', false, 5),
  ('Disaster response training', 'Completed', 'Laguna', 'Disaster response', 0, 'Basic disaster response training for youth volunteers.', false, 6),
  ('Summer service camp', 'Completed', 'Laguna', 'Education', 0, 'A summer camp of community service projects.', false, 7),
  ('Orientation day', 'Completed', 'Laguna', 'Advocacy', 0, 'Welcome orientation for new coalition members.', false, 8)
) as seed(title, starts_label, venue, cause, slots, details, is_current, sort_order)
where not exists (select 1 from public.activities);

insert into public.newsletters (kind, title, date_label, summary, featured, body, cover, sort_order)
select * from (values
  (
    'weekly'::text,
    'Week 44: Lakeshore clean-up recap'::text,
    'Oct 26 to Nov 1, 2026'::text,
    '72 volunteers, 310 kilos of waste, and one very muddy Saturday.'::text,
    null::text,
    '["Our lakeshore clean-up gathered 72 volunteers from 9 schools. Together we collected 310 kilos of waste, most of it single-use plastic.","Next week we pack goods for the community pantry. Slots fill fast, so reserve yours on the Volunteer page."]'::jsonb,
    'Week 44',
    1
  ),
  (
    'weekly',
    'Week 43: Reading Buddies kicks off',
    'Oct 19 to Oct 25, 2026',
    'Our new tutoring program started with 25 kids and 12 volunteers.',
    null::text,
    '["Reading Buddies opened with a full room. Volunteers paired with kids for 30-minute sessions.","We need more volunteers on Thursdays. No teaching experience required."]'::jsonb,
    'Week 43',
    2
  ),
  (
    'weekly',
    'Week 42: Welcome new members',
    'Oct 12 to Oct 18, 2026',
    '38 new members joined the coalition through our orientation.',
    null::text,
    '["Thank you to everyone who attended Saturday’s orientation.","New members: check your email for your team assignment and group chat link."]'::jsonb,
    'Week 42',
    3
  ),
  (
    'monthly',
    'October 2026 Highlights',
    'Published Oct 30',
    'Four events, 210 volunteers, and our first partner school network.',
    'Featured story: five schools joined together to clean the lakeshore.',
    '["Recap: we held 4 events this month, reaching 6 communities.","Volunteer spotlight: Mika, a Grade 11 student, logged 40 service hours.","Next month: pantry drive, voter info booth, and a leadership workshop."]'::jsonb,
    'October',
    1
  ),
  (
    'monthly',
    'September 2026 Highlights',
    'Published Sep 30',
    'Tree planting season and a new chapter in Laguna.',
    'Featured story: 600 seedlings planted in one weekend.',
    '["Recap: three events and 150 volunteers.","Volunteer spotlight: the Calamba student council team.","Next month: Reading Buddies launches."]'::jsonb,
    'September',
    2
  ),
  (
    'monthly',
    'August 2026 Highlights',
    'Published Aug 31',
    'Disaster response training and our summer service camp.',
    'Featured story: 40 youth trained in basic disaster response.',
    '["Recap: two trainings and one service camp.","Volunteer spotlight: our first-aid team.","Next month: tree planting season."]'::jsonb,
    'August',
    3
  )
) as seed(kind, title, date_label, summary, featured, body, cover, sort_order)
where not exists (select 1 from public.newsletters);

notify pgrst, 'reload schema';
