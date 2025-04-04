import asyncio
import re
import logging
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("crawler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class EcommerceProductCrawler:
    def __init__(self, domains, max_pages_per_domain=1000, timeout=10):
        """
        E-commerce Product Crawler
        Args:     ftim
            domains (list): List of e-commerce domains to crawl
            max_pages_per_domain (int): Maximum pages to crawl per domain
            max_workers (int): Maximum concurrent workers
            timeout (int): Request timeout in seconds
        """
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.results = {}
        self.timeout = timeout

        self.product_url_patterns = [
            r'/product[s]?/',
            r'/item[s]?/',
            r'/p/',
            r'/pd/',
            r'/detail/',
            r'/-pr-',
            r'/dp/',
            r'/men[s]?/',
            r'/women[s]?/',
            r'/kids/',
            r'/children/',
            r'/baby/',
            r'/unisex/',
            r'/clothing/',
            r'/apparel/',
            r'/shoes/',
            r'/accessories/',
            r'/wear/',
            r'/fashion/',
            r'/outfit[s]?/',
            r'/dress[es]?/',
            r'/shirt[s]?/',
            r'/trouser[s]?/',
            r'/jean[s]?/',
            r'/pant[s]?/',
            r'/sweater[s]?/',
            r'/hoodie[s]?/',
            r'/jacket[s]?/',
            r'/coat[s]?/',
            r'/underwear/',
            r'/sock[s]?/',
            r'/lingerie/',
            # Shopping
            r'/buy/',
            r'/shop/',
            r'/catalog/',
            r'/collection[s]?/',
            r'/look/',
            r'/style/',
            r'/season/',
            r'/[^/]+/[^/]+\d+\.html',  # category/product12345.html
            r'/products-id/',
            r'/productdetail/',
            r'/product-detail/',
            r'/clothes/',
            r'/wardrobe/',
        ]

        self.exclude_patterns = [
            r'/cart',
            r'/checkout',
            r'/account',
            r'/login',
            r'/register',
            r'/wishlist',
            r'/compare',
            r'/search',
            r'/category',
            r'/tag',
            r'/blog',
        ]

    async def is_product_url(self, url):
        """
        Check if a URL is likely to be a product page based on patterns

        Args:
            url (str): URL to check

        Returns:
            bool: True if likely a product URL, False otherwise
        """
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        # Check : excluded patterns
        if any(re.search(pattern, path) for pattern in self.exclude_patterns):
            return False

        # Check : product patterns
        return any(re.search(pattern, path) for pattern in self.product_url_patterns)

    async def fetch_url(self, session, url):
        """
        Fetch a URL and return its HTML content

        Args:
            session (aiohttp.ClientSession): HTTP session
            url (str): URL to fetch

        Returns:
            str: HTML content or None if request failed
        """
        try:
            async with session.get(url, timeout=self.timeout, allow_redirects=True) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to fetch {url}, status code: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def extract_links(self, html, base_url):
        """
        Extract all links from HTML content

        Args:
            html (str): HTML content
            base_url (str): Base URL for resolving relative URLs

        Returns:
            list: List of absolute URLs
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        links = []

        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            # Ensure we stay within the same domain
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                links.append(absolute_url)

        return links

    async def process_domain(self, domain):
        """
        Process a single domain to find product URLs

        Args:
            domain (str): Domain to crawl

        Returns:
            list: List of product URLs found
        """
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain

        visited_urls = set()
        to_visit = [domain]
        product_urls = set()

        base_domain = urlparse(domain).netloc

        # Custom headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

        # Set up rate limiting
        rate_limit = 1.0  # requests per second

        async with aiohttp.ClientSession(headers=headers) as session:
            with tqdm(total=self.max_pages_per_domain, desc=f"Crawling {base_domain}") as pbar:
                while to_visit and len(visited_urls) < self.max_pages_per_domain:
                    # Process URLs in batches for efficiency
                    batch_size = len(to_visit)
                    current_batch = to_visit[:batch_size]
                    to_visit = to_visit[batch_size:]
                    print("batch_size", batch_size)
                    print("current_batch", current_batch)
                    print("to_visit", to_visit)

                    # Process the batch
                    tasks = []
                    for url in current_batch:
                        if url not in visited_urls:
                            visited_urls.add(url)
                            # Add a small delay for rate limiting
                            await asyncio.sleep(1.0 / rate_limit)
                            tasks.append(
                                self.process_url(session, url, base_domain, visited_urls, to_visit, product_urls)
                            )

                    await asyncio.gather(*tasks)
                    pbar.update(len(current_batch))

        logger.info(f"Found {len(product_urls)} product URLs on {domain}")
        return list(product_urls)

    async def process_url(self, session, url, base_domain, visited_urls, to_visit, product_urls):
        """
        Process a single URL - fetch it, check if it's a product, and extract more links

        Args:
            session : HTTP session
            url (str): URL to process
            base_domain (str): Base domain being crawled
            visited_urls (set): Set of already visited URLs
            to_visit (list): List of URLs to visit
            product_urls (set): Set of product URLs found
        """
        html = await self.fetch_url(session, url)
        print("----------------URLS----------------", url)
        if not html:
            return

        # Check if this is a product URL

        # Extract more links to visit

        links = await self.extract_links(html, url)
        print("TO VISITED", to_visit)
        for link in links:
            if link not in visited_urls and urlparse(link).netloc == base_domain:
                if await self.is_product_url(link):
                    product_urls.add(link)
                to_visit.append(link)
        print("AFTER TO VISITED", to_visit)

    async def crawl(self):
        """
        Crawl all domains to find product URLs

        Returns:
            dict: Dictionary mapping domains to lists of product URLs
        """
        tasks = []
        for domain in self.domains:
            clean_domain = domain.strip('/')
            tasks.append(self.process_domain(clean_domain))

        results = await asyncio.gather(*tasks)

        # Map results to domains
        for i, domain in enumerate(self.domains):
            self.results[domain] = results[i]

        return self.results


async def main():
    domains = ["https://www.virgio.com/"]

    crawler = EcommerceProductCrawler(
        domains=domains,
        max_pages_per_domain=10,
    )

    logger.info("Starting crawler...")
    results = await crawler.crawl()

    print("\nCrawling Complete - Summary:")
    for domain, urls in results.items():
        print(f"{domain}: {len(urls)} product URLs found")
        print(urls)


if __name__ == "__main__":
    asyncio.run(main())
