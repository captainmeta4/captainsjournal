import os
import re
from flask import *
import mistletoe
import bleach
import time
from .db_prep import c, db

#Sanitization object used throughout module
tags=bleach.sanitizer.ALLOWED_TAGS+['p', 'h1','h2','h3','h4','h5','h6','hr','br','table','tr','th','td','del','thead','tbody','tfoot','pre','div','span','img']
attrs=bleach.sanitizer.ALLOWED_ATTRIBUTES
attrs['*']=["class","style"]
attrs['img']=["height","width","alt","src"]
styles=['white-space',"border","border-radius","text-align","align", "float","margin","padding"]
Cleaner=bleach.sanitizer.Cleaner(tags=tags, attributes=attrs, styles=styles)

#SQL timestamp to readable time string
def time_string(timestamp):
    if timestamp is None:
        return None
    try:
        t=str(timestamp).split('.')[0]
        t=time.strptime(t,"%Y-%m-%d %H:%M:%S")
        t=time.strftime("%d %B %Y at %H:%M:%S",t)
    except:
        return None
    return t

class User():

    def __init__(self, name="", uid=0, token=None, make=False):

        if not(name or uid or token):
            raise ValueError("One of name or uid must be provided")

        #check database
        #sanitize name and token
        if name:
            name=re.search("^[A-Za-z0-9_-]+", name).group(0)
        
        if token:
            c.execute("EXECUTE GetUserByToken(%s)", (token,))    
        elif name:
            c.execute("EXECUTE GetUserByName(%s)", (name,))
        elif uid:
            c.execute("EXECUTE GetUserById(%s)", (uid,))

        result=c.fetchone()

        if result is None:
            if make and name:
                c.execute("EXECUTE MakeUser(%s)", (name,))
                db.commit()
                result=c.fetchone()
            else:
                raise KeyError("User not found")

        self.id=int(result[0])
        self.name=result[1]
        self.created=result[2]
        self.google_analytics=result[3]
        self.banned=bool(result[4])
        self.admin=bool(result[5])
        self.agreed=bool(result[6])
        self.patreon=result[8]
        self.over18=result[9]
        self.patreon_id=int(result[10])
        self.patreon_webhook_secret=result[11]
        
        self.url="/u/{}".format(self.name)
        self.created_date=time_string(self.created).split(" at ")[0]

    def set_patreon(self, name, pid):
        c.execute("EXECUTE SetPatreon(%s, %s, %s)", (self.id, pid, name))
        db.commit()

    def set_google(self, tracking_id):

        if tracking_id:
            c.execute("EXECUTE SetGoogle(%s, %s)", (self.id, tracking_id))
        else:
            c.execute("EXECUTE SetGoogle(%s, %s)", (self.id, ""))
        db.commit()

    def set_patreon_webhook(self, secret):

        if secret:
            c.execute("EXECUTE SetPatreonWebhook(%s, %s)", (self.id, secret))
        else:
            c.execute("EXECUTE SetPatreonWebhook(%s, %s)", (self.id, ""))
        db.commit()
        
    def tos_agree(self):
        c.execute("UPDATE Users SET agreed='true' WHERE id=%s",(self.id,))
        self.agreed=True
        db.commit()
	
    def update_token(self, token):
        c.execute("EXECUTE UpdateToken(%s,%s)", (self.id, token))
        db.commit()

    def render_userpage(self, v=None):

        return render_template('userpage.html', u=self, stories=self.stories(), v=v)

    def stories(self):
        
        c.execute("EXECUTE GetStoriesByAuthorId(%s)", (self.id,))
        
        for l in c.fetchall():
            yield Story(result=l)

    def books(self):

        c.execute("EXECUTE GetBooksByAuthorId(%s)", (self.id,))
        for l in c.fetchall():
            yield Book(result=l)

    def ban(self):

        c.execute("EXECUTE BanUser(%s,%s)", (self.id, True))
        db.commit()

    def unban(self):

        c.execute("EXECUTE BanUser(%s,%s)", (self.id, False))
        db.commit()

    def set_over18(self, over18=False):
        c.execute("EXECUTE SetOver18(%s, %s)", (self.id, over18))
    
    def json(self):
        
        output = self.__dict__
        
        if not self.banned:
            stories=[]
            books=[]
            for s in self.stories():
                if not s.banned and not s.deleted:
                    stories.append(s.id)
            for b in self.books():
                if not b.banned and not b.deleted:
                    books.append(b.id)
            output['stories']=stories
            output['books']=books
            
        output.pop("patreon_webhook_secret")
        output.pop("patreon_id")
        output.pop("agreed")
        output.pop("google_analytics")
        output.pop("over18")
        
        return output

