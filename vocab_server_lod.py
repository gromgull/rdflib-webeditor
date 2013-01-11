import rdflib
from rdflib.namespace import SKOS, RDF, Namespace
from rdfextras.utils.pathutils import guess_format

import rdfextras_web.lod

from flaskext.openid import OpenID

id=rdflib.URIRef("urn:concepts")
data="data"

# NAMESPACES
PROPOSALS = Namespace("http://data.igreen-services.com/proposals/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

# APPLICATION SETUP
graph = rdflib.ConjunctiveGraph('Sleepycat',id)
if graph.open(data, create=False) == -1:
    graph.open(data, create=True)
    graph.load("proposal_schema.n3", format=guess_format("proposal_schema.n3"))
    graph.namespace_manager.bind('skos', SKOS)
    graph.namespace_manager.bind('proposals', PROPOSALS)

application=rdfextras_web.lod.get(graph)
graph.close()
del application.config["graph"]
application.debug=True

oid = OpenID(application)

from flask import g
from functools import wraps
from flask import g, request, redirect, url_for, session, render_template


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_user(openid):
    pass

def create_user(openid, name, email):
    print openid, name, email
    pass

# REQUEST HANDLING
@application.before_request
def before_request():
    g.user = None
    g.graph=rdflib.ConjunctiveGraph('Sleepycat',id)
    g.graph.open(data)
    if 'openid' in session:
        g.user = get_user(session['openid'])


@application.teardown_request
def teardown_request(response):
    if hasattr(g,'graph'): 
        g.graph.close()
    return response

@application.route("/editor")
def editor():
    return "<html><body><h1>YAY</h1></body></html>"

@application.route("/login", methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if g.user is not None:
        return redirect(oid.get_next_url())
    return render_template('login.html', next=oid.get_next_url(),
                           error=oid.fetch_error())
@oid.after_login
def create_or_login(resp):
    session['openid'] = resp.identity_url
    user = get_user(session['openid'])
    if user is not None:
        flash(u'Successfully signed in')
        g.user = user
        return redirect(oid.get_next_url())
    user = create_user(resp.identity_url,
                       resp.fullname or resp.nickname,
                       resp.email)
    return redirect(oid.get_next_url())

# MAIN
if __name__ == '__main__':
    application.run(host='0.0.0.0')
