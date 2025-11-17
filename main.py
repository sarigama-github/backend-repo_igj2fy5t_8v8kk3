import os
import re
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import db, create_document, get_documents
from schemas import Post, BlogConfig

app = FastAPI(title="AutoBlog API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Helpers / Env -----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

WORDPRESS_URL = os.getenv("WORDPRESS_URL")
WORDPRESS_USER = os.getenv("WORDPRESS_USER")
WORDPRESS_APP_PASS = os.getenv("WORDPRESS_APP_PASS")

MEDIUM_TOKEN = os.getenv("MEDIUM_TOKEN")
GHOST_ADMIN_API_URL = os.getenv("GHOST_ADMIN_API_URL")
GHOST_ADMIN_API_KEY = os.getenv("GHOST_ADMIN_API_KEY")

scheduler: Optional[AsyncIOScheduler] = None

# ----------- Networking helper -----------
async def fetch_json(client: httpx.AsyncClient, url: str, headers: dict = None, params: dict = None):
    for i in range(3):
        try:
            r = await client.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == 2:
                raise
            await asyncio.sleep(2 * (i + 1))

# ----------- Content Generation (demo) -----------
async def generate_article(topic: str, language: str = "en") -> dict:
    # In production, call your LLM provider here and post-process for SEO.
    title = f"{topic}: What You Need to Know Right Now"
    meta = f"Deep dive into {topic} with context, key takeaways, and FAQs."
    body = f"""
    <article>
      <h1>{title}</h1>
      <p><em>{meta}</em></p>
      <nav aria-label=\"Table of contents\">
        <ol>
          <li><a href=\"#overview\">Overview</a></li>
          <li><a href=\"#key-points\">Key Points</a></li>
          <li><a href=\"#faq\">FAQ</a></li>
        </ol>
      </nav>
      <h2 id=\"overview\">Overview</h2>
      <p>This starter generates structured, SEO-friendly HTML. Connect your LLM API keys to enable long-form generation.</p>
      <h2 id=\"key-points\">Key Points</h2>
      <ul>
        <li>Trend background and current status</li>
        <li>Opportunities and risks</li>
        <li>Useful resources</li>
      </ul>
      <h2 id=\"faq\">FAQ</h2>
      <h3>What is {topic}?</h3>
      <p>High-level explanation to help readers get oriented.</p>
      <h3>Why does {topic} matter now?</h3>
      <p>Context on impact and timing.</p>
      <h3>Where can I learn more?</h3>
      <p>Official docs, reputable sources, and communities.</p>
      <script type=\"application/ld+json\">{json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
          {"@type": "Question", "name": f"What is {topic}?", "acceptedAnswer": {"@type": "Answer", "text": "Explanation."}},
          {"@type": "Question", "name": f"Why does {topic} matter now?", "acceptedAnswer": {"@type": "Answer", "text": "Context."}}
        ]
      })}</script>
    </article>
    """
    keywords = [topic]
    return {
        "title": title,
        "meta": meta,
        "content_html": body,
        "keywords": keywords,
    }

# ----------- Trend aggregation (demo) -----------
async def get_google_trends(country: str = "US") -> List[str]:
    return ["AI breakthroughs", "Tech layoffs", "Electric vehicles"]

async def get_reddit_trends() -> List[str]:
    return ["AskReddit life hacks", "New chip release"]

async def get_news_trends(country: str = "US") -> List[str]:
    return ["Stock market today", "Climate action updates"]

async def aggregate_trending_topics(countries: List[str]) -> List[str]:
    topics: List[str] = []
    for c in countries:
        topics += await get_google_trends(c)
        topics += await get_news_trends(c)
    topics += await get_reddit_trends()
    uniq: List[str] = []
    seen = set()
    for t in topics:
        s = re.sub(r"\s+", " ", t).strip()
        k = s.lower()
        if s and k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq[:20]

# ----------- Models -----------
class GenerateRequest(BaseModel):
    topics: Optional[List[str]] = None
    count: Optional[int] = Field(None, ge=1, le=10)

class ScheduleRequest(BaseModel):
    posts_per_day: Optional[int] = Field(None, ge=1, le=10)
    paused: Optional[bool] = None

# ----------- Core Ops -----------
async def make_posts(desired: int, cfg: BlogConfig) -> List[str]:
    topics = await aggregate_trending_topics(cfg.country_codes)
    to_make = min(desired, len(topics))
    made: List[str] = []
    async with httpx.AsyncClient() as _:
        for topic in topics[:to_make]:
            art = await generate_article(topic, cfg.language)
            post = Post(
                topic=topic,
                title=art["title"],
                meta_description=art["meta"],
                keywords=art["keywords"],
                language=cfg.language,
                content_html=art["content_html"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            pid = create_document("post", post)
            made.append(pid)
    # update last_run
    if db:
        db["blogconfig"].update_one({}, {"$set": {"last_run_at": datetime.now(timezone.utc)}})
    return made

async def scheduler_tick():
    if not db:
        return
    cfg_doc = db["blogconfig"].find_one() or BlogConfig().model_dump()
    cfg = BlogConfig(**{k: v for k, v in cfg_doc.items() if k != "_id"})
    if cfg.paused:
        return
    # Spread posts across the day. Run hourly and aim for posts_per_day/24 per tick.
    target_today = cfg.posts_per_day
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    made_today = db["post"].count_documents({"created_at": {"$gte": start_of_day}})
    remaining = max(0, target_today - made_today)
    if remaining == 0:
        return
    # Simple strategy: make one post per tick until target reached
    await make_posts(1, cfg)

# ----------- Startup / Shutdown -----------
@app.on_event("startup")
async def on_startup():
    global scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(scheduler_tick()), "interval", minutes=60, id="hourly_tick", replace_existing=True)
    scheduler.start()

@app.on_event("shutdown")
async def on_shutdown():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)

# ----------- Routes -----------
@app.get("/")
def root():
    return {"service": "AutoBlog API", "ok": True}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response

@app.get("/schema")
def get_schema():
    return {"models": ["BlogConfig", "Post"]}

@app.get("/config")
def get_config():
    doc = db["blogconfig"].find_one() if db else None
    if not doc:
        cfg = BlogConfig().model_dump()
        if db:
            db["blogconfig"].insert_one(cfg)
        return cfg
    doc["_id"] = str(doc["_id"])  # jsonify
    return doc

@app.post("/config")
def update_config(cfg: BlogConfig):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    cfg.last_run_at = datetime.now(timezone.utc)
    db["blogconfig"].update_one({}, {"$set": cfg.model_dump()}, upsert=True)
    return {"ok": True}

@app.post("/generate")
async def generate_posts(req: GenerateRequest):
    cfg_doc = get_config()
    cfg = BlogConfig(**{k: v for k, v in cfg_doc.items() if k != "_id"})
    desired = req.count or cfg.posts_per_day
    made = await make_posts(desired, cfg)
    return {"created": made}

@app.get("/posts")
def list_posts(limit: int = 50):
    docs = get_documents("post", {}, limit)
    for d in docs:
        d["_id"] = str(d["_id"])  # jsonify
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
    return docs

@app.post("/schedule")
def schedule(req: ScheduleRequest):
    current = get_config()
    if req.posts_per_day is not None:
        current["posts_per_day"] = req.posts_per_day
    if req.paused is not None:
        current["paused"] = req.paused
    if db:
        db["blogconfig"].update_one({}, {"$set": current}, upsert=True)
    return {"ok": True, "config": current}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
