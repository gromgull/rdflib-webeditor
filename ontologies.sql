drop table if exists ontologies;

create table ontologies (
  id integer primary key autoincrement,
  context string not null,
  prefix string not null,
  name string not null,
  description string,
  source string
);
