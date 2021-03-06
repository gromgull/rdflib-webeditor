RDFLib Web Editor
=================

A web-app for collaborativ editing of RDF files. 


REQUIREMENTS
------------
* python 2.7.x
* rdflib 3.2.3
* flask 0.9
* Flask-OpenID 1.0.1

SETUP DATABASE
--------------

```sh
cat database.sql changesets.sql ontologies.sql | sqlite3 db.db
mkdir ontologies
```

RUN
---

```sh
python vocab_server.py
```

TODO
----
 * "Source Code" view
 * Restore changes in a proposal to "uncommited" changes.
 * Show related proposals and history for each resource.
 * MAKE AJAX SEARCHING FASTER
  - The Objects search box is unbearable to use when large ontologies are in the system
  - Add in some search caching
 * Comment system
 * Fix up CSS for new/import ontology form
 * Fix up CSS so it looks the same in Chrome and Firefox
   (it's currently functional in chrome, but looks kinda funky)
 * Fix up \n display in ontology descriptions and comments
 * Actually support all the listed input formats for ontology importing
 * Sanity checking on create/import ontology forms
 * Deal with qnames that show us as "ns35:blah", etc.
 * "Deploying" ontologies

 * Search code for TODOs for more!

Quirks (that may become TODOs)
------------------------------

 * "Modifying" a value is not distingishable from an addition and removal, 
   and will show as such once the modifications are stored.

 * Changing the URI of a new resource that hasn't been stored in the rdf store
   creates a new resource and the old one has to be reverted manually.

DESIGN DESCISIONS
-----------------

### About the use of the sql database

The database is used to store details about ontologies in play as it removes any ambiguities about whether a specific "namespace" should be available to be modified. Also, named-graphs that don't have any triples associated with them don't get stored anywhere, so I couldn't find a way to add a "namespace" without adding any initial triples to it.

Since the sql database was already in play it just seemed easier to manage "uncommited" triples in sql as opposed to keeping track of extra named graphs for the various different states that the triples could be in and only write the triples to the rdf graph when the proposals were being "accepted".

PROPOSALS DATABASE SPECIFICS
----------------------------

There are 3 tables used for the proposals system

```sql
create table commits (
  id integer primary key autoincrement,
  user string not null,
  status string not null
);
```

This is a simple table to join the others together.

```sql
create table history (
  id integer primary key autoincrement,
  commitid integer not null,
  status string not null,  /* proposed, accepted, rejected */
  user string not null,
  date integer not null
);
```

This stores a history of status changes for the specific commit. Comments for each history item are stored in the comments table (see below)

```sql
create table changes (
  id integer primary key autoincrement,
  commitid integer not null,
  type string not null,
  subject string,
  predicate string,
  object string,
  context string
);
```

This stores the triples (quads acutally, since context is present) for the speicific commit, along with whether the
triple is an 'addition' or a 'removal' (type)

```sql
create table comments (
  id integer primary key autoincrement,
  user string not null,
  resource string not null, /* URI to resource or commit#id */
  date integer not null,
  comment string not null
);
```

Stores comments about various resources.
A special type of resource is the commit. Commit messages are linked to the history table by the resource column, having "commit#<id>" as it's value (where <id> is the commitid), and the date column being the same as the specific history item.

E.G.

```
history(1, 1, "proposed", "bob", "20121211T14:37"), comments(1, "bob", "commitid#1", "20121211T14:37", "a proposed commit")
history(2, 1, "accepted", "bob", "20121211T14:47"), comments(2, "bob", "commitid#1", "20121211T14:47", "accepted the proposal")
```

This may be a bit over complicated and it may have simply been enough to have the comment stores in the history table. I was somewhat preparing for the existance of a generic "comment" system, but it's highly likely this would have changed completely once I got to that point.