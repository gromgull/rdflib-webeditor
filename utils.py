import rdflib
from flask import g
import sqlite3
import datetime
import re
import time
import itertools
from config import DATABASE, BASE_URL

# DATABASE UTILS

def connect_db():
    return sqlite3.connect(DATABASE)

def query_db(query, args=(), one=False):
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

def commit_db():
    g.db.commit()

# USER UTILS

def get_user(openid):
    return query_db('select * from users where openid = ?', [openid], one=True)


def create_user(openid, name, email):
    g.db.execute('insert into users (name, email, openid) values (?, ?, ?)',
                 [name, email, openid])
    g.db.commit()
    return get_user(openid)

# CHANGESET UTILS

# Each user has an "uncommited changeset". This is represented by the last ID associated with the user that has
# status = "unsaved". if no ID exists for the user with "unsaved" status, this function will create one
def get_uncommited_changeset_id(userid):
    # NOTE: we have status = unsaved for this as well
    commitid = query_db('select id from commits where user = ? and status = ?', [userid, 'unsaved'], one=True)
    if commitid is None:
        g.db.execute('insert into commits (user, status) values (?, ?)', [userid, 'unsaved'])
        g.db.commit()
        return get_uncommited_changeset_id(userid)
    return commitid['id']

# returns all the changes associated with the specific commit id
def get_changes(commitid):
    return query_db('select * from changes where commitid = ?', [commitid])

# get all the "uncommited" changes for the specified user
# TODO: _quads is a bit misleading as it returns a dict, not a tuple/list
def get_uncommited_quads(userid, subject=None):
    commitid = get_uncommited_changeset_id(userid)
    if subject:
        return query_db('select * from changes where commitid = ? and subject = ?', [commitid, subject])
    else:
        return query_db('select * from changes where commitid = ?', [commitid])

# return all the proposals in the system
def get_proposals():
    props = query_db('select * from commits where status != ?', ['unsaved'])
    for p in props:
        c = query_db('select * from comments where user = ? and resource = ?', [p['user'], 'commit#%s' % p['id']], one=True)
        if c is not None:
            p['date'] = c['date']
            p['comment'] = c['comment']
        p['user'] = get_user(p['user'])
    return props

# get a specific proposal
def get_proposal(id):
    rval = query_db('select * from commits where id = ?', [id], one=True)
    if rval is not None:
        # add history
        rval['history'] = query_db('select * from history where commitid = ?', [id])
        # add comments for each history item
        for h in rval['history']:
            h['user'] = get_user(h['user'])
            c = query_db('select comment from comments where date = ? and resource = ?', [h['date'], 'commit#%s' % id], one=True)
            if c is not None:
                h['comment'] = c['comment']
        # add changes
        rval['changes'] = get_changes(id)
    return rval

"""
adds/removes triples to/from the changes database.

variables:
additions/removals: list of nquads [s,p,o,c]

Triples already in the changes database are considered to be part of the whole ontology. This means that un-referenced triples will be unchanged, but if a triple which is already marked as "removed" is present in the "additions" list, it will be removed from the database and vice versa. If the triple isn't in the database at all it will be added as is.

"""
def store_triples(userid, additions, removals, commit=True):
    commitid = get_uncommited_changeset_id(userid)
    ins = lambda t,q: g.db.execute('insert into changes (commitid, type, subject, predicate, object, context) values (?, ?, ?, ?, ?, ?)', [commitid, t, q[0], q[1], q[2], q[3]])
    delete = lambda t,q: g.db.execute('delete from changes where commitid = ? and type = ? and subject = ? and predicate = ? and object = ? and context = ?', [commitid, t, q[0], q[1], q[2], q[3]])
    check = lambda t,q: query_db('select * from changes where commitid = ? and type = ? and subject = ? and predicate = ? and object = ? and context = ?', [commitid, t, q[0], q[1], q[2], q[3]], one=True)
    for a in additions:
        # check if this quad is a "removed" quad (i.e. it's being reverted to the original
        if check('removal', a):
            delete('removal', a)
        # also check if this quad is already in the changes
        elif not check('addition', a):
            ins('addition', a)
    for r in removals:
        if check('addition', r):
            delete('addition', r)
        elif not check('removal', r):
            ins('removal', r)
    if commit:
        g.db.commit()

