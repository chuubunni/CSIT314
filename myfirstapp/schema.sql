-- Drop children before parents
drop table if exists idp_view;
drop table if exists favourite;
drop table if exists idp_media;
drop table if exists idp;
drop table if exists category;
drop table if exists designer;
drop table if exists user;

-- One table for everyone: this is what login/register/sessions use.
create table user(
    id integer primary key autoincrement,
    name text not null,
    password text not null,
    email text unique not null,
    phone text not null,                       -- text keeps leading zeros / +65
    Usertype text not null
        check (Usertype in ('designer', 'customer', 'platform')),
    created timestamp not null default current_timestamp
);

-- Only designers have extra attributes, so only they get a subtype table.
-- Its primary key IS the user id (1-to-1), so there is no separate designerID.
create table designer(
    userID integer primary key,
    companyName text not null,
    companyLine text unique not null,
    companyDescription text,
    foreign key (userID) references user (id) on delete cascade
);

create table category(
    id integer primary key autoincrement,
    name text unique not null,
    active integer not null default 1
);

-- One row per interior design project (IDP)
create table idp(
    id integer primary key autoincrement,
    designer_id integer not null,
    category_id integer,
    title text not null,
    description text,
    status text not null default 'completed'
        check (status in ('ongoing', 'completed')),
    created timestamp not null default current_timestamp,
    foreign key (designer_id) references designer (userID),
    foreign key (category_id) references category (id)
);

-- Many images/PDFs per IDP (replaces the images + files tables)
create table idp_media(
    id integer primary key autoincrement,
    idp_id integer not null,
    kind text not null check (kind in ('image', 'file')),
    link text not null,        -- random name on disk
    filename text,             -- original name (files)
    caption text,              -- (images)
    created timestamp not null default current_timestamp,
    foreign key (idp_id) references idp (id) on delete cascade
);

-- Customer's shortlist; the composite key stops duplicates
create table favourite(
    customer_id integer not null,
    idp_id integer not null,
    created timestamp not null default current_timestamp,
    primary key (customer_id, idp_id),
    foreign key (customer_id) references user (id) on delete cascade,
    foreign key (idp_id) references idp (id) on delete cascade
);

-- One row per view, with a timestamp: needed for view counts and daily/weekly/monthly reports
create table idp_view(
    id integer primary key autoincrement,
    idp_id integer not null,
    viewer_id integer,         -- null for logged-out visitors
    viewed_at timestamp not null default current_timestamp,
    foreign key (idp_id) references idp (id) on delete cascade,
    foreign key (viewer_id) references user (id) on delete set null
);