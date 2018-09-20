import praw
from flask import *
import os
import time
from classes import *
from flaskext.markdown import Markdown

#globals
app=Flask(__name__)
user_agent="Captain's Journal by /u/captainmeta4"
r=praw.Reddit(client_id=os.environ.get('client_id'),
              client_secret=os.environ.get('client_secret'),
              redirect_uri="https://cj.captainmeta4.me/oauth/redirect",
              user_agent=user_agent)

@app.route('/assets/<path:path>')
def static_service(path):
    return send_from_directory('assets', path)

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

    token=request.cookies.get("cj_reddit")
    if token==None:
        raise ValueError('not found')
    else:
        return temporary_reddit(token)

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



    resp=make_response(redirect('https://cj.captainmeta4.me/me'))
    resp.set_cookie("cj_reddit", value=token, domain="cj.captainmeta4.me")

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
        s=Story(sid)
    except KeyError:
        abort(404)

    return s.render_storypage()
