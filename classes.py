import psycopg2
import os
import re
from flask import *

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

#clear any aborted transactions from previous iteration (debugging)
c.execute("ROLLBACK TRANSACTION")

#prepare parameterized sql statements
#for users
c.execute("PREPARE MakeUser(name) AS INSERT INTO Users (reddit_name, created_utc, banned, google_analytics) VALUES ($1,'NOW','false','')")
c.execute("PREPARE GetUserByName(name) AS SELECT * FROM Users WHERE reddit_name = $1")
c.execute("PREPARE GetUserByID(int) AS SELECT * FROM Users WHERE id = $1")

#for stories
c.execute("PREPARE MakeStory(int, text, text, text) AS INSERT INTO Stories (author_id, created, pre, story, post, banned) VALUES ($1,'NOW', $2, $3, $4, 'false')")
c.execute("PREPARE GetStoryById(int) AS SELECT * FROM Stories WHERE id = $1")
c.execute("PREPARE GetStoriesByAuthorId(int) AS SELECT * FROM Stories WHERE author_id = $1")

class User():

    def __init__(self, name="", uid=0, make=False):

        if not(name or uid):
            raise ValueError("One of name or uid must be provided")
        if (name and uid):
            raise ValueError("Only one of name or uid can be provided")

        #check database
        if name:
            #sanitize name
            name=re.search("^[A-Za-z0-9_-]+", name).group(0)
            c.execute("EXECUTE GetUserByName('{}')".format(name))
        elif uid:
            c.execute("EXECUTE GetUserById({})".format(str(uid)))

        result=c.fetchone()

        if result is None and make and name:
            c.execute("EXECUTE MakeUser('{}')".format(name))
            c.execute("EXECUTE GetUserByName('{}')".format(name))
            result=c.fetchone()
        elif result is None:
            return None

        self.id=str(result[0])
        self.name=result[1]
        self.created=result[2]
        self.banned=bool(result[4])
        self.url="/u/{}".format(self.id)
        self.created_date=str(self.created).split()[0]

    def render_userpage(self):

        stories=self.stories()

        return render_template('userpage.html', u=self, stories=stories)

    def stories(self):

        c.execute("EXECUTE GetStoriesByAuthorId('{}')".format(self.id))
        return c.fetchall()

class Story():

    def __init__(self, sid, make=False):

        #sanitize id
        sid=re.search("^[0-9]+", str(sid)).group(0)

        #check database
        c.execute("EXECUTE GetStoryById('{}')".format(sid))
        result=c.fetchone()

        if result is None:
            raise KeyError('story with that id does not exist')


        self.id=int(result[0])
        self.author_id=int(result[7])
        self.created=result[1]
        self.pre=result[2]
        self.story=result[3]
        self.post=result[4]
        self.banned=bool(result[5])
        self.title=result[6]
        self.url="/s/{}".format(self.id)
        self.created_date=str(self.created).split()[0]

    def author(self):

        return User(uid=self.author_id)

    def render_storypage(self):
        return render_template('storypage.html', s=self)
