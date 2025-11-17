# AutoBlog 24/7 (Starter)

This project is a production-ready starter that automates daily content discovery and post generation with a scheduler, database, and a simple control panel.

What you get now:
- FastAPI backend with MongoDB integration
- Config model (niches, language, countries, posts/day, pause/resume)
- Trend aggregation stubs (Google Trends/News/Reddit placeholders)
- Article generation stub (structured SEO HTML + FAQ schema)
- APScheduler hourly tick to spread posts across the day
- REST endpoints to configure, generate, and list posts
- React dashboard to view posts and control automation

Bring your own keys to enable advanced features:
- LLM generation (OpenAI, Anthropic, etc.)
- Media generation (DALL·E, Stability, etc.)
- Platform publishing (WordPress, Medium, Ghost, Blogger, Hashnode)
- Social sharing, indexing pings, email notifications

## Quick Start

1) Environment
Create `.env` files or set environment variables for the backend:

```
DATABASE_URL=mongodb://...
DATABASE_NAME=autoblog
OPENAI_API_KEY=...
# Optional: publishers
WORDPRESS_URL=https://your-site.com
WORDPRESS_USER=youruser
WORDPRESS_APP_PASS=abcd xyz...
MEDIUM_TOKEN=...
GHOST_ADMIN_API_URL=https://your-ghost.com
GHOST_ADMIN_API_KEY=...
```

Frontend expects:
```
VITE_BACKEND_URL=https://<backend-url>
```

2) Run
- Use the provided dev environment (servers auto start) or run locally with uvicorn and Vite.

3) Use
- Open the frontend URL. Set posts/day and pause/resume.
- Click Generate Now to create a post immediately.

## API
- GET /config – fetch current automation config
- POST /config – update full config
- POST /schedule – update posts_per_day or paused
- POST /generate – trigger generation now
- GET /posts – list recent posts

## Extend to Full Requirements

This starter is structured to add the rest quickly:

- Trend sources: implement real fetchers using APIs (Google Trends via pytrends, Reddit API, Twitter/X API, YouTube Trends, News API). Merge into `aggregate_trending_topics` with de-duplication.
- Long-form SEO content: replace `generate_article` body with calls to your LLM provider and a post-processor that injects title, meta, ToC, headings (H1/H2/H3), internal/external links, alt text, FAQ schema, and JSON-LD.
- Media: call DALL·E/Stability for 8–15 images and attach URLs + captions to the Post.media array. For videos, store embed links.
- Publishers: add functions to publish to WordPress, Medium, and Ghost via their REST APIs and persist external URLs in the post document.
- Scheduling: switch to a queue where posts are generated first, then scheduled evenly throughout the day based on `posts_per_day`.
- Safety: add YMYL filters, rate-limiting wrappers, retries with backoff, and fact-checking via Tavily/Perplexity.
- Social + Indexing: add webhook tasks to push links to X/LinkedIn/etc. and Search Console/Bing APIs after publish.

This repo provides the data model, endpoints, scheduler, and dashboard needed to wire those features with minimal friction.
