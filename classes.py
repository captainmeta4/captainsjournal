import psycopg2
import os
import re
from Flask import *

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

#clear any aborted transactions from previous iteration (debugging)
c.execute("ROLLBACK TRANSACTION")

#prepare parameterized sql statements
c.execute("PREPARE GetUser(name) AS SELECT * FROM Users WHERE reddit_name = $1")
c.execute("PREPARE MakeUser(name) AS INSERT INTO Users (reddit_name, created_utc, banned, posts, comments, google_analytics) VALUES ($1,'NOW','false','','','')")

class User():

    def __init__(self, name, make=False):

        #sanitize name
        name=re.search("^[A-Za-z0-9_-]+", name).group(0)

        #check database
        c.execute("EXECUTE GetUser('{}')".format(name))
        result=c.fetchone()

        if result is None and make:
            c.execute("EXECUTE MakeUser('{}')".format(name))
            c.execute("EXECUTE GetUser('{}')".format(name))
            result=c.fetchone()
        elif result is None:
            return None

        self.name=name
        self.id=str(result[0])
        self.created=str(result[2])
        self.banned=bool(result[3])

    def render_userpage(self):

        return render_template('userpage.html', u=self)
