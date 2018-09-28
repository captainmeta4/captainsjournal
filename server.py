import praw
from flask import *
import os
import time
from classes import *
from flaskext.markdown import Markdown

### NAMING CONVENTIONS ###
# s - Story object
# v - viewer (the person browsing) - User object
# u - target user - User object
# q - Temporary reddit object
# l - Listing object for homepages

#globals
app=Flask(__name__)
Markdown(app)
user_agent="Captain's Journal by /u/captainmeta4"
r=praw.Reddit(client_id=os.environ.get('client_id'),
              client_secret=os.environ.get('client_secret'),
              redirect_uri="http://www.captainslogbook.org/oauth/redirect",
              user_agent=user_agent)

#take care of static pages
@app.route('/assets/<path:path>')
def static_service(path):
    return send_from_directory('assets', path)

#take care of error pages
@app.errorhandler(401)
def error_401(e):
    return render_template('401.html'), 401

@app.errorhandler(403)
def error_403(e):
    return render_template('403.html'), 403

@app.errorhandler(404)
def error_404(e):
    return render_template('404.html'), 404

def temporary_reddit(refresh_token):

    '''
    Generates a temporary reddit client
    '''
    
    q=praw.Reddit(client_id=os.environ.get('client_id'),
              client_secret=os.environ.get('client_secret'),
              refresh_token=refresh_token,
              user_agent=user_agent)
    return q

def check_token():

    token=request.cookies.get("logbook_reddit")
    if token==None:
        raise KeyError('not found')
    else:
        return temporary_reddit(token)

def auth_required(f):
    '''
    wrapper for returning 401 if user not logged in
    '''

    def wrapper(*args, **kwargs):

        try:
            q=check_token()
            name=q.user.me().name
        except:
            return abort(401)

        return f(*args, q=q, v=User(name=name), **kwargs)

    wrapper.__name__=f.__name__
    return wrapper

def auth_desired(f): #but not necessary
    '''
    wrapper for passing logged in user to function
    passes None if not logged in
    '''

    def wrapper(*args, **kwargs):

        try:
            q=check_token()
            name=q.user.me().name
        except:
            return f(*args, v=None, **kwargs)

        return f(*args, v=User(name=name, make=True), **kwargs)

    wrapper.__name__=f.__name__
    return wrapper

def agree_required(f):
    '''
    wrapper for ensuring user has agreed to rules
    wrap inside auth_required
    '''

    def wrapper(q, v, *args, **kwargs):

        if not v.agreed:
            try:
                agreed=request.form.get('agreed', False)
            except:
                abort(400)
                
            if agreed:
                v.tos_agree()
                
        if v.agreed:
            return f(q, v, *args, **kwargs)
        else:
            abort(403)       

    wrapper.__name__=f.__name__
    return wrapper

def not_banned(f):
    '''
    wrapper for ensuring user is not banned
    wrap inside auth_required
    '''

    def wrapper(q, v, *args, **kwargs):

        if v.banned:
            abort(403)
            
        return f(q, v, *args, **kwargs)
    
    wrapper.__name__=f.__name__
    return wrapper

def admin_required(f):
    '''
    wrapper that aborts 403 if user is not admin
    use for admin api calls
    '''

    def wrapper(q, v, *args, **kwargs):

        if not v.admin:
            abort(403)

        return f(*args, q=q, v=v, **kwargs)

    wrapper.__name__=f.__name__
    return wrapper

@app.route('/submit')
@auth_required
def create_submission(q, v):
    return render_template('submit.html', v=v)

@app.route("/makebook")
@auth_required
@not_banned
def create_book(q, v):
    return render_template('submitbook.html',v=v)

@app.route('/')
@auth_desired
def home(v):
    l=Listing(kind='new')
    return render_template('home.html', v=v, l=l)

@app.route('/rules')
@auth_desired
def rules(v):
    return render_template('rules.html',v=v)

@app.route("/oauth/redirect")
def oauth_redirect():
    '''
    Handle incoming redirects from reddit oauth flow
    '''

    #get redditor name
    code = request.args.get('code')
    token=r.auth.authorize(code)

    q=temporary_reddit(token)

    name=q.user.me().name

    #create user if it doesn't yet exist
    v=User(name=name, make=True)

    resp=make_response(redirect('/'))
    resp.set_cookie("logbook_reddit", value=token, domain=".captainslogbook.org")

    return resp

@app.route("/me")
@auth_required
def me_page(v):
    return redirect('/u/{}'.format(v.name))
            
@app.route("/u/<name>")
@auth_desired
def userpage(name, v=None):
    
    try:
        u=User(name=name)
    except KeyError:
        abort(404)

    #redirection for case insensitivity purposes
    if not name == u.name:
        return redirect(u.url)

    return u.render_userpage(v=v)

@app.route("/s/<sid>")
@auth_desired
def storypage(sid, v=None):

    try:
        s=Story(sid, load_author=True)
    except KeyError:
        abort(404)

    return s.render_storypage(v=v)

@app.route("/b/<bid>")
@auth_desired
def bookpage(bid, v=None):

    try:
        b=Book(bid, load_author=True)
    except KeyError:
        abort(404)

    return b.render_bookpage(v=v)

