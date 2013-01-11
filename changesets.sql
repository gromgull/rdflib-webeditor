drop table if exists commits;

create table commits (
  id integer primary key autoincrement,
  user string not null,
  status string not null /* unsaved, proposed, accepted, rejected */
);

drop table if exists history;

create table history (
  id integer primary key autoincrement,
  commitid integer not null,
  status string not null,  /* proposed, accepted, rejected */
  user string not null,
  date integer not null
);

drop table if exists changes;

create table changes (
  id integer primary key autoincrement,
  commitid integer not null,
  type string not null,
  subject string,
  predicate string,
  object string,
  context string
);

drop table if exists comments;

create table comments (
  id integer primary key autoincrement,
  user string not null,
  resource string not null, /* URI to resource or commit#id */
  date integer not null,
  comment string not null
);

/* NOTES:

* comment for status changes are identified by the comment date and user
  being the same as the history record's date and user

*/


/* TODO

howto "select history for subject"
 - join changes w/ 'accepted' commits and select changes.subject


*/
