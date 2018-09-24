import praw
from flask import *
import os
import time
from classes import *
from flaskext.markdown import Markdown

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

@app.route('/submit')
def create_submission():
    return render_template('submit.html')

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

    def wrapper():

        try:
            q=check_token()
            name=q.user.me().name
        except:
            abort(401)

        return f(q, name)

    wrapper.__name__=f.__name__
    return wrapper

@app.route('/')
def home():
    return render_template('home.html')
    

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



    resp=make_response(redirect('/'))
    resp.set_cookie("logbook_reddit", value=token, domain="captainslogbook.org")

    return resp

@app.route("/me")
def me_page():
    try:
        q=check_token()
    except ValueError:
        return redirect('/')
    
    name=q.user.me().name

    return redirect('/user/{}'.format(name))
            
@app.route("/u/<name>")
def userpage(name):
    
    try:
        u=User(name=name)
    except KeyError:
        abort(404)

    return u.render_userpage()

@app.route("/s/<sid>")
def storypage(sid):

    try:
        s=Story(sid, load_author=True)
    except KeyError:
        abort(404)

    return s.render_storypage()

#API hits
@app.route('/api/submit', methods=["POST"])
@auth_required
def create_story(q, name):
    title_md=request.form.get('form-title',"")
    pre_md=request.form.get('form-pre',"")
    story_md=request.form.get('form-story',"")
    post_md=request.form.get('form-post')

    #validate info
    if len(title_md)<5:
        abort(400)
    if len(story_md)<100:
        abort(400)

    author=User(name=name)

    #assemble data for story object and save it
    data=(-1,0,pre_md,story_md,post_md, False, title_md, author.id,None)
    story=Story(result=data)
    return story.save()
    
    

    
    
    
