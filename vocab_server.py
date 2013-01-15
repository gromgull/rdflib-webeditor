import rdflib
import json
import time
from jinja2.utils import Markup
from rdflib.namespace import SKOS, RDF, Namespace, RDFS, XSD
import rdfextras, sys, os, re, urllib2
from flask import g
import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session
import flask
from flaskext.openid import OpenID
from utils import connect_db, list_ontologies, get_uncommited_quads, query_db, get_label, parse_string_rdfobject, get_qname, rdfobject2dict, get_proposals, get_changes, get_prefix_from_uri, rdfstring2dict, accept_changeset, reject_changeset, get_proposal, revert_changes, propose_changeset, store_triples, commit_db, qname2uri, store_subject_diff, get_user, create_user
from config import data, ONTOLOGY_DIR
import atexit

# NAMESPACES
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
CS = Namespace("http://purl.org/vocab/changeset/schema#")

# For debugging when the server wont start
# A common reason for this is something to do with the rdf db locking up
#import pdb; pdb.set_trace()

# APPLICATION SETUP
maingraph = rdflib.ConjunctiveGraph('Sleepycat',id)
if maingraph.open(data, create=False) == -1:
    maingraph.open(data, create=True)
    maingraph.load("http://www.w3.org/TR/rdf-schema/rdfs-namespace")
    maingraph.load("http://www.w3.org/2009/08/skos-reference/skos.rdf", publicID=u'http://www.w3.org/2004/02/skos/core#')
    maingraph.load("http://www.w3.org/1999/02/22-rdf-syntax-ns")
    maingraph.load("http://vocab.org/changeset/schema.rdf")
    maingraph.namespace_manager.bind('skos', SKOS)
    maingraph.namespace_manager.bind('rdfs', RDFS)
    maingraph.namespace_manager.bind('rdf', RDF)
    maingraph.namespace_manager.bind('xsd', XSD)

# Store graphs globally to avoid having to re-open them on every request
# which is a very slow process
# TODO: using a global for this is a bit scary however, as it may not 
# be very scalable. It should, however, be no less scalable than loading the
# graph from disk every request
GRAPHS = {'':maingraph}
def get_graph(prefix):
    if prefix in GRAPHS:
        return GRAPHS[prefix]
    graph = dict(maingraph.namespace_manager.namespaces()).get(prefix, None)
    print graph.__class__
    if graph is None:
        return None
    graph = maingraph.get_context(graph)
    GRAPHS[prefix] = graph
    return graph

# app
application = Flask(__name__)
application.config.update(
    DEBUG = True,
    SECRET_KEY = 'correct horse battery staple',
    USERNAME = 'admin',
    PASSWORD = 'default'
)
application.jinja_env.globals["rdflib_version"]=rdflib.__version__
application.jinja_env.globals["rdfextras_version"]=rdfextras.__version__
application.jinja_env.globals["python_version"]="%d.%d.%d"%(sys.version_info[0], sys.version_info[1], sys.version_info[2])

# jinja filter for date formatting
def datetimeformat(value, format='%d.%m.%Y %H:%M'):
    if type(value) == int:
        return time.strftime(format, time.localtime(value))
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f").strftime(format)
application.jinja_env.filters['datetimeformat'] = datetimeformat

# jinja filter for turning a dict into a json map
def jsonify(value):
    return Markup(json.dumps(value))
application.jinja_env.filters['jsonify'] = jsonify

# OPEN ID
oid = OpenID(application)

# decorator for functions that require login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in', False) is False:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# wrapping render_template to add kwargs that are used by all templates
def render_template(template, **kwargs):
    if session.get('logged_in', False):
        changes = len(get_uncommited_quads(g.userid))
    else:
        changes = 0
    return flask.render_template(template, no_of_uncommited_changes=changes, **kwargs)

# Do shutdown things here
# I attempted to .close() the rdf graph to avoid problems with it getting
# locked up after a lot of quick server restarts, but it didn't seem to help.
def shutdown():
    print "shutting down"
    #maingraph.close()

atexit.register(shutdown)

# REQUEST HANDLING
@application.before_request
def before_request():
    g.graph = maingraph
    g.db = connect_db()
    if session.get('logged_in', False):
        u = session.get('user')
        if u is not None:
            g.userid = u.get('openid')

@application.teardown_request
def teardown_request(response):
    g.db.close()
    return response