"""
Assumes the whole "diff" for the subject "uri" is present and will remove triples
that are not present in either the additions or removals lists.

Any triples that don't have a subject the same as the uri will be ignored
"""
def store_subject_diff(userid, uri, additions, removals, commit=True):
    commitid = get_uncommited_changeset_id(userid)
    old = [[x['type'], x['subject'], x['predicate'], x['object'], x['context']] for x in query_db('select * from changes where commitid = ? and subject = ?', [commitid, uri])]
    # handle additions
    for a in additions:
        # don't add again if the addition already exists
        if ['addition', a[0], a[1], a[2], a[3]] in old:
            old.remove(['addition', a[0], a[1], a[2], a[3]])
        elif a[0] == uri:
            g.db.execute('insert into changes (commitid, type, subject, predicate, object, context) values (?, ?, ?, ?, ?, ?)', [commitid, 'addition', a[0], a[1], a[2], a[3]])
    # handle removals
    for a in removals:
        if ['removal', a[0], a[1], a[2], a[3]] in old:
            old.remove(['removal', a[0], a[1], a[2], a[3]])
        elif a[0] == uri:
            g.db.execute('insert into changes (commitid, type, subject, predicate, object, context) values (?, ?, ?, ?, ?, ?)', [commitid, 'removal', a[0], a[1], a[2], a[3]])
    # handle remaining "old" triples
    for o in old:
        g.db.execute('delete from changes where commitid = ? and type = ? and subject = ? and predicate = ? and object = ? and context = ?', [commitid, o[0], o[1], o[2], o[3], o[4]])
    # commit if needed
    if commit:
        g.db.commit()

# takes a commit ID and sets it's status to "proposed". if no commit ID is specified it will use the user's
# uncommited changeset id.
def propose_changeset(userid, commitid=None, message=None, commit=True):
    if commitid is None:
        commitid = get_uncommited_changeset_id(userid)
    timestamp = time.mktime(datetime.datetime.utcnow().timetuple())
    g.db.execute('update commits set status = ? where id = ?', 
                 ['proposed', commitid])
    g.db.execute('insert into history (commitid, status, user, date) values (?, ?, ?, ?)',
                 [commitid, 'proposed', userid, timestamp])
    if message:
        g.db.execute('insert into comments (user, resource, date, comment) values (?, ?, ?, ?)',
                 [userid, 'commit#%s' % commitid, timestamp, message])
    if commit:
        g.db.commit()

def revert_changes(changeids, commit=True):
    g.db.executemany('delete from changes where id = ?',
                     [(c,) for c in changeids])
    if commit:
        g.db.commit()

def accept_changeset(userid, commitid, message=None, commit=True):
    triples = query_db('select * from changes where commitid = ?', [commitid])
    for t in triples:
        if 'context' in t:
            graph = g.graph.get_context(rdflib.URIRef(t['context']))
        else:
            graph = g.graph
        o = parse_string_rdfobject(t['object'])
        if isinstance(o, rdflib.resource.Resource):
            # graph.add need a URIRef as apposed to a Resource
            print '============== STILL GETTING Resource HERE ==============='
            o = o.identifier
        tup = (rdflib.URIRef(t['subject']), rdflib.URIRef(t['predicate']), o)
        print tup
        if t['type'] == 'addition':
            graph.add(tup)
        elif t['type'] == 'removal':
            graph.remove(tup)
    timestamp = time.mktime(datetime.datetime.utcnow().timetuple())
    g.db.execute('update commits set status = ? where id = ?', 
                 ['accepted', commitid])
    g.db.execute('insert into history (commitid, status, user, date) values (?, ?, ?, ?)',
                 [commitid, 'accepted', userid, timestamp])
    if message:
        g.db.execute('insert into comments (user, resource, date, comment) values (?, ?, ?, ?)',
                 [userid, 'commit#%s' % commitid, timestamp, message])
    if commit:
        g.db.commit()

