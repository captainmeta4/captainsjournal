import psycopg2
import os
import re
from flask import *
import mistletoe
import bleach

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

#clear any aborted transactions from previous iteration (debugging)
c.execute("ROLLBACK TRANSACTION")

#prepare parameterized sql statements
#for users
c.execute("PREPARE MakeUser(text) AS INSERT INTO Users (reddit_name, created_utc, google_analytics) VALUES ($1,'NOW','') RETURNING *")
c.execute("PREPARE GetUserByName(text) AS SELECT * FROM Users WHERE UPPER(reddit_name) = UPPER($1)")
c.execute("PREPARE GetUserByID(int) AS SELECT * FROM Users WHERE id = $1")
c.execute("PREPARE BanUser(int) AS UPDATE Users SET banned='true' WHERE id=$1")
c.execute("PREPARE UnbanUser(int) AS UPDATE Users Set banned='false' WHERE id=$1")

#for stories
c.execute("PREPARE MakeStory(int, text, text, text, text, text, text, text) AS INSERT INTO Stories (author_id, created, title, pre, story, post, pre_raw, story_raw, post_raw) VALUES ($1,'NOW', $2, $3, $4, $5, $6, $7, $8) RETURNING *")
c.execute("PREPARE EditStory(int, text, text, text, text, text, text) AS UPDATE Stories SET pre=$2, story=$3, post=$4, pre_raw=$5, story_raw=$6, post_raw=$7 WHERE id=$1")
c.execute("PREPARE GetStoryById(int) AS SELECT * FROM Stories WHERE id = $1")
c.execute("PREPARE GetStoriesByAuthorId(int) AS SELECT * FROM Stories WHERE author_id = $1 ORDER BY id DESC")
c.execute("PREPARE BanStory(int) AS UPDATE Stories SET banned='true' WHERE id=$1")
c.execute("PREPARE UnbanStory(int) AS UPDATE Stories Set banned='false' WHERE id=$1")
c.execute("PREPARE DeleteStory(int) AS UPDATE Stories SET deleted='true' WHERE id=$1")
c.execute("PREPARE UndeleteStory(int) AS UPDATE Stories Set deleted='false' WHERE id=$1")

#Module global
Cleaner=bleach.sanitizer.Cleaner(tags=bleach.sanitizer.ALLOWED_TAGS+['p', 'h1','h2','h3','h4','h5','h6','hr','br','table','tr','th','td'])

class User():

    def __init__(self, name="", uid=0, make=False):

        if not(name or uid):
            raise ValueError("One of name or uid must be provided")
        if (name and uid):
            raise ValueError("Only one of name or uid can be provided")

        #check database
        #sanitize name
        if name:
            name=re.search("^[A-Za-z0-9_-]+", name).group(0)


        if name:
            c.execute("EXECUTE GetUserByName(%s)", (name,))
        elif uid:
            c.execute("EXECUTE GetUserById(%s)", (uid,))

        result=c.fetchone()

        if result is None:
            if make and name:
                c.execute("EXECUTE MakeUser(%s)", (name,))
                conn.commit()
                result=c.fetchone()
            else:
                raise KeyError("User not found")

        self.id=int(result[0])
        self.name=result[1]
        self.created=result[2]
        self.banned=bool(result[4])
        self.admin=bool(result[5])
        self.url="/u/{}".format(self.name)
        self.created_date=str(self.created).split()[0]

    def render_userpage(self, v=None):

        return render_template('userpage.html', u=self, stories=self.stories(), v=v)

    def stories(self):
        

        c.execute("EXECUTE GetStoriesByAuthorId(%s)", (self.id,))
        output=[]
        for l in c.fetchall():
            output.append(Story(result=l))

        return output

    def ban(self):

        c.execute("EXECUTE BanUser(%s)", (self.id,))
        conn.commit()

    def unban(self):

        c.execute("EXECUTE UnbanUser(%s)", (self.id,))
        conn.commit()

class Story():

    def __init__(self, sid=0, result=None, make=False, load_author=False):

        if result is None:
            #sanitize id
            sid=re.search("^[0-9]+", str(sid)).group(0)

            #check database
            c.execute("EXECUTE GetStoryById(%s)", (sid,))
            result=c.fetchone()

            if result is None:
                raise KeyError('story with that id does not exist')


        self.id=int(result[0])
        self.created=result[1]
        self.pre=result[2]
        self.story=result[3]
        self.post=result[4]
        self.banned=bool(result[5])
        self.title=result[6]
        self.author_id=int(result[7])
        self.deleted=bool(result[8])
        self._pre_raw=result[9]
        self._story_raw=result[10]
        self._post_raw=result[11]
        
        self.url="/s/{}".format(self.id)
        self.created_date=str(self.created).split()[0]

        if load_author:
            self.author=User(uid=self.author_id)
        else:
            self.author=None

    def process(self):
        
        #render markdown
        self.pre=mistletoe.markdown(self._pre_raw)
        self.story=mistletoe.markdown(self._story_raw)
        self.post=mistletoe.markdown(self._post_raw)

        #sanitize html
        self.title=Cleaner.clean(self.title)
        self.pre=Cleaner.clean(self.pre)
        self.story=Cleaner.clean(self.story)
        self.post=Cleaner.clean(self.post)

    def save(self):

        if self.id!=-1:
            raise Exception("This story seems to already exist. Use `edit()` instead.")

        self.process()
        c.execute("EXECUTE MakeStory(%s,%s,%s,%s,%s,%s,%s,%s)", (self.author_id, self.title, self.pre, self.story, self.post, self._pre_raw, self._story_raw, self._post_raw))
        data=c.fetchone()
        conn.commit()
        s=Story(result=data)
        return redirect(s.url)

    def edit(self, pre, story, post):
        
        if self.id==-1:
            raise KeyError("This story does not yet exist. Use `save()` instead.")

        self._pre_raw=pre
        self._story_raw=story
        self._post_raw=post
        self.process()
        
        c.execute("EXECUTE EditStory(%s,%s,%s,%s,%s,%s,%s)",  (self.id, self.pre, self.story, self.post, self._pre_raw, self._story_raw, self._post_raw))
        conn.commit()
        
    def render_storypage(self, v=None):
        
        return render_template('storypage.html', s=self, v=v)

    def ban(self):

        c.execute("EXECUTE BanStory(%s)", (self.id,))
        conn.commit()

    def unban(self):

        c.execute("EXECUTE UnbanStory(%s)", (self.id,))
        conn.commit()

    def delete(self):
        c.execute("EXECUTE DeleteStory(%s)", (self.id,))
        conn.commit()

    def undelete(self):

        c.execute("EXECUTE UndeleteStory(%s)", (self.id,))
        conn.commit()

class Listing():

    def __init__(self, kind="new"):
        if kind=='new':
            c.execute("SELECT * FROM Stories WHERE banned='false' AND deleted='false' ORDER BY id DESC LIMIT 10")
        self.raw=c.fetchall()

    def __iter__(self):
        for entry in self.raw:
            yield Story(result=entry, load_author=True)
            
