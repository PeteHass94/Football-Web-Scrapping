-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.cards (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fixture_id bigint,
  team_id integer,
  player_id integer,
  card_minute integer,
  match_minute integer,
  yellow boolean,
  yellow 2 boolean,
  red boolean,
  reason text,
  CONSTRAINT cards_pkey PRIMARY KEY (id),
  CONSTRAINT cards_fixture_id_fkey FOREIGN KEY (fixture_id) REFERENCES public.fixtures(fixture_id),
  CONSTRAINT cards_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id),
  CONSTRAINT cards_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id)
);
CREATE TABLE public.fixtures (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fixture_id bigint NOT NULL UNIQUE,
  home_team_id integer,
  away_team_id integer,
  season_id integer,
  round smallint,
  kickoff_date_time timestamp with time zone,
  total_time integer,
  injury_time_1 integer,
  injury_time_2 integer,
  home_score integer,
  away_score integer,
  result text,
  fixture_custom_id text,
  home_manager_id integer,
  away_manager_id integer,
  CONSTRAINT fixtures_pkey PRIMARY KEY (id),
  CONSTRAINT fixtures_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES public.teams(team_id),
  CONSTRAINT fixtures_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES public.teams(team_id),
  CONSTRAINT fixtures_season_id_fkey FOREIGN KEY (season_id) REFERENCES public.seasons(season_id)
);
CREATE TABLE public.game_states (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fixture_id bigint,
  half text,
  start_minute integer,
  end_minute integer,
  home_state text,
  away_state text,
  CONSTRAINT game_states_pkey PRIMARY KEY (id),
  CONSTRAINT game_states_fixture_id_fkey FOREIGN KEY (fixture_id) REFERENCES public.fixtures(fixture_id)
);
CREATE TABLE public.goals (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fixture_id bigint,
  team_id integer,
  player_id integer,
  goal_minute integer,
  added_time integer,
  match_minute integer,
  half text,
  type text,
  is_own_goal boolean DEFAULT false,
  CONSTRAINT goals_pkey PRIMARY KEY (id),
  CONSTRAINT goals_fixture_id_fkey FOREIGN KEY (fixture_id) REFERENCES public.fixtures(fixture_id),
  CONSTRAINT goals_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id),
  CONSTRAINT goals_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id)
);
CREATE TABLE public.managers (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  name text,
  short_name text,
  manager_id integer,
  slug text,
  team_id integer NOT NULL,
  CONSTRAINT managers_pkey PRIMARY KEY (id),
  CONSTRAINT managers_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id)
);
CREATE TABLE public.players (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  player_id integer NOT NULL UNIQUE,
  name text,
  short_name text,
  dateOfBirthTimestamp integer,
  team_id integer,
  sofascoreId text,
  CONSTRAINT players_pkey PRIMARY KEY (id)
);
CREATE TABLE public.players_fixtures (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  player_id integer,
  fixture_id bigint,
  team_id integer,
  started boolean,
  substitute boolean,
  substituted_on boolean,
  substituted_off boolean,
  minutes_played smallint,
  subbed_on_time smallint,
  subbed_off_time smallint,
  game_minutes_played smallint,
  CONSTRAINT players_fixtures_pkey PRIMARY KEY (id),
  CONSTRAINT players_fixtures_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id),
  CONSTRAINT players_fixtures_fixture_id_fkey FOREIGN KEY (fixture_id) REFERENCES public.fixtures(fixture_id),
  CONSTRAINT players_fixtures_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id)
);
CREATE TABLE public.seasons (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  season_id integer NOT NULL UNIQUE,
  name text,
  year text,
  tournament_id smallint,
  unique_tournament_id smallint,
  CONSTRAINT seasons_pkey PRIMARY KEY (id),
  CONSTRAINT seasons_tournament_id_fkey FOREIGN KEY (tournament_id) REFERENCES public.tournaments(tournament_id),
  CONSTRAINT seasons_unique_tournament_id_fkey FOREIGN KEY (unique_tournament_id) REFERENCES public.tournaments(unique_tournament_id)
);
CREATE TABLE public.shots (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fixture_id bigint NOT NULL,
  player_id integer,
  team_id integer,
  shot_type text,
  goal_type text,
  situation text,
  player_coordinates json,
  body_part text,
  goal_mouth_location text,
  goal_mouth_coordinates json,
  xg real,
  xgot real,
  shot_id bigint,
  minute smallint,
  added_time smallint,
  time_seconds integer,
  incident_type text,
  CONSTRAINT shots_pkey PRIMARY KEY (id),
  CONSTRAINT shots_fixture_id_fkey FOREIGN KEY (fixture_id) REFERENCES public.fixtures(fixture_id),
  CONSTRAINT shots_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id),
  CONSTRAINT shots_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id)
);
CREATE TABLE public.teams (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  team_id integer NOT NULL UNIQUE,
  name text,
  nameCode text,
  teamColours jsonb,
  crest text,
  CONSTRAINT teams_pkey PRIMARY KEY (id)
);
CREATE TABLE public.tournaments (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  name text,
  tournament_id smallint UNIQUE,
  unique_tournament_id smallint UNIQUE,
  CONSTRAINT tournaments_pkey PRIMARY KEY (id)
);

