-- Drop children before parents
drop table if exists idp_group_member;
drop table if exists idp_group;
drop table if exists idp_view;
drop table if exists favourite_designer;
drop table if exists favourite_idp;
drop table if exists favourite;          -- old name, kept so re-running init-db cleans it up
drop table if exists idp_media;
drop table if exists idp_category;
drop table if exists idp;
drop table if exists category;
drop table if exists customer;
drop table if exists designer;
drop table if exists company;
drop table if exists platform;
drop table if exists house_type;
drop table if exists user;

-- ---------------------------------------------------------------------------
-- Accounts
-- ---------------------------------------------------------------------------

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

create table platform(
    managerID integer primary key,
    foreign key (managerID) references user (id) on delete cascade
);

-- ---------------------------------------------------------------------------
-- Customers
-- ---------------------------------------------------------------------------
create table customer(
    cust_id integer primary key,
    current_house_type text not null,
    received_keys integer check (received_keys in (0, 1)),   
    foreign key (cust_id) references user (id) on delete cascade
);

-- ---------------------------------------------------------------------------
-- Companies and designers (many designers can belong to one company)
-- ---------------------------------------------------------------------------
create table company(
    companyID integer primary key autoincrement,
    companyName text not null,
    companyLine text unique not null,
    companyEmail text
);

-- Only designers have extra attributes, so only they get a subtype table.
-- Its primary key IS the user id (1-to-1).
create table designer(
    userID integer primary key,
    companyID integer not null,
    foreign key (userID) references user (id) on delete cascade,
    foreign key (companyID) references company (companyID)
);

-- ---------------------------------------------------------------------------
-- Categories (managed by platform managers)
-- ---------------------------------------------------------------------------
create table category(
    id integer primary key autoincrement,
    name text unique not null,
    active integer not null default 1
);

-- ---------------------------------------------------------------------------
-- Interior design projects
-- ---------------------------------------------------------------------------
create table idp(
    id integer primary key autoincrement,
    designer_id integer not null,
    title text not null,
    description text,
    houseType text not null,
    price integer not null check (price >= 0), -- whole dollars (SGD)
    status text not null default 'completed'
        check (status in ('ongoing', 'completed')),
    created timestamp not null default current_timestamp,
    foreign key (designer_id) references designer (userID)
);

-- An IDP can be in several categories
create table idp_category(
    idp_id integer not null,
    category_id integer not null,
    primary key (idp_id, category_id),
    foreign key (idp_id) references idp (id) on delete cascade,
    foreign key (category_id) references category (id)
);

-- Many images per IDP
create table idp_media(
    mediaID integer primary key autoincrement,
    idp_id integer not null,
    link text not null,        -- random name on disk
    caption text,
    created timestamp not null default current_timestamp,
    foreign key (idp_id) references idp (id) on delete cascade
);

-- A designer's own named groups of IDPs, used for bulk changes
-- (e.g. select group "Kitchens" -> change category/price for all of it).
-- The controller must check that every member IDP belongs to the group's designer.
create table idp_group(
    id integer primary key autoincrement,
    designer_id integer not null,
    name text not null,
    created timestamp not null default current_timestamp,
    unique (designer_id, name),
    foreign key (designer_id) references designer (userID) on delete cascade
);

create table idp_group_member(
    group_id integer not null,
    idp_id integer not null,
    primary key (group_id, idp_id),
    foreign key (group_id) references idp_group (id) on delete cascade,
    foreign key (idp_id) references idp (id) on delete cascade
);

-- ---------------------------------------------------------------------------
-- Customer shortlists
-- ---------------------------------------------------------------------------
create table favourite_idp(
    customer_id integer not null,
    idp_id integer not null,
    created timestamp not null default current_timestamp,
    primary key (customer_id, idp_id),         -- stops duplicates
    foreign key (customer_id) references customer (cust_id) on delete cascade,
    foreign key (idp_id) references idp (id) on delete cascade
);

create table favourite_designer(
    customer_id integer not null,
    designer_id integer not null,
    created timestamp not null default current_timestamp,
    primary key (customer_id, designer_id),
    foreign key (customer_id) references customer (cust_id) on delete cascade,
    foreign key (designer_id) references designer (userID) on delete cascade
);

-- ---------------------------------------------------------------------------
-- Tracking for designers' stats and the managers' daily/weekly/monthly reports
-- ---------------------------------------------------------------------------
-- One row per view, with a timestamp
create table idp_view(
    id integer primary key autoincrement,
    idp_id integer not null,
    viewer_id integer,         -- null for logged-out visitors
    viewed_at timestamp not null default current_timestamp,
    foreign key (idp_id) references idp (id) on delete cascade,
    foreign key (viewer_id) references user (id) on delete set null
);

-- ---------------------------------------------------------------------------
-- Indexes for the search / filter / report queries
-- ---------------------------------------------------------------------------
create index ix_user_type            on user (Usertype);
create index ix_user_created         on user (created);
create index ix_designer_company     on designer (companyID);
create index ix_idp_designer         on idp (designer_id);
create index ix_idp_price            on idp (price);
create index ix_idp_created          on idp (created);
create index ix_idp_category_cat     on idp_category (category_id);
create index ix_idp_media_idp        on idp_media (idp_id);
create index ix_idp_group_member_idp on idp_group_member (idp_id);
create index ix_fav_idp_idp          on favourite_idp (idp_id);
create index ix_fav_idp_created      on favourite_idp (created);
create index ix_fav_designer_des     on favourite_designer (designer_id);
create index ix_idp_view_idp         on idp_view (idp_id);
create index ix_idp_view_time        on idp_view (viewed_at);