class Story():

    def __init__(self, sid=0, result=None, load_author=False):

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
        self.book_id=int(result[12])
        self.nsfw=bool(result[13])
        self.patreon_threshold=int(result[14])
        self.edited=result[15]
        self.distinguished=bool(result[16])
        self.reddit=result[17]
        self.subreddit=result[18]
        
        self.url="/s/{}".format(self.id)
        self.created_date=time_string(self.created)
        self.edited_date=time_string(self.edited)

        if load_author:
            self.author=User(uid=self.author_id)
        else:
            self.author=None

    def set_reddit(self, reddit_id, subreddit)

        c.execute("EXECUTE SetReddit(%s,%s,%s)",(self.id, reddit_id, subreddit))
    
    def json(self):
        
        output=self.__dict__
        
        output.pop("_pre_raw")
        output.pop("_story_raw")
        output.pop("_post_raw")
        output.pop("author")
        
        if self.banned or self.deleted or self.patreon_threshold:
            output.pop("pre")
            output.pop("story")
            output.pop("post")
        
        return output
    
    def set_nsfw(self, nsfw=False):
        c.execute("EXECUTE SetNSFW(%s, %s)", (self.id, nsfw))
        db.commit()

    def set_patreon_threshold(self, cents):
        c.execute("EXECUTE SetPatreonThreshold(%s,%s)", (self.id, cents))
        db.commit()

    def book(self):

        if self.book_id==0:
            return None
        
        return Book(bid=self.book_id)       

    def next(self):

        if self.book_id==0:
            return None

        c.execute("SELECT * FROM Stories WHERE book_id=%s AND id>%s ORDER BY id ASC LIMIT 1", (self.book_id, self.id))
        result=c.fetchone()
        if result is None:
            return None

        return Story(result=result)

    def previous(self):

        if self.book_id==0:
            return None

        c.execute("SELECT * FROM Stories WHERE book_id=%s AND id<%s ORDER BY id DESC LIMIT 1", (self.book_id, self.id))
        result=c.fetchone()
        if result is None:
            return None

        return Story(result=result)
    
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
        c.execute("EXECUTE MakeStory(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (self.author_id, self.title, self.pre, self.story, self.post, self._pre_raw, self._story_raw, self._post_raw, self.book_id))
        data=c.fetchone()
        db.commit()
        s=Story(result=data)
        return s
    
    def edit(self, title, pre, story, post):
		
        if self.id==-1:
            raise KeyError("This story does not yet exist. Use `save()` instead.")

        if title==self.title and pre==self._pre_raw and story==self._story_raw and post == self._post_raw:
            return
	
        self.title=title
	
        self._pre_raw=pre
        self._story_raw=story
        self._post_raw=post
        self.process()
        
        c.execute("EXECUTE EditStory(%s,%s,%s,%s,%s,%s,%s,%s)",  (self.id, self.pre, self.story, self.post, self._pre_raw, self._story_raw, self._post_raw, self.title))
        db.commit()

    def set_book(self, bid):

        if bid==0:
            c.execute("UPDATE Stories SET book_id=0 WHERE id=%s", (self.id,))
            db.commit()
            return

        b=Book(bid=bid)
        if b.author_id!=self.author_id and not(bid==4 and self.author.admin):
                abort(403)

        c.execute("UPDATE Stories SET book_id=%s WHERE id=%s", (bid, self.id))
        db.commit()

    def render_storypage(self, v=None):

        cent_string=str(self.patreon_threshold).rjust(3,'0')
        d=str(self.patreon_threshold)[0:-2]
        c=str(self.patreon_threshold)[-2:]

        if self.patreon_threshold and v:
            pledge_cents=Pledge(self.author.patreon_id, v.patreon_id).amount_cents
        else:
            pledge_cents=0
        
        return render_template('storypage.html', s=self, v=v, d=d, c=c, pledge_cents=pledge_cents)

    def ban(self):

        c.execute("EXECUTE BanStory(%s, %s)", (self.id, True))
        db.commit()

    def unban(self):

        c.execute("EXECUTE BanStory(%s, %s)", (self.id, False))
        db.commit()

    def delete(self):
        c.execute("EXECUTE DeleteStory(%s, %s)", (self.id, True))
        db.commit()

    def undelete(self):

        c.execute("EXECUTE DeleteStory(%s, %s)", (self.id, False))
        db.commit()

class Listing():

    def __init__(self, kind="new"):
        self.kind=kind
        
        if kind=='new':
            c.execute("SELECT * FROM Stories WHERE banned='false' AND deleted='false' AND book_id<>4 ORDER BY id DESC LIMIT 15")
        elif kind=='news':
            c.execute("SELECT * FROM Stories WHERE banned='false' AND deleted='false' AND book_id=4 ORDER BY id DESC LIMIT 5")
        self.raw=c.fetchall()

    def __iter__(self):

        
        for entry in self.raw:
            yield Story(result=entry, load_author=True)
            
class Book():

    def __init__(self, bid=0, result=None, load_author=None):

        if result is None:
            #sanitize id
            sid=re.search("^[0-9]+", str(bid)).group(0)

            #check database
            c.execute("EXECUTE GetBookById(%s)", (bid,))
            result=c.fetchone()

            if result is None:
                raise KeyError('book with that id does not exist')
            
        self.id=int(result[0])
        self.title=result[1]
        self.author_id=result[2]
        self.description=result[3]
        self._description_raw=result[4]
        self.created=result[5]
        self.banned=result[6]
        self.deleted=result[7]
        self.edited=result[8]
        self.distinguished=bool(result[9])

        self.created_date=time_string(self.created)
        self.edited_date=time_string(self.edited)
        self.url="/b/{}".format(str(self.id))

        if load_author:
            self.author=User(uid=self.author_id)
        else:
            self.author=None

    def json(self):
        
        output=self.__dict__
        
        output.pop("_description_raw")
        output.pop("author")
        
        if self.banned or self.deleted:
            output.pop(self.description)
        else:
            stories=[]
            for s in self.stories():
                if not s.banned and not s.deleted:
                    stories.append(s.id)
            output['stories']=stories
            
        return output

    def save(self):
    
        self.title=Cleaner.clean(self.title)
        self.description=Cleaner.clean(mistletoe.markdown(self._description_raw))

        c.execute("EXECUTE MakeBook(%s,%s,%s,%s)",(self.title, self.author_id, self.description, self._description_raw))
        data=c.fetchone()
        db.commit()
        b=Book(result=data)
        return b

    def edit(self, title, description):

        if title==self.title and description==self._description_raw:
            return

        self.title=Cleaner.clean(title)
        self._description_raw=description
        self.description=Cleaner.clean(mistletoe.markdown(self._description_raw))

        c.execute("EXECUTE EditBook(%s, %s, %s, %s)", (self.title, self.description, self._description_raw, self.id))
        db.commit()
    

    def stories(self):

        c.execute("EXECUTE GetStoriesByBook(%s)",(self.id,))
        for entry in c.fetchall():
            yield Story(result=entry)

    def render_bookpage(self, v=None):
        
        return render_template('bookpage.html', b=self, v=v)

    def ban(self):

        c.execute("EXECUTE BanBook(%s, 'true')",(self.id,))
        db.commit()

    def unban(self):

        c.execute("EXECUTE BanBook(%s, 'false')",(self.id,))
        db.commit()

    def delete(self):

        c.execute("EXECUTE DeleteBook(%s, 'true')",(self.id,))
        db.commit()

    def undelete(self):

        c.execute("EXECUTE DeleteBook(%s, 'false')",(self.id,))
        db.commit()

class Pledge():

    def __init__(self, creator_id, supporter_id, make=False):
        
        self.creator_id=creator_id
        self.supporter_id=supporter_id

        c.execute("EXECUTE GetPledge(%s,%s)", (creator_id, supporter_id))

        result=c.fetchone()
        if result is None and make==True:
            c.execute("EXECUTE MakePledge(%s,%s,0)" (creator_id, supporter_id))
            result=c.fetchone()
            self.amount_cents=0
            db.commit()
        elif result is None:
            self.amount_cents=0
        else:
            self.amount_cents=int(result[3])

        
    def update_pledge(self, amount_cents):
        c.execute("EXECUTE UpdatePledge(%s,%s,%s)", (self.creator_id, self.supporter_id, amount_cents))
        db.commit()
        self.amount_cents=amount_cents
    

        
    
