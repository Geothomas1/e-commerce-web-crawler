# Define data models
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional


class CrawlerRequest(BaseModel):
    domains: List[str]
    max_pages_per_domain: Optional[int] = 10


class CrawlResponse(BaseModel):
    job_id: UUID
    status: str
    message: str
