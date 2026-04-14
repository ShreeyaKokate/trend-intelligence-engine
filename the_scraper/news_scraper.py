import os
import sqlite3
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from newsapi import NewsApiClient

# Setup environment
base_dir = os.path.dirname(os.path.abspath(__file__))
# Adjusted path to ensure it finds the .env in the root
env_path = os.path.join(base_dir, '..', '.env')
load_dotenv(dotenv_path=env_path)

newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))

def get_db_connection():
    # Ensuring the DB is in the root directory relative to this script
    db_path = os.path.join(base_dir, '..', 'database/news_articles.db')
    return sqlite3.connect(db_path)

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            source_name TEXT,
            author TEXT,
            title TEXT,
            description TEXT,
            url TEXT UNIQUE,
            url_to_image TEXT,
            published_at TEXT,
            content TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.close()

def run_perfect_extractor():
    init_db()

    # Today's Date
    print("\n" + "="*40)
    print(f"NEWS ARTICLES SCRAPER: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Bucket Strategy to bypass 100-result limit
    queries = [
        '"Artificial Intelligence" OR "AI"',
        '"Machine Learning" OR "Deep Learning"',
        '"LLM" OR "Large Language Models"',
        '"Neural Networks" OR "Computer Vision" OR "NLP"'
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()

    total_raw_scraped_this_run = 0  # Every article returned by API
    total_unique_new_this_run = 0   # Only those successfully inserted (INSERT OR IGNORE)
    unique_count_in_bucket = 0
    
    # 3-day window for safety
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

    for q_string in queries:
        try:
            response = newsapi.get_everything(
                q=q_string,
                from_param=start_date, 
                language='en',
                sort_by='publishedAt',
                page_size=100,
                page=1 
            )
            
            articles = response.get('articles', [])
            raw_count_in_bucket = len(articles)
            unique_count_in_bucket = 0 # Reset for every bucket
            
            for art in articles:
                src = art.get('source', {})
                
                cursor.execute('''
                    INSERT OR IGNORE INTO ai_news (
                        source_id, source_name, author, title, 
                        description, url, url_to_image, published_at, content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    src.get('id'),
                    src.get('name'),
                    art.get('author'),
                    art.get('title'),
                    art.get('description'),
                    art.get('url'),
                    art.get('urlToImage'),
                    art.get('publishedAt'),
                    art.get('content')
                ))
                
                if cursor.rowcount > 0:
                    unique_count_in_bucket += 1
            
            # Output Format
            print(f"📊 {q_string} Stats: {raw_count_in_bucket} found | {unique_count_in_bucket} new unique added")
            total_raw_scraped_this_run += raw_count_in_bucket
            total_unique_new_this_run += unique_count_in_bucket

            time.sleep(1) # Be nice to the API

        except Exception as e:
            print(f"❌ Error in bucket {q_string}: {e}")

    # Get count for the log
    cursor = conn.execute("SELECT COUNT(*) FROM ai_news")
    total_db_count = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    # Final Summary
    print(f"✅ Articles Summary")
    print(f"Total articles processed from API: {total_raw_scraped_this_run}")
    print(f"Total new unique articles saved:   {total_unique_new_this_run}")
    print(f"Total articles in database now:    {total_db_count}")

if __name__ == "__main__":
    run_perfect_extractor()