create table public.match_statistics (
  id bigint generated always as identity not null,
  created_at timestamp with time zone not null default now(),
  fixture_id bigint not null,
  period text not null,
  group_name text null,
  key text not null,
  name text null,
  value_type text null,
  home_value double precision null,
  away_value double precision null,
  home_raw text null,
  away_raw text null,
  constraint match_statistics_pkey primary key (id),
  constraint match_statistics_uniq unique (fixture_id, period, key),
  constraint match_statistics_fixture_fk foreign KEY (fixture_id) references fixtures (fixture_id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists match_statistics_fixture_idx on public.match_statistics using btree (fixture_id) TABLESPACE pg_default;

create index IF not exists match_statistics_key_idx on public.match_statistics using btree (key) TABLESPACE pg_default;

create table public.player_statistics (
  id bigint generated always as identity not null,
  created_at timestamp with time zone not null default now(),
  fixture_id bigint not null,
  player_id integer not null,
  team_id integer null,
  side text null,
  started boolean null,
  substitute boolean null,
  position text null,
  jersey_number text null,
  stats_json jsonb not null,
  constraint player_statistics_pkey primary key (id),
  constraint player_statistics_uniq unique (fixture_id, player_id),
  constraint player_statistics_fixture_fk foreign KEY (fixture_id) references fixtures (fixture_id) on delete CASCADE,
  constraint player_statistics_player_fk foreign KEY (player_id) references players (player_id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists player_statistics_fixture_idx on public.player_statistics using btree (fixture_id) TABLESPACE pg_default;

create index IF not exists player_statistics_player_idx on public.player_statistics using btree (player_id) TABLESPACE pg_default;

create index IF not exists player_statistics_json_gin on public.player_statistics using gin (stats_json) TABLESPACE pg_default;

create table public.substitutions (
  id bigint generated always as identity not null,
  created_at timestamp with time zone not null default now(),
  fixture_id bigint not null,
  team_id integer null,
  player_in_id integer null,
  player_out_id integer null,
  minute smallint null,
  added_time smallint null,
  match_minute integer null,
  half text null,
  injury boolean default false,
  incident_id bigint null,
  constraint substitutions_pkey primary key (id),
  constraint substitutions_fixture_fk foreign KEY (fixture_id) references fixtures (fixture_id) on delete CASCADE,
  constraint substitutions_player_in_fk foreign KEY (player_in_id) references players (player_id) on delete SET NULL,
  constraint substitutions_player_out_fk foreign KEY (player_out_id) references players (player_id) on delete SET NULL,
  constraint substitutions_team_fk foreign KEY (team_id) references teams (team_id) on delete SET NULL
) TABLESPACE pg_default;

create index IF not exists substitutions_fixture_idx on public.substitutions using btree (fixture_id) TABLESPACE pg_default;
create index IF not exists substitutions_player_in_idx on public.substitutions using btree (player_in_id) TABLESPACE pg_default;
create index IF not exists substitutions_player_out_idx on public.substitutions using btree (player_out_id) TABLESPACE pg_default;

create table public.incidents (
  id bigint generated always as identity not null,
  created_at timestamp with time zone not null default now(),
  fixture_id bigint not null,
  incident_type text not null,
  incident_id bigint null,
  team_id integer null,
  player_id integer null,
  minute smallint null,
  added_time smallint null,
  match_minute integer null,
  half text null,
  -- Fields specific to different incident types
  text text null,  -- For period: "HT", "FT", etc.
  home_score integer null,  -- For period
  away_score integer null,  -- For period
  is_live boolean null,  -- For period
  time_seconds integer null,  -- For period
  period_time_seconds integer null,  -- For period
  length smallint null,  -- For injuryTime
  confirmed boolean null,  -- For varDecision
  incident_class text null,  -- For varDecision, inGamePenalty
  reason text null,  -- For inGamePenalty
  description text null,  -- For inGamePenalty
  incident_data jsonb null,  -- Full JSON for reference
  constraint incidents_pkey primary key (id),
  constraint incidents_fixture_fk foreign KEY (fixture_id) references fixtures (fixture_id) on delete CASCADE,
  constraint incidents_player_fk foreign KEY (player_id) references players (player_id) on delete SET NULL,
  constraint incidents_team_fk foreign KEY (team_id) references teams (team_id) on delete SET NULL
) TABLESPACE pg_default;

create index IF not exists incidents_fixture_idx on public.incidents using btree (fixture_id) TABLESPACE pg_default;
create index IF not exists incidents_type_idx on public.incidents using btree (incident_type) TABLESPACE pg_default;
create index IF not exists incidents_incident_id_idx on public.incidents using btree (incident_id) TABLESPACE pg_default;