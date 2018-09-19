import psycopg2
import os
import re

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

#clear any aborted transactions from previous iteration (debugging)
c.execute("ROLLBACK TRANSACTION")

#prepare parameterized sql statements
c.execute("PREPARE GetUser(name) AS SELECT * FROM Users WHERE reddit_name=$1")

class User():

    def __init__(self, name):

        #sanitize name
        name=re.search("^[A-Za-z_-]+", name).group(0)

        #check database
        c.execute("EXECUTE GetUser({})".format(name))
        result=c.fetchone()

        if result is None:
            raise KeyError('that user does not exist')

        self.name=name
        self.id=str(result[0])
        self.created=str(result[2])
        self.banned=bool(result[3])
