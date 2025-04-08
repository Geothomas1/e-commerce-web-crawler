# shoppin-task-web-crawler

ecommerce website crawler

Web Crawler for Product URLs
With Python,FastAPI, BeautifulSoup, Selenium

Input Domains

[
"https://www.virgio.com/",
"https://www.tatacliq.com/",
"https://nykaafashion.com/",
"https://www.westside.com/"
]

API Endpoints

1. POST /api/crawler/

Purpose: Initiates a web crawling task for a list of domains.

{
"domains": ["https://example.com", "https://example2.com"],
"max_pages_per_domain": 20 // Optional
}
Response:

Edit
{
"job_id": "abcd1234",
"status": "pending"
}

Saves results in:

{HOME*DIR}/crawler_results/{job_id}*{domain_name}.csv

2. GET /crawler/status/{job_id}
   Purpose: Checks the current status of a crawling job.

Response:

{
"job_id": "abcd1234",
"status": "running"
}
Possible status values:

pending

running

completed

3. GET /crawler/results/{job_id}
   Purpose: Retrieve all product URLs found for each domain.

Response:

{
"virgio.com": [
"https://www.virgio.com/product1",
"https://www.virgio.com/product2"
],
"tatacliq.com": [
"https://www.tatacliq.com/product1"
]
}

Install dependencies:

pip install -r requirements.txt
Start FastAPI server:

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Access Swagger docs at: http://localhost:8000/docs
