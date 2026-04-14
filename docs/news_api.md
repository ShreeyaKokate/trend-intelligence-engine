# News API Data Scraper

An automated, high-volume news ingestion pipeline designed to build a massive dataset of Artificial Intelligence and Machine Learning developments. This project uses **GitHub Actions** for scheduling, **NewsAPI** for data sourcing, and **SQLite** for deduplicated persistent storage.

---

## 🎯 The 10,000 Article Strategy
To achieve a target of **10,000 unique articles per month**, the scraper is calibrated with the following logic:

| Frequency | Daily Target | Monthly Total | Logic |
| :--- | :--- | :--- | :--- |
| **Every 24 Hours** | **~335 - 350** | **~10,500** | Uses a sliding window to capture all new AI/ML hits. |

### **Overcoming API Limits**
NewsAPI restricts individual requests to 100 results. To hit our 350+ daily target, the script:
1.  **Paginate:** Iterates through pages 1–5 of the `everything` endpoint.
2.  **Overlap:** Scans the last **3 days** of news in every run to ensure no gaps.
3.  **Deduplicate:** Uses a `UNIQUE` constraint on the `url` column with `INSERT OR IGNORE` to ensure only brand-new stories are saved.

---

## 🛠️ Data Schema & Metadata
The database captures the full metadata object provided by the NewsAPI `everything` endpoint.

| Field | Type | Description |
| :--- | :--- | :--- |
| `source_name` | TEXT | Publication name (e.g., Wired, TechCrunch). |
| `author` | TEXT | Primary writer of the article. |
| `title` | TEXT | Headline (Main search index). |
| `description` | TEXT | Short summary provided by the source. |
| `url` | TEXT (Unique) | Primary key for deduplication. |
| `url_to_image` | TEXT | Link to the article's hero image. |
| `published_at` | TEXT | ISO 8601 timestamp of publication. |
| `content` | TEXT | **Snippet Only:** The first 200 characters (API limit). |
| `ingested_at` | TIMESTAMP | Internal tracking of when data was added. |

---

## ⚠️ Important API Constraints
* **Truncated Content:** The `content` field contains only a **200-character snippet**. This is the standard delivery for the NewsAPI "Everything" endpoint.
* **Search Scope:** The query targets `"Artificial Intelligence"`, `"Machine Learning"`, `"LLM"`, and related neural network terminology.
* **Lookback Limit:** The script is optimized for the **30-day window** available on Developer/Basic API plans.

---

## 🚀 Setup & Automation

### **Environment Variables**
Ensure your `.env` file (or GitHub Secret) contains:

NEWSAPI_KEY=your_alphanumeric_key_here

### **GitHub Action Configuration**
The scraper is triggered daily via your workflow file (e.g., .github/workflows/daily_scrape.yml).

* Schedule: 0 0 * * * (Midnight UTC)
* Storage: The ai_news_storage.db file is updated and committed back to the repository to maintain state.

---

## 📈 Future Roadmap
Full-Text Extraction: Visit the url and extract 100% of the article body