import psycopg2
import os

conn=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=conn.cursor()

class User():

    def __init__(self, name):

        #check database
        s="SELECT * FROM Users WHERE reddit_name=@0"
        c.execute(s, name)
        result=c.fetchone()

        if result is None:
            raise KeyError('that user does not exist')

        self.name=name
        self.id=str(result[0])
        self.created=str(result[2])
        self.banned=bool(result[3])
