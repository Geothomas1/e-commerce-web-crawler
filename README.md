# Ecommerce website crawler

Web Crawler for Product URLs

## Requirements

- Python 3.9+
- FastAPI,
- BeautifulSoup,
- Selenium
- Docker (optional)

Input Domains

[
"https://www.virgio.com/",
"https://www.tatacliq.com/",
"https://nykaafashion.com/",
"https://www.westside.com/"
]

## API Endpoints

```
1. POST /api/crawler/

Initiates a web crawling task for a list of domains.
{
  "domains": [
    "https://www.tatacliq.com/","https://www.nykaafashion.com/"
  ],
  "max_pages_per_domain": 2
}
Response:

{
  "job_id": "b5b19f4b-fe34-4eb6-9ae2-899fed9b5019",
  "status": "success",
  "message": "Crawling started"
}

Saves results in:

{HOME*DIR}/crawler_results/{job_id}*{domain_name}.csv

2. GET /crawler/status/{job_id}
   Purpose: Checks the current status of a crawling job.

Response:

{
  "status": {
    "job_id": "b5b19f4b-fe34-4eb6-9ae2-899fed9b5019",
    "status": "completed",
    "request_domain": [
      "https://www.virgio.com/"
    ]
  }
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
```

## Install dependencies:

pip install -r requirements.txt

## Start FastAPI server:

```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access Swagger docs at: http://localhost:8000/docs

Doc link - https://docs.google.com/document/d/1kgER5Vsoolw_nW5RsXq5rDOFD5FB7pflaTSVwK_21VU/edit?usp=sharing
