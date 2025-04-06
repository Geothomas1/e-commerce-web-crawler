# Define data models
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Dict


class CrawlerRequest(BaseModel):
    domains: List[str]
    max_pages_per_domain: Optional[int] = 10


class CrawlResponse(BaseModel):
    job_id: UUID
    status: str
    message: str


class JobStatus(BaseModel):
    status: dict


class JobResults(BaseModel):
    product_urls: Optional[list] = None
    total_products_found: Optional[int] = None


class CrawlerResults(BaseModel):
    job_id: str
    results: Dict[str, List[str]]
