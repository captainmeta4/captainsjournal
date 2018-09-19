import psycopg2
import os

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

#prepare parameterized sql statements
c.execute("PREPARE GetUser(name) AS SELECT * FROM Users WHERE reddit_name=$1")

class User():

    def __init__(self, name):

        #check database
        c.execute("EXECUTE GetUser({})".format(name))
        result=c.fetchone()

        if result is None:
            raise KeyError('that user does not exist')

        self.name=name
        self.id=str(result[0])
        self.created=str(result[2])
        self.banned=bool(result[3])
