import feedparser
import requests
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

    session = requests.Session()
    # 2026 SEC-FETCH STRATEGY: These headers are the "secret sauce" to bypass 403s
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.reddit.com/',
        'Origin': 'https://www.reddit.com',
        'DNT': '1',
        # These 3 headers are CRITICAL for 2026 bypass
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    })
    
    for sub in SUBREDDITS:
        # We target the most recent archive of the daily top posts
        url = f"https://web.archive.org/web/20260414/https://www.reddit.com/r/{sub}/top/.json?t=day"
        
        try:
            # Wayback doesn't block GitHub IPs!
            response = session.get(url, timeout=30)
            
            if response.status_code == 403:
                print(f"⛔ 403 Forbidden for r/{sub}. GitHub IP might be temporarily flagged.")
                continue
            
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            raw_count_in_bucket = len(posts)
            unique_count_in_bucket = 0

            for post in posts:
                # Map JSON fields back to your existing extraction variables
                entry = post.get('data', {})
                post_id = entry.get('id')
                link = entry.get('url')
                domain = entry.get('domain', 'reddit.com')
                
                # Maintain original logic for self-posts
                is_self = 1 if entry.get('is_self') else 0

                cursor.execute('''
                    INSERT OR IGNORE INTO reddit_posts 
                    (id, subreddit, author, title, url, domain, comment_count, flair, published_at, summary_html, is_self_post)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post_id, 
                    f"r/{sub}", 
                    entry.get('author', 'unknown'),
                    entry.get('title'), 
                    link, 
                    domain, 
                    entry.get('num_comments', 0), 
                    entry.get('link_flair_text', 'None'), 
                    datetime.fromtimestamp(entry.get('created_utc')).isoformat(), 
                    entry.get('selftext_html', ''), 
                    is_self
                ))
                
                if cursor.rowcount > 0:
                    unique_count_in_bucket += 1
            
            # Output Format
            print(f"📊 r/{sub} Stats: {raw_count_in_bucket} found | {unique_count_in_bucket} new unique added")

            total_raw_scraped_this_run += raw_count_in_bucket
            total_unique_new_this_run += unique_count_in_bucket

        except Exception as e:
            print(f"❌ Error in bucket {sub}: {e}")

        time.sleep(5) # Prevent IP throttling


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