@app.route("/edit/<sid>")
@auth_required
@not_banned
def edit_story(q, v, sid):
    try:
        s=Story(sid=sid)
    except KeyError:
        abort(404)

    if not v.id == s.author_id:
        abort(403)

    return render_template('edit.html', s=s, v=v)

@app.route("/editbook/<bid>")
@auth_required
@not_banned
def edit_book(q, v, bid):
    try:
        b=Book(bid=bid)
    except KeyError:
        abort(404)

    if not v.id == b.author_id:
        abort(403)

    return render_template('editbook.html', b=b, v=v)
    
#API hits
@app.route('/api/submit', methods=["POST"])
@auth_required
@not_banned
@agree_required
def create_story(q, v):

    if v.banned:
        abort(403)
    
    title_md=request.form.get('title',"")
    pre_md=request.form.get('pre',"")
    story_md=request.form.get('story',"")
    post_md=request.form.get('post',"")
    bid=request.form.get("book",0)

    honeypot=request.form.get('subtitle',"")
    if honeypot:
        abort(418)

    #validate info
    if len(title_md)<5 or len(story_md)<10:
        return render_template('badstory.html')
    if bid!=0:
        b=Book(bid=bid)
        if b.author_id != v.id:
            abort(403)

    #assemble data for story object and save it
    data=(-1,0,"","","", False, title_md, v.id,None,pre_md,story_md,post_md, bid)
    story=Story(result=data)
    return story.save()
    
@app.route('/api/banuser/<uid>', methods=["POST"])
@auth_required
@admin_required
def ban_user(q, v, uid):
    u=User(uid=uid)
    u.ban()
    return redirect(u.url)
    
@app.route('/api/unbanuser/<uid>', methods=["POST"])
@auth_required
@admin_required
def unban_user(q, v, uid):
    u=User(uid=uid)
    u.unban()
    return redirect(u.url)
    
@app.route('/api/banstory/<sid>', methods=["POST"])
@auth_required
@admin_required
def ban_story(q, v, sid):
    s=Story(sid=sid)
    s.ban()
    return redirect(s.url)
    
@app.route('/api/unbanstory/<sid>', methods=["POST"])
@auth_required
@admin_required
def unban_story(q, v, sid):
    s=Story(sid=sid)
    s.unban()
    return redirect(s.url)


@app.route('/api/deletestory/<sid>', methods=["POST"])
@auth_required
def delete_story(q, v, sid):
    s=Story(sid=sid)
    if not v.id==s.author_id:
        abort(403)
    s.delete()
    return redirect(s.url)
    
@app.route('/api/undeletestory/<sid>', methods=["POST"])
@auth_required
def undelete_story(q, v, sid):
    s=Story(sid=sid)
    if not v.id==s.author_id:
        abort(403)
    s.undelete()
    return redirect(s.url)

@app.route("/api/edit/<sid>", methods=["POST"])
@auth_required
@not_banned
@agree_required
def post_edit_story(q, v, sid):
    try:
        s=Story(sid=sid)
    except KeyError:
        abort(404)

    if not v.id == s.author_id:
        abort(403)

    honeypot=request.form.get("subtitle","")
    if honeypot:
        abort(418)

    bid=int(request.form.get("book",0))
    
    title=request.form.get("title","")
    pre_md=request.form.get("pre","")
    story_md=request.form.get("story","")
    post_md=request.form.get("post","")

    s.edit(title, pre_md, story_md, post_md)
    s.set_book(bid)

    return redirect(s.url)

@app.route("/api/makebook", methods=["POST"])
@auth_required
@not_banned
@agree_required
def make_book(q, v):

    honeypot=request.form.get("subtitle","")
    if honeypot:
        abort(418)

    title=request.form.get('title',"")
    description=request.form.get('desc',"")
    
    result=(0,title,v.id,"",description,0,False,False)

    b=Book(result=result)
    
    return b.save()

@app.route("/api/editbook/<bid>", methods=["POST"])
@auth_required
@not_banned
@agree_required
def post_edit_book(q, v, bid):
    try:
        b=Book(bid=bid)
    except KeyError:
        abort(404)

    if not v.id == b.author_id:
        abort(403)

    honeypot=request.form.get("subtitle","")
    if honeypot:
        abort(418)
    
    title=request.form.get("title","")
    description=request.form.get("desc","")

    b.edit(title, description)

    return redirect(b.url)

###
@app.route('/api/banbook/<bid>', methods=["POST"])
@auth_required
@admin_required
def ban_book(q, v, bid):
    b=Book(bid=bid)
    b.ban()
    return redirect(b.url)
    
@app.route('/api/unbanbook/<bid>', methods=["POST"])
@auth_required
@admin_required
def unban_book(q, v, bid):
    b=Book(bid=bid)
    b.unban()
    return redirect(b.url)


@app.route('/api/deletebook/<bid>', methods=["POST"])
@auth_required
def delete_book(q, v, bid):
    b=Book(bid=bid)
    if not v.id==b.author_id:
        abort(403)
    b.delete()
    return redirect(b.url)
    
@app.route('/api/undeletebook/<bid>', methods=["POST"])
@auth_required
def undelete_book(q, v, bid):
    b=Book(bid=bid)
    if not v.id==b.author_id:
        abort(403)
    b.undelete()
    return redirect(b.url)


