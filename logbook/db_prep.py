import psycopg2
import os

db=psycopg2.connect(os.environ.get("DATABASE_URL"))
c=db.cursor()

#prepare parameterized sql statements
#for users
c.execute("PREPARE MakeUser(text) AS INSERT INTO Users (reddit_name, created_utc, google_analytics) VALUES ($1,'NOW','') RETURNING *")
c.execute("PREPARE GetUserByName(text) AS SELECT * FROM Users WHERE UPPER(reddit_name) = UPPER($1)")
c.execute("PREPARE GetUserByID(int) AS SELECT * FROM Users WHERE id = $1")
c.execute("PREPARE BanUser(int, boolean) AS UPDATE Users SET banned=$2 WHERE id=$1")
c.execute("PREPARE GetUserByToken(text) AS SELECT * FROM Users WHERE token=$1")
c.execute("PREPARE UpdateToken(int, text) AS UPDATE Users SET token=$2 WHERE id=$1")
c.execute("PREPARE SetPatreon(int, int, text, text, text, int) AS UPDATE Users SET patreon_id=$2, patreon=$3, patreon_token=$4, patreon_refresh_token=$5, patreon_campaign_id=$6 WHERE id=$1")
c.execute("PREPARE SetGoogle(int, text) AS UPDATE Users SET google_analytics=$2 WHERE id=$1")
c.execute("PREPARE SetOver18(int, boolean) AS UPDATE Users SET over_18=$2 WHERE id=$1")
c.execute("PREPARE SetPatreonTokens(int, text,text) AS UPDATE Users SET patreon_token=$2, patreon_refresh_token=$3 WHERE id=$1")

#for stories
c.execute("PREPARE MakeStory(int, text, text, text, text, text, text, text, int) AS INSERT INTO Stories (author_id, created, title, pre, story, post, pre_raw, story_raw, post_raw, book_id) VALUES ($1,'NOW', $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *")
c.execute("PREPARE EditStory(int, text, text, text, text, text, text, text) AS UPDATE Stories SET pre=$2, story=$3, post=$4, pre_raw=$5, story_raw=$6, post_raw=$7, title=$8, edited='NOW' WHERE id=$1")
c.execute("PREPARE GetStoryById(int) AS SELECT * FROM Stories WHERE id = $1")
c.execute("PREPARE GetStoriesByAuthorId(int) AS SELECT * FROM Stories WHERE author_id = $1 ORDER BY id DESC")
c.execute("PREPARE BanStory(int, boolean) AS UPDATE Stories SET banned=$2 WHERE id=$1")
c.execute("PREPARE DeleteStory(int, boolean) AS UPDATE Stories SET deleted=$2 WHERE id=$1")
c.execute("PREPARE GetStoriesByBook(int) AS SELECT * FROM Stories WHERE book_id=$1")
c.execute("PREPARE SetNSFW(int, boolean) AS UPDATE Stories SET nsfw=$2 WHERE id=$1")
c.execute("PREPARE SetPatreonThreshold(int,int) AS UPDATE Stories SET patreon_threshold=$2 WHERE id=$1")
c.execute("PREPARE SetReddit(int, text, text) AS UPDATE Stories SET reddit=$2, subreddit=$3 WHERE id=$1") 

#for books
c.execute("PREPARE MakeBook(text, int, text, text) AS INSERT INTO Books (name, author_id, description, description_raw, timestamp) VALUES ($1, $2, $3, $4, 'NOW') RETURNING *")
c.execute("PREPARE GetBookById(int) AS SELECT * FROM Books WHERE id=$1")
c.execute("PREPARE GetBooksByAuthorId(int) AS SELECT * FROM Books WHERE author_id=$1")
c.execute("PREPARE EditBook(text, text, text, int) AS UPDATE Books SET name=$1, description=$2, description_raw=$3, edited='NOW' WHERE id=$4")
c.execute("PREPARE BanBook(int, boolean) AS UPDATE Books SET banned=$2 WHERE id=$1")
c.execute("PREPARE DeleteBook(int, boolean) AS UPDATE Books SET deleted=$2 WHERE id=$1")
