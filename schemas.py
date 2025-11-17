"""
Database Schemas

Define MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class BlogConfig(BaseModel):
    """
    Global configuration for automation
    Collection: "blogconfig"
    """
    niches: List[str] = Field(default_factory=lambda: ["technology"], description="Target niches/keywords")
    language: str = Field("en", description="Language code, e.g., en, es")
    country_codes: List[str] = Field(default_factory=lambda: ["US"], description="Country codes for trends")
    posts_per_day: int = Field(3, ge=1, le=10)
    publish_targets: List[Literal["wordpress", "medium", "ghost", "blogger", "hashnode", "devto", "substack"]] = Field(default_factory=lambda: ["medium"], description="Where to publish")
    schedule_enabled: bool = Field(True)
    last_run_at: Optional[datetime] = None
    paused: bool = Field(False)

class MediaItem(BaseModel):
    type: Literal["image", "video"]
    url: HttpUrl
    alt: Optional[str] = None
    caption: Optional[str] = None

class Post(BaseModel):
    """
    Represents a generated post
    Collection: "post"
    """
    topic: str
    title: str
    meta_description: str
    keywords: List[str] = []
    language: str = "en"
    content_html: str
    featured_image: Optional[HttpUrl] = None
    media: List[MediaItem] = Field(default_factory=list)
    status: Literal["generated", "published", "failed"] = "generated"
    platforms_published: List[str] = Field(default_factory=list)
    external_urls: List[HttpUrl] = Field(default_factory=list)
    scheduled_for: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Example schemas kept for reference
class User(BaseModel):
    name: str
    email: str
    address: str

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