@application.route("/")
def index():
    ontologies=list_ontologies()
    print ontologies
    return render_template('index.html', ontologies=ontologies)

# The main ontology view
# responsible for listing the subjects under an ontology (/<ontology_>/)
# and for viewing specific subjects (/<ontology_>/?resource_=<resource_>)
# underscores are used at the end of variables to distinguish them from the function names
@application.route('/<ontology_>', methods=['GET'])
def ontology(ontology_):
    ont = query_db('select * from ontologies where prefix = ?', [ontology_], one=True)
    # get the graph for the relevant ontology
    graph = get_graph(ontology_)
    if graph is None:
        # TODO: 404
        return redirect(url_for('index'))
    resource_ = request.args.get('resource_', None)
    errors = []
    # for recreating a page if there are errors
    changes = {'addition':[], 'removal':[]}

    # if ?resource_=xxx is present and xxx is not None then go into "resource viewing mode"
    if resource_ is not None:
        properties = {}
        # get the label of the resource
        res_name = get_label(resource_)

        # force the resource to a URIRef
        uri2res = lambda uri: uri if isinstance(uri, rdflib.URIRef) else rdflib.URIRef(uri)
        r = uri2res(resource_)

        # build list of (type,predicate,object)s, using an empty string for the type of original triples
        tpos = [('', p, o) for p, o in graph.predicate_objects(subject=r)]
        # include additions/removals from uncommited proposal
        if session.get('logged_in', False):
            tpos.extend([(s['type'], uri2res(s['predicate']), parse_string_rdfobject(s['object'])) for s in get_uncommited_quads(g.userid, resource_)])

        # TODO: these 2 lines may be redundant now as most form validation is done in the UI, remove them  completely when this is confirmed
        # include additions from changes (only present if errors in form submission)
        tpos.extend([('addition', uri2res(stmt['pred']), parse_string_rdfobject(stmt['val'])) for stmt in changes['addition']])
        # include removals from changes (only present if errors in form submission)
        tpos.extend([('removal', uri2res(stmt['pred']), parse_string_rdfobject(stmt['val'])) for stmt in changes['removal']])
        # TODO: add "modified" type (maybe)
        for t,p,o in tpos:
            # get existing values for this predicate
            item = properties.get(p,
                                  {'value': [],
                                   'qname': get_qname(p), 
                                   'label': get_label(p)})
            # convert rdf object to a dict
            v = rdfobject2dict(o)
            # add 'deleted' or 'added' 'class' value (used by templates)
            if t == 'removal':
                try:
                    # if it's a removal, it should already exist in the values list
                    # find it and add the class to the existing entry
                    idx = item['value'].index(v)
                    v['class'] = 'deleted'
                    item['value'][idx] = v
                except ValueError:
                    pass # caused when .index fails
            else:
                if t == 'addition':
                    v['class'] = 'added'
                item['value'].append(v)

            # update the changes
            properties[p] = item

            # TODO: this may be redundant with the get_label call above
            # simply sets the resource name variable to the value of the RDFS.label predicate
            if res_name is '' and p == RDFS.label:
                res_name = v['value']

        # if there were no predicates, consider this a "new resource" and present the "create resource" view
        # with the URI already filled in
        # TODO: a lot of this is duplicate code from the create_resource function
        is_new = False
        if len(properties) == 0:
            # create new resource
            properties = {}
            properties[RDF.type] = {'value': [{'type':"URI", 'value':"", 'class':'added'}],
                                    'qname': 'rdf:type',
                                    'label': 'type'}
            properties[RDFS.label] = {'value': [{'type':"Literal", 'value':"", 'class':'added'}],
                                      'qname': 'rdfs:label', 
                                      'label': 'label'}
            res_name='Create New Resource'
            is_new=True

        # TODO: proposal/history stuff
        proposals = []
        history = []
        return render_template('resource.html',
                               ontology_=ont,
                               uri=resource_,
                               name=res_name,
                               properties_=properties,
                               proposals=proposals,
                               history=history,
                               is_new=is_new,
                               auto_save=False)

    # if no resource is requested, go to the ontology view, retrieving a list of all the subjects in the ontology
    resources = [{'uri':s[0], 'qname':get_qname(s[0]), 'label':get_label(s[0])} for s in graph.triples((None, RDF.type, None))]
    proposals = None #[s for s,_ in groupby(pgraph.subjects()) if isinstance(s, rdflib.URIRef)] # TODO and not s.startswith(changeset_base_uri)
    return render_template('ontology.html', ontology_=ont, resources=resources, proposals=proposals)

