import feedparser
import sqlite3
import os
import time
import re
from datetime import datetime, timedelta
import argparse  

# Setup Arguments to listen to the GitHub Action
parser = argparse.ArgumentParser()
parser.add_argument("--output", help="Path to save the database", default=None) 
args, unknown = parser.parse_known_args()

# Targeted high-signal AI subreddits
SUBREDDITS = [
    "artificial", "MachineLearning", 
    "AI_Agents", "ArtificialInteligence",
    "LocalLlama", "singularity",
    "OpenAI", "ChatGPT", "ClaudeAI", "computervision", 
    "dataisbeautiful", "VibeCoding", "ClaudeCode", "PromptEngineering",
    "DeepLearning", "Build_AI_Agents", "AI_Art", "AIAgentsInAction", "AINewsMinute",
]

# Dynamic DB Path Logic
base_dir = os.path.dirname(os.path.abspath(__file__))

if args.output:
    db_dir = args.output
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    DB_PATH = os.path.join(db_dir, 'reddit_data.db')
else:
    # Your original local path fallback
    DB_PATH = os.path.join(base_dir, '..', 'database/reddit_data.db')
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reddit_posts (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            author TEXT,
            title TEXT,
            url TEXT,
            domain TEXT,
            comment_count INTEGER,
            flair TEXT,
            published_at TEXT,
            summary_html TEXT,
            is_self_post INTEGER
        )
    ''')
    conn.commit()
    return conn

def scrape_reddit():
    # Today's Date
    print("\n" + "="*40)
    print(f"Reddit Scraping Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    total_raw_scraped_this_run = 0
    total_unique_new_this_run = 0

    conn = init_db()
    cursor = conn.cursor()
    
    for sub in SUBREDDITS:
        # Fetching Top 100 of the day for max volume/quality
        rss_url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day&limit=100"
        
        # User-Agent is strictly required to avoid 429 "Too Many Requests"
        feed = feedparser.parse(rss_url, agent='AI_Trend_Flywheel')

        raw_count_in_bucket = len(feed.entries)
        unique_count_in_bucket = 0
        
        for entry in feed.entries:
            # Unique ID
            post_id = entry.id.split('_')[-1] if '_' in entry.id else entry.id
            
            # Extract domain of the url
            link = entry.link
            domain = link.split('//')[-1].split('/')[0] if '//' in link else "reddit.com"

            # Comment Count (Uses the slash:comments XML tag)
            comments = int(entry.get('slash_comments', 0))

            # Flair Extraction
            flair = "None"
            if 'tags' in entry and len(entry.tags) > 0:
                flair = entry.tags[0].term

            # Determine if it's a Text Post or a Link
            is_self = 1 if "/comments/" in link and domain == "www.reddit.com" else 0

            cursor.execute('''
                INSERT OR IGNORE INTO reddit_posts 
                (id, subreddit, author, title, url, domain, comment_count, flair, published_at, summary_html, is_self_post)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_id, f"r/{sub}", entry.author if 'author' in entry else 'unknown',
                entry.title, link, domain, comments, flair, entry.published, entry.summary, is_self
            ))
            
            if cursor.rowcount > 0:
                unique_count_in_bucket += 1
        
        # Output Format
        print(f"📊 r/{sub} Stats: {raw_count_in_bucket} found | {unique_count_in_bucket} new unique added")

        total_raw_scraped_this_run += raw_count_in_bucket
        total_unique_new_this_run += unique_count_in_bucket
        time.sleep(2) # Prevent IP throttling
    
    # Get total count in DB till date
    cursor.execute("SELECT COUNT(*) FROM reddit_posts")
    total_db_count = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    # Final Summary
    print(f"✅ Reddit Summary")
    print(f"Total posts processed from RSS: {total_raw_scraped_this_run}")
    print(f"Total new unique posts saved:   {total_unique_new_this_run}")
    print(f"Total reddit posts in database now:    {total_db_count}")

if __name__ == "__main__":
    scrape_reddit()