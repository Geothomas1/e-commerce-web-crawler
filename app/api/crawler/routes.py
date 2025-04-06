import os
import uuid
import json
import pandas as pd
from urllib.parse import urlparse
from fastapi import APIRouter, BackgroundTasks, HTTPException
from .utils.models import CrawlerRequest, CrawlResponse, JobStatus, CrawlerResults
from .utils.files import OUTPUT_DIR
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
        "request_domain": crawler_request.domains,
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


@crawler_api.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get the status of a crawling job
    """
    print(OUTPUT_DIR)

    status_file = os.path.join(OUTPUT_DIR, f"{job_id}_status.json")
    if os.path.exists(status_file):
        with open(status_file, 'r') as f:
            status_data = json.load(f)
            print(status_data)
            return JobStatus(status=status_data)
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@crawler_api.get('/results/{job_id}')
async def get_job_results(job_id: str):
    status_file = os.path.join(OUTPUT_DIR, f"{job_id}_status.json")

    if not os.path.exists(status_file):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    with open(status_file, 'r') as f:
        status_data = json.load(f)

    if status_data["status"] != "completed":
        return {
            "job_id": job_id,
            "status": status_data["status"],
            "message": f"Job is {status_data['status']}, results not available yet",
        }
    results = {}
    for domain in status_data.get('request_domain', []):
        domain = urlparse(domain).netloc.replace('.', '_')
        file_path = os.path.join(OUTPUT_DIR, f'{job_id}_{domain}.csv')
        if os.path.exists(file_path):
            urls_df = pd.read_csv(file_path)
            results[domain] = urls_df['product_url'].tolist()

    return CrawlerResults(job_id=job_id, results=results)
