import praw
import psycopg2
import Flask
import os
import time
from classes import *

#globals
app=Flask.app(__name__)
conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()
user_agent="Captain's Journal by /u/captainmeta4"
r=praw.Reddit(client_id=os.environ.get('client_id'),
              client_secret=os.environ.get('client_secret'),
              redirect_uri="https://cj.captainmeta4.me/oauth/redirect",
              user_agent=user_agent)

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
    if token=None:
        return None
    else:
        return temporary_reddit(token)

@app.route('/'):
def home():
    return make_response("home page")
    

@app.route("/oauth/redirect")
def redirect():
'''
Handle incoming redirects from reddit oauth flow
'''

    #get redditor name
    code = request.args.get('code')
    token=r.auth.authorize(code)

    q=temporary_reddit(token)

    name=q.user.me().name

    #check database
    s="SELECT * FROM Users WHERE reddit_name=@0"
    c.execute(s, name)
    result=c.fetchone()

    if result is None:
        s="INSERT INTO Users (reddit_name, created_utc, banned, posts, comments, google_analytics) VALUES (@0,NOW,0,'','','')"
        c.execute(s,name)
        conn.commit()

    resp=make_response(redirect('https://cj.captainmeta4.me/me'))
    resp.set_cookie("cj_reddit", value=token, domain="cj.captainmeta4.me")

    return resp

@app.route("/me")
def me_page():
    
    q=check_token()
    if q is None:
        return redirect('/')

    name=q.user.me().name

    return redirect('/user/{}'.format(name))
            
@app.route("/user/<name>")
def userpage()

    try:
        u=User(name)
    except KeyError:
        abort(404)

    output=("username: {}"
            "created at: {}"
            "id: {}"
            "banned: {}")
    output=output.format(name,u.created,u.id,str(u.banned))
    return make_response(output)

