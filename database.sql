drop table if exists users;

create table users (
  id integer primary key autoincrement,
  email string,
  name string,
  openid string not null
);
