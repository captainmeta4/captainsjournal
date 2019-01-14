import praw
from flask import *
import os
import time
from .classes import *
import patreon
import hashlib
import json
import hmac
import jinja2
import re
import requests


### NAMING CONVENTIONS ###
# s - Story object
# v - viewer (the person browsing) - User object
# u - target user - User object
# q - Temporary reddit object
# l - Listing object for homepages
# p - pledge object


#globals
app=Flask(__name__,)

user_agent="Captain's Journal by /u/captainmeta4"
r=praw.Reddit(client_id=os.environ.get('client_id'),
              client_secret=os.environ.get('client_secret'),
              redirect_uri=os.environ.get('reddit_uri'),
              user_agent=user_agent)

PATREON_ID=os.environ.get('patreon_id')
PATREON_SECRET=os.environ.get('patreon_secret')

COOKIE=os.environ.get('cookie')
DOMAIN=os.environ.get('domain')

#define jinja2 custom filters
@app.template_filter("os_get")
def os_get(key):
    return os.environ.get(key)

#take care of static pages
@app.route('/assets/<path:path>')
def static_service(path):
    return send_from_directory('assets', path)
  
#take care of robots
@app.route('/robots.txt')
def robots_txt():
    return send_file('static/robots.txt')

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

    token=request.cookies.get(COOKIE)
    if token==None:
        raise KeyError('not found')
    else:
        return token

def auth_required(f):
    '''
    wrapper for returning 401 if user not logged in
    '''

    def wrapper(*args, **kwargs):

        try:
            token=check_token()
        except:
            return abort(401)
          
        try:
            v=User(token=token)
            q=temporary_reddit(token)
        except:
            try:
                q=temporary_reddit(token)
                name=q.user.me().name
                v=User(name=name, make=True)
                v.update_token(token)
            except:
                abort(401)

        return f(*args, q=q, v=v, **kwargs)

    wrapper.__name__=f.__name__
    return wrapper

def auth_desired(f): #but not necessary
    '''
    wrapper for passing logged in user to function
    passes None if not logged in
    '''

    def wrapper(*args, **kwargs):

        try:
            token=check_token()
        except:
            return f(*args, v=None, **kwargs)
  
        try:
            v=User(token=token)
        except:
            try:
                q=temporary_reddit(token)
                name=q.user.me().name
                v=User(name=name, make=True)
                v.update_token(token)
            except:
                return f(*args, v=None, **kwargs)

        return f(*args, v=v, **kwargs)

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
  
#take care of error pages
@app.errorhandler(401)
@auth_desired
def error_401(e, v):
    return render_template('401.html', v=v), 401

@app.errorhandler(403)
@auth_desired
def error_403(e, v):
    return render_template('403.html', v=v), 403

@app.errorhandler(404)
@auth_desired
def error_404(e, v):
    return render_template('404.html', v=v), 404

@app.errorhandler(405)
@auth_desired
def error_405(e, v):
    return render_template('405.html', v=v), 405

@app.errorhandler(500)
@auth_desired
def error_500(e, v):
    return render_template('500.html', v=v, e=e), 500

#take care of mostly static content
@app.route('/info/<path:filename>')
@auth_desired
def rules(v, filename):
    filepath=safe_join("/info/",filename)
    file="{}.html".format(filepath)
    try:
        return render_template(file,v=v)
    except jinja2.exceptions.TemplateNotFound:
        abort(404)

@app.route('/submit')
@auth_required
def create_submission(q, v):
    return render_template('submit.html', v=v)
  
@app.route('/your_data')
@auth_required
def your_data(q,v):
    return render_template("your_data.html",v=v)

@app.route("/makebook")
@auth_required
@not_banned
def create_book(q, v):
    return render_template('submitbook.html',v=v)

@app.route('/')
@auth_desired
def home(v):
    new=Listing(kind='new')
    news=Listing(kind='news')
    return render_template('home.html', v=v, l=new,news=news)

@app.route("/oauth/redirect")
def oauth_redirect():
    '''
    Handle incoming redirects from reddit oauth flow
    '''

    #get redditor name
    code = request.args.get('code')
    print(code)
    token=r.auth.authorize(code)

    q=temporary_reddit(token)

    name=q.user.me().name

    #create user if it doesn't yet exist
    v=User(name=name, make=True)

    resp=make_response(redirect(v.url))
    resp.set_cookie(COOKIE, value=token, domain=DOMAIN)

    return resp

@app.route("/oauth/patreon")
@auth_required
def patreon_redirect(q, v):
    '''
    Handle incoming redirects from patreon oauth flow
    '''

    #get code
    code = request.args.get('code')
    
    oauth_client = patreon.OAuth(PATREON_ID, PATREON_SECRET)
    tokens = oauth_client.get_tokens(request.args.get('code'), 'https://{}/oauth/patreon'.format(DOMAIN))
    access_token = tokens['access_token']
    refresh_token=tokens['refresh_token']
    
    
    #assemble request
    header={"Authorization":"Bearer "+access_token}
    params={"include":"campaign",
            "fields[user]":"vanity"}
    url="https://www.patreon.com/api/oauth2/v2/identity"
    
    x=requests.get(url, headers=header, params=params)
    
    j=x.json()
    print(j)
    
    name=j['data']['attributes']['vanity']
    p_id=j['data']['id']
    try:
        c_id=j['data']["relationships"]["campaign"]["data"]["id"]
    except KeyError:
        c_id=0
    
    v.set_patreon(name, p_id, access_token, refresh_token, c_id)
    
    return redirect("/settings")