def reject_changeset(userid, commitid, message, commit=True):
    timestamp = time.mktime(datetime.datetime.utcnow().timetuple())
    g.db.execute('update commits set status = ? where id = ?', 
                 ['rejected', commitid])
    g.db.execute('insert into history (commitid, status, user, date) values (?, ?, ?, ?)',
                 [commitid, 'rejected', userid, timestamp])
    g.db.execute('insert into comments (user, resource, date, comment) values (?, ?, ?, ?)',
                 [userid, 'commit#%s' % commitid, timestamp, message])
    if commit:
        g.db.commit()

# RDF UTILS

def get_qname(uri):
    rval = ''
    try:
        if isinstance(uri, basestring):
            uri = rdflib.URIRef(uri)
        rval = g.graph.qname(uri)
        #if isinstance(uri, rdflib.resource.Resource):
        #    rval = str(uri.qname())
    except:
        pass # ignore errors
    return rval

def get_label(uri):
    rval = ''
    try:
        if isinstance(uri, basestring):
            uri = rdflib.URIRef(uri)
        rval = g.graph.label(uri)
    except:
        pass # ignore errors
    return rval

# used to force a qname to a URI (if the prefix exists in the graph)
def qname2uri(qn):
    # check if this is already a uri
    if re.match("https?://.+", qn):
        return qn
    m = re.match("^([a-zA-Z0-9]+):(.+)$", qn)
    if m:
        prefix = m.group(1)
        suffix = m.group(2)
        try:
            ctx = itertools.dropwhile(lambda x: x[0] != prefix, g.graph.namespaces()).next()[1]
            return ctx + suffix
        except Exception, e: # happens if prefix is not found
            pass
    return qn

# MISC UTILS

# generate a unique URI for a changeset
def generate_changeset_uri(graph):
    last_changeset_id = 0
    while (rdflib.URIRef(changeset_base_uri + str(last_changeset_id)), RDF.type, CS.ChangeSet) in graph:
        last_changeset_id += 1
    return rdflib.URIRef(changeset_base_uri + str(last_changeset_id))

def list_ontologies():
    return query_db('select * from ontologies')

def get_prefix_from_uri(uri):
    ont = query_db('select prefix from ontologies where context = ?', [uri], one=True)
    if ont:
        return ont['prefix']
    return None

# TODO: check if there is something that already exists to do this!
def parse_string_rdfobject(o):
    if not isinstance(o, basestring):
        return rdflib.Literal(o)
    if o.startswith("<") and o.endswith(">"):
        return rdflib.URIRef(qname2uri(o[1:-1]))
    elif o.startswith('"'):
        e = o[1:].find('"') + 1
        if o[e+1:].startswith('@'):
            return rdflib.Literal(o[1:e], lang=o[e+2:])
        elif o[e+1:].startswith('^^'):
            datatype=rdflib.URIRef(qname2uri(o[e+3:]))
            return rdflib.Literal(o[1:e], datatype=datatype)
        else:
            return rdflib.Literal(o[1:e])
    else:
        # TODO: we shouldn't have this, perhaps error if we get here instead
        return rdflib.Literal(o)

def rdfobject_to_string(o):
    if isinstance(o, rdflib.URIRef):
        return "<" + qname2uri(str(o)) + ">"
    if isinstance(o, rdflib.Literal):
        val = '"' + str(o) + '"'
        if o.language:
            val += "@" + o.language
        elif o.datatype:
            val += "^^" + qname2uri(str(o.datatype))
        return val
    return str(o)

def rdfobject2dict(o):
    v = {'value': o}
    if isinstance(o, rdflib.term.URIRef):
        v = {'value': str(o), 'type': 'URI', 'qname': get_qname(o), 'label':get_label(o)}
    elif isinstance(o, rdflib.term.Literal):
        v = {'value': str(o), 'type': 'Literal'}
        if o.language:
            v['language'] = o.language
        elif o.datatype:
            v['datatype'] = get_qname(o.datatype) or o.datatype
    elif isinstance(o, rdflib.resource.Resource):
        print "========== WARNING: rdfobject2dict GOT rdflib.resource.Resource =============="
    return v

def rdfstring2dict(o):
    o = parse_string_rdfobject(o)
    return rdfobject2dict(o)
