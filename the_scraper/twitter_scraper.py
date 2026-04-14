import asyncio
import sqlite3
import pandas as pd
import os
import json
from Scweet import Scweet
from datetime import datetime, timedelta
import argparse  

# Setup Arguments to listen to the GitHub Action
parser = argparse.ArgumentParser()
parser.add_argument("--output", help="Path to save the database", default=None) 
args, unknown = parser.parse_known_args() 

async def run_ai_flywheel():

    COOKIE_PATH = "twitter_setup/cookies.json"
    COOKIE_DIR = "twitter_setup"

    # Dynamic DB Path Logic 
    if args.output:
        db_dir = args.output
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        DB_PATH = os.path.join(db_dir, "twitter_data.db")
    else:
        # Your original local path fallback
        if not os.path.exists('database'): os.makedirs('database')
        DB_PATH = "database/twitter_data.db"

    # PROVISIONING 
    if os.getenv('TWITTER_AUTH_TOKEN'):
        if not os.path.exists(COOKIE_DIR): os.makedirs(COOKIE_DIR)
        def sanitize(val):
            return val.strip().replace('"', '').replace("'", "") if val else ""
        auth = sanitize(os.getenv('TWITTER_AUTH_TOKEN'))
        ct0 = sanitize(os.getenv('TWITTER_CT0'))
        user = sanitize(os.getenv('TWITTER_USERNAME'))
        action_cookies = [{"username": user, "cookies": {"auth_token": auth, "ct0": ct0}}]
        with open(COOKIE_PATH, "w") as f:
            json.dump(action_cookies, f)

    # INITIALIZATION
    if os.path.exists('scweet_state.db'):
        os.remove('scweet_state.db')

    s = Scweet(cookies_file=COOKIE_PATH)

    # SEARCH EXECUTION
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Today's Date
    now = datetime.now()
    print("\n" + "="*40)
    print(f"TWITTER SCRAPER: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # SEARCH CALL
    keywords = ["LLM", "AI", "Artificial Intelligence", "Agentic AI", "GenAI"]
    query = f"(({' OR '.join(keywords)}) min_faves:100 lang:en)"
    tweets = await s.asearch(
        query,
        since=yesterday, 
        limit=500,
        min_likes=100,
        lang="en" 
    )
    
    # Tracking dictionaries for individual categories
    total_raw_scraped_this_run = len(tweets) if tweets else 0
    # Dictionary to track counts per category
    keyword_stats = {k: {"found": 0} for k in keywords}

    if tweets:
        processed_data = []
        for t in tweets:
            text = t.get('text', '')
            
            # Count category occurrences in the raw results
            for k in keywords:
                if k in text:
                    keyword_stats[k]["found"] += 1

            u = t.get('user', {})
            raw_tweet = t.get('raw', {})
            author_core = raw_tweet.get('core', {}).get('user_results', {}).get('result', {}).get('core', {})

            processed_data.append({
                'tweet_id': str(t.get('tweet_id')),
                'tweet_timestamp': t.get('timestamp'),
                'tweet_text': text,
                'tweet_likes': t.get('likes', 0),
                'tweet_retweets': t.get('retweets', 0),
                'tweet_comments': t.get('comments', 0),
                'tweet_views': raw_tweet.get('views', {}).get('count', 0),
                'tweet_bookmarks': raw_tweet.get('legacy', {}).get('bookmark_count', 0),
                'tweet_emojis': ",".join(t.get('emojis', [])) if t.get('emojis') else None,
                'tweet_url': t.get('tweet_url'),
                'tweet_image_links': ",".join(t.get('media', {}).get('image_links', [])),

                'author_screen_name': u.get('screen_name'),
                'author_name': u.get('name'),
                'author_is_blue_verified': raw_tweet.get('core', {}).get('user_results', {}).get('result', {}).get('is_blue_verified', False),
                'author_description': raw_tweet.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {}).get('description', u.get('profile_bio', {}).get('description')),
                'author_followers_count': raw_tweet.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {}).get('followers_count', u.get('followers_count', 0)),
                'author_friends_count': raw_tweet.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {}).get('friends_count', u.get('friends_count', 0)),
                'author_acc_creation_date': author_core.get('created_at'),
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

        # SAVE
        conn = sqlite3.connect(DB_PATH)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                tweet_id TEXT PRIMARY KEY,
                tweet_timestamp TEXT,
                tweet_text TEXT,
                tweet_likes INTEGER,
                tweet_retweets INTEGER,
                tweet_comments INTEGER,
                tweet_views INTEGER,
                tweet_bookmarks INTEGER,
                tweet_emojis TEXT,
                tweet_url TEXT,
                tweet_image_links TEXT,
                author_screen_name TEXT,
                author_name TEXT,
                author_is_blue_verified BOOLEAN,
                author_description TEXT,
                author_followers_count INTEGER,
                author_friends_count INTEGER,
                author_acc_creation_date TEXT,
                scraped_at TEXT
            )
        """)

        cursor = conn.cursor()
        initial_count = cursor.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]

        df = pd.DataFrame(processed_data)
        df.to_sql("temp_tweets", conn, if_exists="replace", index=False)

        conn.execute("""
            INSERT OR IGNORE INTO tweets 
            SELECT * FROM temp_tweets
        """)
        conn.execute("DROP TABLE temp_tweets")

        final_count = cursor.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
        unique_scraped_count = final_count - initial_count

        conn.commit()
        conn.close()

        # Print per-category stats
        for k in keywords:
            print(f"📊 {k} Stats: {keyword_stats[k]['found']} found")

        # Final Print Summary
        print(f"✅ Tweets Summary")
        print(f"Total scraped from this run:  {total_raw_scraped_this_run}")
        print(f"Total unique added this run: {unique_scraped_count}")
        print(f"Total unique tweets in DB:   {final_count}")

    else:
        print("No tweets found. Double-check your cookies.json content.")

if __name__ == "__main__":
    asyncio.run(run_ai_flywheel())