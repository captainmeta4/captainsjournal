from logbook import server


#close db connections
server.classes.c.close()
server.classes.db.close()
