drop table if exists user; 
drop table if exists post; 
drop table if exists images;
drop table if exists files;
drop table if exists designer;
drop table if exists adminUsers;

create table user(
    id integer primary key autoincrement, 
    name text not null, 
    password text not null,
    email text unique not null,
    phone integer not null,
    Usertype text not null
);

create table designer(
    designerID integer primary key autoincrement, 
    companyName text not null,
    companyLine integer unique not null,
    userID integer not null,
    foreign key (userID) references user (id)
);

create table adminUsers(
    adminID integer primary key autoincrement,
    userID integer not null,
    foreign key (userID) references user (id)
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