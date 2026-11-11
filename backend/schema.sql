-- Run in the Supabase SQL editor (the app also creates these tables itself on startup).
create table if not exists products (
  id serial primary key,
  url text unique not null,
  shop text not null,
  title text not null,
  category text not null,
  current_price double precision not null,
  analysis_json text,
  analyzed_at timestamp,
  created_at timestamp not null default now()
);
create table if not exists price_history (
  id serial primary key,
  product_id integer not null references products(id) on delete cascade,
  price double precision not null,
  scraped_at timestamp not null default now()
);
create index if not exists ix_price_history_product on price_history(product_id, scraped_at);
create table if not exists raw_reviews (
  id serial primary key,
  product_id integer not null references products(id) on delete cascade,
  review_text text not null,
  rating integer not null,
  scraped_at timestamp not null default now()
);
create index if not exists ix_raw_reviews_product on raw_reviews(product_id);
create table if not exists request_counts (
  client_id text not null,
  window text not null,
  count integer not null default 0,
  primary key (client_id, window)
);
create table if not exists watchlist (
  id serial primary key,
  product_id integer not null references products(id) on delete cascade,
  email text not null,
  target_price double precision not null,
  token text unique not null,
  created_at timestamp not null default now(),
  notified_at timestamp
);
create index if not exists ix_watchlist_product on watchlist(product_id);
create index if not exists ix_watchlist_email on watchlist(email);
create table if not exists system_logs (
  id serial primary key,
  level text not null,
  source text not null,
  message text not null,
  created_at timestamp not null default now()
);
create table if not exists scrape_requests (
  id serial primary key,
  url text unique not null,
  shop text not null,
  status text not null default 'pending',
  error text,
  requested_at timestamp not null default now(),
  finished_at timestamp
);