# route used to create a new resource
# NOTE this is also used to store changes to resources
@application.route('/<ontology_>/_new', methods=['GET', 'POST'])
@login_required
def create_resource(ontology_):
    ont = query_db('select * from ontologies where prefix = ?', [ontology_], one=True)
    # if this is a post, call the "autosave" function and redirect to the resource uri
    if request.method == 'POST':
        uri = request.form.get('uri')
        autosave()
        return redirect(url_for('ontology', ontology_=ontology_, resource_=uri))
    properties = {}
    properties[RDF.type] = {'value': [{'type':"URI", 'value':"", 'class':'added'}],
                            'qname': 'rdf:type', 
                            'label': 'type'}
    properties[RDFS.label] = {'value': [{'type':"Literal", 'value':"", 'class':'added'}],
                              'qname': 'rdfs:label', 
                              'label': 'label'}
    return render_template('resource.html', ontology_=ont, 
                           properties_=properties,
                           uri=ont['context'],
                           name='Create New Resource',
                           is_new=True,
                           auto_save=False)

# route responsible for importing an ontology into the system from a url
@application.route('/_import', methods=['GET', 'POST'])
@login_required
def import_ontology():
    errors = []
    url = ''
    format = ''
    pubid = ''
    prefix = ''
    name = ''
    description = ''
    if request.method == 'POST':
        url = request.form.get('url', '')
        if url == '':
            errors.append("Missing prefix")
        else:
            url_ = re.match("^http(s)?://([^:]+):([^@]+)@([^/]+)/(.*)$", url)
            if url_ is not None:
                # setup auth for this url
                url_ = url_.groups()
                username = url_[1]
                password = url_[2]
                url_ = "http%s://%s/%s" % (url_[0] or "", url_[3], url_[4])
                passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
                passman.add_password(None, url_, username, password)
                authhandler = urllib2.HTTPBasicAuthHandler(passman)
                opener = urllib2.build_opener(authhandler)
                urllib2.install_opener(opener)
            else:
                url_ = url
        # get the format parameter, this value will be passed to the graph.load function
        format = request.form.get('format', 'RDF-XML')
        if format == 'RDF-XML':
            format = 'xml'
        # this is the 'context' uri (uses the ontology url by default)
        pubid = request.form.get('pubid', '')
        if '' == pubid:
            pubid = url
        # the prefix: to use for this ontology
        prefix = request.form.get('prefix', '')
        if prefix == '':
            errors.append("Missing prefix")
        if len(errors) == 0:
            # get the "verbose name" for this ontology (using the prefix if none is given)
            name = request.form.get('name', prefix)
            description = request.form.get('description', '')
            try:
                # TODO: this can take a while in the case of large ontologies
                # look into doing this asychroniously
                # TODO: figure out a "safe" way to do a load (i.e. if the db operation fails, we should rollback)
                maingraph.load(url_, publicID=pubid, format=format)
                maingraph.namespace_manager.bind(prefix, Namespace(pubid))
                # register the imported ontology into the ontologies database
                g.db.execute('insert into ontologies (prefix, context, name, description, source) values (?, ?, ?, ?, ?)',
                             [prefix, pubid, name, description, url])
                g.db.commit()
                # redirect to the new ontology
                return redirect(url_for('ontology', ontology_=prefix))
            except Exception, e:
                errors.append(str(e))
    return render_template('import_ontology.html', url=url, importing=True, description=description, name=name, format=format, pubid=pubid, prefix=prefix, errors=errors)

# the same as the import except creates an empty ontology
@application.route('/_new', methods=['GET', 'POST'])
@login_required
def create_ontology():
    errors = []
    pubid = ''
    prefix = ''
    name = ''
    description = ''
    if request.method == 'POST':
        pubid = request.form.get('pubid', '')
        if '' == pubid:
            errors.append("Missing Base URI")
        prefix = request.form.get('prefix', '')
        if prefix == '':
            errors.append("Missing prefix")
        if len(errors) == 0:
            name = request.form.get('name', prefix)
            description = request.form.get('description', '')
            try:
                maingraph.namespace_manager.bind(prefix, Namespace(pubid))
                g.db.execute('insert into ontologies (prefix, context, name, description, source) values (?, ?, ?, ?, ?)',
                             [prefix, pubid, name, description, None])
                g.db.commit()
                return redirect(url_for('ontology', ontology_=prefix))
            except Exception, e:
                errors.append(str(e))
    return render_template('import_ontology.html', url=None, format=None, description=description, name=name, pubid=pubid, prefix=prefix, errors=errors)

