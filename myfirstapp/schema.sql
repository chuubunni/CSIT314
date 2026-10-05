drop table if exists user; 
drop table if exists post; 
drop table if exists usercontent;
drop table if exists uploads;
drop table if exists images;
drop table if exists files;

create table user(
    id integer primary key autoincrement, 
    username text unique not null, 
    password text not null
);

create table post(
    id integer primary key autoincrement, 
    author_id integer not null, 
    created timestamp not null default current_timestamp, 
    title text not null, 
    body text not null, 
    foreign key (author_id) references user (id)
);

-- create table uploads(
--     id integer primary key autoincrement,
--     author_id integer not null,
--     picture 
-- )
create table images(
    id integer primary key autoincrement,
    imagelink text, caption text,
    author_id integer not null,
    created timestamp not null default current_timestamp,
    foreign key (author_id) references user (id));

create table files(
    id integer primary key autoincrement,
    filelink text not null,   -- random name stored in static/files
    filename text not null,   -- original name, shown to users
    author_id integer not null,
    created timestamp not null default current_timestamp,
    foreign key (author_id) references user (id)
);