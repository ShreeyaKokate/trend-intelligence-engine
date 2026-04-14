import requests
import sqlite3
import pandas as pd
import os
import time
import re
from datetime import datetime, timedelta
import argparse  

# Setup Arguments to listen to the GitHub Action
parser = argparse.ArgumentParser()
parser.add_argument("--output", help="Path to save the database", default=None) # <-- ADDED
args, unknown = parser.parse_known_args() 

# CREDENTIALS
HANDLE = os.getenv('BSKY_HANDLE')
PASSWORD = os.getenv('BSKY_APP_PASSWORD')

if not HANDLE or not PASSWORD:
    print("❌ ERROR: BSKY_HANDLE or BSKY_APP_PASSWORD not found.")
    exit(1)

# INITIALIZATION
now = datetime.now()
now_str = now.strftime('%Y-%m-%d %H:%M:%S')
time_threshold = now - timedelta(hours=24)
TARGET_UNIQUE_POSTS = 350

# Dynamic DB Path Logic
if args.output:
    db_dir = args.output
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    DB_PATH = os.path.join(db_dir, "bluesky_data.db")
else:
    # Your original local path fallback
    DB_PATH = "database/bluesky_data.db"
    if not os.path.exists('database'): 
        os.makedirs('database')

print("\n" + "="*40)
print(f"BLUESKY AI-FLYWHEEL ENGINE : {now_str}")

keywords = [
    "AI", "Artificial Intelligence", "LLM", "Large Language Model",
    "Small Language Model", "Transformer", "Deep Learning", "Neural Network",
    "NLP", "Natural Language Processing", "Computer Vision", "CV",
    "Generative Models", "Diffusion Models", "AI Ethics", "AI Safety",
    "Reinforcement Learning", "Supervised Learning", "Unsupervised Learning", "RL",
    "AI Agents", "AI Inference", "Model Training", "Fine-tuning", "Prompt Engineering",
    "ChatGPT", "Gemini", "Bard", "GPT-4", "Claude",
    "Llama 3", "Mistral", "Ollama", "HuggingFace", 
    "Stable Diffusion", "ComfyUI", "Generative AI", "GenAI",
    "Machine Learning", "ML", "RAG", "Local LLM", "Agentic AI", 
    "OpenAI", "PyTorch", "LangChain", "DeepSeek", 
]
keyword_stats = {k: {"found": 0} for k in keywords}

# AUTHENTICATION
session = requests.Session()
try:
    auth_resp = session.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": HANDLE, "password": PASSWORD}
    )
    auth_resp.raise_for_status()
    access_jwt = auth_resp.json().get('accessJwt')
    session.headers.update({"Authorization": f"Bearer {access_jwt}"})
    print("🔑 Auth: SUCCESS")
except Exception as e:
    print(f"❌ Auth: FAILED - {e}")
    exit(1)

# EXTRACTION
all_processed_posts = []
unique_ids = set()

def extract_emojis(text):
    return "".join(re.findall(r'[^\w\s,.]', text)) # regex for non-alphanumeric

for kw in keywords:
    search_query = f'"{kw}" lang:en' if " " in kw else f'{kw} lang:en'
    
    try:
        # Pulling 100 per keyword to try and hit that 350 target
        params = {"q": search_query, "limit": 100}
        resp = session.get("https://bsky.social/xrpc/app.bsky.feed.searchPosts", params=params)
        resp.raise_for_status()
        posts = resp.json().get('posts', [])
        
        for p in posts:
            record = p.get('record', {})
            author = p.get('author', {})
            uri = p.get('uri')
            
            # Engagement counts
            likes = p.get('likeCount', 0)
            reposts = p.get('repostCount', 0)
            replies = p.get('replyCount', 0)
            
            # FILTERS: Quality check 
            if likes > 5:
                try:
                    clean_date = record.get('createdAt', '').split('.')[0].replace('Z', '')
                    post_time = datetime.fromisoformat(clean_date)
                    
                    if post_time >= time_threshold:
                        if uri not in unique_ids:
                            # Image handling
                            embed = p.get('embed', {})
                            images = []
                            if embed.get('$type') == 'app.bsky.embed.images#view':
                                images = [img.get('fullsize') for img in embed.get('images', [])]
                            
                            unique_ids.add(uri)
                            keyword_stats[kw]["found"] += 1
                            
                            all_processed_posts.append({
                                'post_id': uri,
                                'post_timestamp': record.get('createdAt'),
                                'post_text': record.get('text', ''),
                                'post_likes': likes,
                                'post_reposts': reposts,
                                'post_comments': replies,
                                'post_emojis': extract_emojis(record.get('text', '')),
                                'post_url': f"https://bsky.app/profile/{author.get('handle')}/post/{uri.split('/')[-1]}",
                                'post_image_links': ",".join(images) if images else None,
                                'author_handle': author.get('handle'),
                                'author_name': author.get('displayName'),
                                'author_is_verified': 1 if author.get('viewer', {}).get('muted') == False else 0, # Rough proxy
                                'author_description': author.get('description', ''),
                                'author_followers_count': author.get('followersCount', 0),
                                'author_follows_count': author.get('followsCount', 0),
                                'scraped_at': now_str
                            })
                except: continue
        time.sleep(0.5)
    except Exception as e:
        print(f"⚠️ Error with '{kw}': {e}")

# DATABASE SYNC
if not os.path.exists('database'): os.makedirs('database')
conn = sqlite3.connect(DB_PATH)
cursor_db = conn.cursor()

# Table Schema
cursor_db.execute("""
    CREATE TABLE IF NOT EXISTS bluesky_posts (
        post_id TEXT PRIMARY KEY,
        post_timestamp TEXT,
        post_text TEXT,
        post_likes INTEGER,
        post_reposts INTEGER,
        post_comments INTEGER,
        post_emojis TEXT,
        post_url TEXT,
        post_image_links TEXT,
        author_handle TEXT,
        author_name TEXT,
        author_is_verified INTEGER,
        author_description TEXT,
        author_followers_count INTEGER,
        author_follows_count INTEGER,
        scraped_at TEXT
    )
""")
initial_count = cursor_db.execute("SELECT COUNT(*) FROM bluesky_posts").fetchone()[0]

if all_processed_posts:
    df = pd.DataFrame(all_processed_posts)
    df.to_sql("temp_bs", conn, if_exists="replace", index=False)
    conn.execute("INSERT OR IGNORE INTO bluesky_posts SELECT * FROM temp_bs")
    conn.execute("DROP TABLE temp_bs")
    conn.commit()

final_count = cursor_db.execute("SELECT COUNT(*) FROM bluesky_posts").fetchone()[0]
unique_added = final_count - initial_count
conn.close()

# SUMMARY
for kw in keywords:
    print(f"📊 {kw} Stats: {keyword_stats[kw]['found']} found")

print(f"✅ Bluesky Summary")
print(f"Total Unique Scraped: {len(all_processed_posts)}")
print(f"Unique Added to DB:   {unique_added}")
print(f"Total bluesky posts in database now:  {final_count}")
print("-" * 40)