@application.route('/_proposals/', methods=['GET', 'POST'])
@login_required
def proposals():
    proposals_ = get_proposals()
    for p in proposals_:
        c = get_changes(p['id'])
        adds = 0
        rems = 0;
        subs = []
        for x in c:
            if x['type'] == 'addition':
                adds += 1
            else:
                rems += 1
            s = {'subject': x['subject'], 'ontology': get_prefix_from_uri(x['context'])}
            if s not in subs:
                subs.append(s)
        p['additions'] = adds
        p['removals'] = rems
        p['subjects'] = subs
    return render_template('proposals.html', proposals=proposals_)

# TODO: this is a "view" util
def prepare_nquads_for_template(nquads):
    changes = {}
    for q in nquads:
        ctx = changes.get(q['context'], {'prefix': get_prefix_from_uri(q['context'])})
        sub = ctx.get(q['subject'], {'qname': get_qname(q['subject']), 
                                     'label': get_label(q['subject'])})
        pred = sub.get(q['predicate'], {'qname': get_qname(q['predicate']), 
                                        'label': get_label(q['predicate']),
                                        'values': []})
        vals = pred.get('values')
        v = rdfstring2dict(q['object'])
        v['class'] = q['type']
        v['id'] = q['id']
        vals.append(v)
        sub[q['predicate']] = pred
        ctx[q['subject']] = sub
        changes[q['context']] = ctx
    return changes

@application.route('/_proposal/<proposal_>', methods=['GET', 'POST'])
@login_required
def proposal(proposal_):
    if request.method == 'POST':
        if 'accept' in request.form:
            accept_changeset(g.userid, proposal_)
        elif 'reject' in request.form:
            comment = request.form.get('comment')
            reject_changeset(g.userid, proposal_, comment)
    prop = get_proposal(proposal_)
    nquads = prop.pop('changes', None)
    return render_template('proposal.html', id=proposal_, proposal=prop, changes=prepare_nquads_for_template(nquads))

@application.route('/_review', methods=['GET', 'POST'])
@login_required
def review():
    nquads = get_uncommited_quads(g.userid)
    print nquads
    if request.method == 'POST' and len(nquads) > 0:
        # set status of proposed quads to "proposed"
        revert = request.form.get('unchecked', 'revert') == 'revert'
        checked = []
        unchecked = []
        additions = []
        removals = []
        commitid = nquads[0]['commitid']
        message = request.form.get('comment')
        print request.form
        for q in nquads:
            if q['subject'] in request.form and str(q['id']) in request.form:
                checked.append(q['id'])
            else:
                unchecked.append(q['id'])
                if not revert:
                    if q['type'] == 'addition':
                        additions.append([q['subject'], q['predicate'], q['object'], q['context']])
                    else:
                        removals.append([q['subject'], q['predicate'], q['object'], q['context']])
        if 'revert' in request.form:
            if revert:
                revert_changes(checked)
            else:
                revert_changes(unchecked)
            nquads = get_uncommited_quads(g.userid)
        else: # if 'submit' in request.form
            # revert unchecked changes
            revert_changes(unchecked, commit=False)
            # propose remaining changes
            propose_changeset(g.userid, message=message, commit=False)
            # if "keep" unchecked was selected, re-apply unchecked
            if not revert:
                store_triples(g.userid, additions, removals, commit=False)
            commit_db()
            return redirect(url_for('proposal', proposal_=commitid))
    # <context> / <subj> / predicates: [pred + obj]
    return render_template('review_changes.html', changes=prepare_nquads_for_template(nquads))

@application.route("/_help")
def help():
    return render_template('help.html')

### COMMON REGEX ###

uri_re = """^<[^>]+>$""";
literal_re = """^"[^"]*"(?:\^\^[^\s]+|@[^\s]+|)$""";
num_re = """^[+-]?[0-9]+(?:(?:\.?[0-9]+(?:(?:(?:E|e)?[+-]?[0-9]+)|)|))$""";
quad_re = """^<([^>]+)>\s+<([^>]+)>\s+("[^"]*"(?:\^\^[^\s]+|@[^\s]+|)|<[^>]+>|[+-]?[0-9]+(?:(?:\.?[0-9]+(?:(?:(?:E|e)?[+-]?[0-9]+)|)|)))(?:\s+<([^>]+)>|)$""";


