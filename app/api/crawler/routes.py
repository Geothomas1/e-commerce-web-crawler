import os
import uuid
import json
from fastapi import APIRouter, BackgroundTasks
from .utils.models import CrawlerRequest, CrawlResponse
from .utils.constants import OUTPUT_DIR
from .utils.service import run_crawler


crawler_api = APIRouter()


@crawler_api.post('/', response_model=CrawlResponse)
async def start_crawler(crawler_request: CrawlerRequest, background_task: BackgroundTasks):
    job_id = str(uuid.uuid4())
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    job_json = os.path.join(OUTPUT_DIR, f'{job_id}_status.json')
    active_jobs = dict()
    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "Running",
        "request_domain": [crawler_request.domains],
    }
    with open(job_json, 'w') as f:
        json.dump(active_jobs[job_id], f)

    background_task.add_task(
        run_crawler,
        crawler_request.domains,
        crawler_request.max_pages_per_domain,
        job_json,
        job_id,
    )

    return CrawlResponse(job_id=job_id, status="success", message="Crawling started")