@app.route("/me")
@auth_required
def me_page(v):
    return redirect(v.url)
            
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
        
    over_18 = request.cookies.get("over_18", False)
    return s.render_storypage(v=v, over18override=over_18)

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
        b=Book(bid=bid, load_author=True)
    except KeyError:
        abort(404)

    if not v.id == b.author_id:
        abort(403)

    return render_template('editbook.html', b=b, v=v)

@app.route("/settings")
@auth_required
def settings_page(q,v):
    return render_template("settings.html", v=v)
    
#API hits
@app.route('/api/submit', methods=["POST"])
@auth_required
@not_banned
@agree_required
def create_story(q, v):
    
    title_md=request.form.get('title',"")
    pre_md=request.form.get('pre',"")
    story_md=request.form.get('story',"")
    post_md=request.form.get('post',"")
    bid=int(request.form.get("book",0))
    nsfw=request.form.get("nsfw",False)
    try:
        patreon_threshold=int(request.form.get('patreon_threshold',0))
    except:
        patreon_threshold=0

    honeypot=request.form.get('subtitle',"")
    if honeypot:
        abort(418)

    #validate info
    if len(title_md)<5 or len(story_md)<10:
        return render_template('badstory.html')

    #assemble data for story object and save it
    data=(-1,0,"","","", False, title_md, v.id,None,pre_md,story_md,post_md, bid,False,0,0,False,None,None)
    story=Story(result=data)
    s=story.save()

    if nsfw:
        s.set_nsfw(True)
    if patreon_threshold:
        s.set_patreon_threshold(patreon_threshold)
    if bid:
        s.set_book(bid)

    return redirect(s.url)
    
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
@not_banned
def delete_story(q, v, sid):
    s=Story(sid=sid)
    if not v.id==s.author_id:
        abort(403)
    s.delete()
    return redirect(s.url)
    
@app.route('/api/undeletestory/<sid>', methods=["POST"])
@auth_required
@not_banned
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
        s=Story(sid=sid, load_author=True)
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
    patreon_threshold=int(request.form.get("patreon_threshold",0))
    

    s.edit(title, pre_md, story_md, post_md)
    s.set_book(bid)

    nsfw=request.form.get("nsfw")
    if nsfw != s.nsfw:
        s.set_nsfw(nsfw=nsfw)
    if patreon_threshold != s.patreon_threshold:
        s.set_patreon_threshold(patreon_threshold)

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
    
    result=(0,title,v.id,"",description,0,False,False,0,False)

    book=Book(result=result)
    b=book.save()
    return redirect(b.url)

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
@not_banned
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


@app.route('/api/settings', methods=["POST"])
@auth_required
def settings_api(q,v):
    
    google=request.form.get('analytics','')
    v.set_google(google)

    over18=request.form.get('over18')
    if over18 != v.over18:
        v.set_over18(over18=over18)

    return redirect("/settings")

@app.route('/api/unlink_patreon', methods=["POST"])
@auth_required
def unlink_patreon(q,v):

    v.set_patreon("", 0, None, None, 0)
    return redirect("/settings")

@app.route("/api/s/<sid>")
def story_json(sid):
    try:
        s=Story(sid=sid)
    except KeyError:
        abort(404)
    return jsonify(s.json())

@app.route("/api/b/<bid>")
def book_json(bid):
    try:
        b=Book(bid=bid)
    except KeyError:
        abort(404)
    return jsonify(b.json())

@app.route("/api/u/<name>")
def user_json(name):
    try:
        u=User(name=name)
    except KeyError:
        abort(404)
    return jsonify(u.json())

@app.route("/api/uid/<uid>")
def uid_json(uid):
    try:
        u=User(uid=uid)
    except:
        abort(404)
    return jsonify(u.json())

@app.route("/api/postreddit/<sid>", methods=["POST"])
@auth_required
def post_reddit(q, v, sid):
    s=Story(sid=sid)
    if not v.id==s.author_id:
        abort(403)

    if s.reddit or s.subreddit or s.banned or s.deleted or s.patreon_threshold:
        abort(403)
    
    subreddit=request.form.get("subreddit")
    
    sub=q.subreddit(subreddit)

    description = re.match("^\s?(.*?\s+){0,30}", s._story_raw).group(0)
    description+="..."

    
    if s.book_id:
        b=Book(bid=s.book_id)
        title="[{}] {}".format(b.title, s.title)
        description = b._description_raw+"\n\n---\n\n"+description
    else:
        title=s.title

    #remove html
    description = re.sub("</?\w+.*?(>|$)","",description)
    #remove images
    description = re.sub("!\[.*?\]\(.*?\)","",description)
        

    body="[**LINK**](https://{}{})\n\n---\n\n{}\n\n---\n\n[**LINK**](https://{}{})".format(DOMAIN, s.url, description, DOMAIN, s.url)    
    try:
        submission=sub.submit(title, selftext=body)
    except:
        abort(400)
        
    s.set_reddit(submission.id, submission.subreddit.display_name)

    return redirect("https://reddit.com"+submission.permalink)

@app.route("/api/logout")
@auth_required
def logout(q,v):

    resp = make_response(redirect('/'))
    resp.set_cookie(COOKIE, value="", domain=DOMAIN)
    return resp

@app.route("/api/set_nsfw", methods=["GET"])
def api_set_nsfw():
    
    x=request.values.get("over_18", False)
    sid=request.values.get("redirect", None)
    
    if sid:
        resp=make_response(redirect("/s/{}".format(sid)))
    else:
        resp=make_response(redirect("/"))
    
    resp.set_cookie("over_18", True, 3600)
    
    return resp