### AJAX Calls ###

# saves a "diff" from the resource.html template to the "uncommited changes" database
@application.route("/ajax/save", methods=['POST'])
def autosave():
    diff = request.form.get('diff', '')
    uri = request.form.get('uri', '')
    try:
        print diff
        diff = json.loads(diff)
        nquads = {'removal': [], 'addition': []}
        for type in ['deleted', 'added']:
            for stmt in diff[type]:
                # sanity check on predicate
                pred = stmt[1]
                pred = qname2uri(pred)

                # sanity check on object
                obj = stmt[2]
                if obj.startswith('"'):
                    # if the object is a literal with a datatype, make sure the datatype
                    # is stored as a URI and not a qname
                    m = re.match("^\"([^\"]+)\"\^\^(.+)$", obj)
                    if m:
                        obj = '"' + m.group(1) + '"^^' + qname2uri(m.group(2))
                elif re.match(num_re, obj):
                    # if the object is a number, store it as a Literal w/ the datatype
                    dt = "xsd:" + ("double" if "." in obj else "integer")
                    obj = '"' + obj + '"^^' + qname2uri(dt)
                elif re.match(uri_re, obj):
                    # force qnames to URIs
                    obj = '<' + qname2uri(obj[1:-1]) + '>'
                else:
                    # TODO: figure out when this is a case and if we need to do anything about it
                    # perhaps strings without surrounding ""
                    # but this cause should probably be handled by the editor
                    pass
                nquads['removal' if type is 'deleted' else 'addition'].append([stmt[0], pred, obj, stmt[3]])
        store_subject_diff(g.userid, uri, nquads['addition'], nquads['removal'])
    except ValueError, e:
        raise e
    return "OK"

@application.route("/ajax/search")
def search():
    t = request.args.get('type', 'all')
    s = request.args.get('term', '').lower()
    c = request.args.get('custom', '') == 'true';
    #l = request.args.get('label', '%(uri)s')

    if (s == ''):
        return "{}"

    ontologies=['']
    ontologies.extend(os.listdir(ONTOLOGY_DIR))
    results = []
    if t == 'all' or t == 'subjects':
        for subj in maingraph.subjects():
            subj = str(subj)
            try:
                subjlabel = str(get_label(subj))
            except:
                subjlabel = subj
            try:
                subjqname =  str(get_qname(subj))
            except:
                subjqname =  subj
            if s in subj.lower() or s in subjlabel.lower() or s in subjqname.lower():
                item = {'uri':subj, 'qname': subjqname, 'label': subjlabel}
                if item not in results:
                    results.append(item)
    if t == 'predicates':
        for pred,_,_ in maingraph.triples((None, RDF.type, RDF.Property)):
            pred = str(pred)
            try:
                predlabel = str(get_label(pred))
            except:
                predlabel = pred
            try:
                predqname =  str(get_qname(pred))
            except:
                predqname =  pred
            if s in pred.lower() or s in predlabel.lower() or s in predqname.lower():
                item = {'uri':pred, 'qname': predqname, 'label': predlabel}
                if item not in results:
                    results.append(item)
    if c:
        results.append({'uri':s})
    return json.dumps(results)

# TODO: i might remove this and leave it up to the LOD version
@application.route("/sparql", methods=['GET', 'POST'])
def query():
    pass

@application.route("/login", methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if session.get('logged_in', False) is not False:
        return redirect(oid.get_next_url())
    if request.method == 'POST':
        openid = request.form.get('ooid')
        # use the "other" openid provider before using the selected one
        print request.form, openid
        if openid is None or openid == '':
            openid = request.form.get('provider')
        if openid:
            return oid.try_login(openid, ask_for=['email', 'fullname',
                                                  'nickname'])
    return render_template('login.html', next=oid.get_next_url(),
                           error=oid.fetch_error())

@application.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('userid', None)
    session.pop('openid', None)
    return redirect(url_for('index'))

@oid.after_login
def create_or_login(resp):
    print resp
    session['openid'] = resp.identity_url
    user = get_user(session['openid'])
    if user is None:
        user = create_user(resp.identity_url,
                           resp.fullname or resp.nickname,
                           resp.email)
    session['user'] = user
    session['logged_in'] = True
    return redirect(oid.get_next_url())

# MAIN
if __name__ == '__main__':
    application.run(host='0.0.0.0')
