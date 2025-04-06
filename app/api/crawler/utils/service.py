import asyncio
import os
import re
import json
import logging
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
import pandas as pd
from .constants import OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/crawler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class EcommerceProductCrawler:
    def __init__(self, domains, max_pages_per_domain=100, timeout=10):
        """
        E-commerce Product Crawler
        Args:
            domains (list): List of e-commerce domains to crawl
            max_pages_per_domain (int): Maximum pages to crawl per domain
        """
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.results = {}
        self.timeout = timeout

        self.product_url_patterns = [
            r'/product[s]?/[^/]+/?$',  # /products/product-name
            r'/item[s]?/[^/]+/?$',  # /items/item-name
            r'/p/[^/]+/?$',  # /p/product-id
            r'/pd/[^/]+/?$',  # /pd/product-id
            r'/detail/[^/]+/?$',  # /detail/product-name
            r'/dp/[A-Z0-9]{10}/?$',  # Amazon style /dp/PRODUCTID
            r'/-pr-[^/]+/?$',  # /-pr-productid
            r'/[^/]+/[^/]+\d+\.html$',  # category/product12345.html
            r'/productdetail/[^/]+/?$',
            r'/product-detail/[^/]+/?$',
        ]

        # Collection/category URL patterns
        self.collection_url_patterns = [
            r'/collection[s]?/[^/]+/?$',
            r'/category/[^/]+/?$',
            r'/shop/[^/]+/?$',
            r'/catalog/[^/]+/?$',
            r'/men[s]?/?$',
            r'/women[s]?/?$',
            r'/kids/?$',
            r'/sale/?$',
            r'/new-arrival[s]?/?$',
        ]

        self.exclude_patterns = [
            r'/cart',
            r'/checkout',
            r'/account',
            r'/login',
            r'/register',
            r'/wishlist',
            r'/compare',
            r'/search\?',
            r'/tag/',
            r'/blog',
            r'/about',
            r'/contact',
            r'/faq',
            r'/help',
            r'/support',
            r'/careers',
            r'/press',
            r'/privacy',
            r'/terms',
            r'/shipping',
            r'/returns',
            r'/profile',
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

    async def is_collection_url(self, url):
        """
        Check if a URL is likely to be a collection/category page

        Args:
            url (str): URL to check

        Returns:
            bool: True if likely a collection URL, False otherwise
        """
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        # Check excluded patterns
        if any(re.search(pattern, path + parsed_url.query) for pattern in self.exclude_patterns):
            return False

        # Check collection patterns
        return any(re.search(pattern, path) for pattern in self.collection_url_patterns)

    async def verify_product_page(self, html, url):
        """
        Verify if a page is a product page by examining its content with enhanced detection
        for e-commerce specific elements like size selection, pincode checks, and offers.

        Args:
            html (str): HTML content
            url (str): URL of the page

        Returns:
            bool: True if confirmed as a product page, False otherwise
        """
        if not html:
            return False

        soup = BeautifulSoup(html, 'html.parser')

        # Initialize score for product and collection indicators
        product_score = 0
        collection_score = 0

        # === PRODUCT PAGE INDICATORS ===

        # 1. Add to Cart/Bag buttons (strong indicators)
        cart_button_patterns = [
            r'add\s+to\s+cart',
            r'add\s+to\s+bag',
            r'buy\s+now',
            r'purchase\s+now',
            r'add\s+to\s+basket',
            r'place\s+order',
            r'checkout\s+now',
        ]

        for pattern in cart_button_patterns:
            # Check button text
            cart_buttons = soup.find_all(['button', 'a', 'input'], string=re.compile(pattern, re.I))
            # Check value attribute for input buttons
            cart_inputs = soup.find_all('input', {'value': re.compile(pattern, re.I)})
            # Check class or id attributes
            cart_elements = soup.find_all(attrs={'class': re.compile(pattern, re.I)})
            cart_elements.extend(soup.find_all(attrs={'id': re.compile(pattern, re.I)}))

            if cart_buttons or cart_inputs or cart_elements:
                product_score += 3  # Strong indicator
                break

        # 2. Size/variant selection (very strong indicator)
        size_indicators = [
            soup.find_all(['select', 'div', 'ul'], attrs={'class': re.compile(r'size', re.I)}),
            soup.find_all(['select', 'div', 'ul'], attrs={'id': re.compile(r'size', re.I)}),
            soup.find_all(['select', 'div', 'ul'], attrs={'class': re.compile(r'variant', re.I)}),
            soup.find_all(['select', 'div', 'ul'], attrs={'id': re.compile(r'variant', re.I)}),
            soup.find_all(['select', 'div', 'ul'], attrs={'data-product': re.compile(r'.+')}),
            soup.find_all('label', string=re.compile(r'size|color|variant|quantity', re.I)),
            soup.find_all(['input', 'button'], attrs={'name': re.compile(r'size|color|variant', re.I)}),
        ]

        for indicator_group in size_indicators:
            if indicator_group:
                product_score += 3
                break

        # 3. Pincode/Zipcode check (strong indicator for Indian e-commerce)
        pincode_indicators = [
            soup.find_all(
                string=re.compile(r'check\s+pincode|check\s+delivery|check\s+availability|delivery\s+to', re.I)
            ),
            soup.find_all(
                ['input', 'div'], attrs={'placeholder': re.compile(r'pincode|zip\s*code|postal\s*code', re.I)}
            ),
            soup.find_all(['input', 'div'], attrs={'class': re.compile(r'pincode|zip\s*code|postal\s*code', re.I)}),
            soup.find_all(['input', 'div'], attrs={'id': re.compile(r'pincode|zip\s*code|postal\s*code', re.I)}),
            soup.find_all(attrs={'aria-label': re.compile(r'pincode|zip\s*code|postal\s*code', re.I)}),
        ]

        for indicator_group in pincode_indicators:
            if indicator_group:
                product_score += 2
                break

        # 4. Bank offers/payment options (good indicator)
        payment_indicators = [
            soup.find_all(string=re.compile(r'bank\s+offer|payment\s+option|EMI|credit\s+card|debit\s+card', re.I)),
            soup.find_all(['div', 'section'], attrs={'class': re.compile(r'offer|payment|emi', re.I)}),
            soup.find_all(['div', 'section'], attrs={'id': re.compile(r'offer|payment|emi', re.I)}),
            soup.find_all(['img'], attrs={'alt': re.compile(r'visa|mastercard|paypal|gpay|upi', re.I)}),
        ]

        for indicator_group in payment_indicators:
            if indicator_group:
                product_score += 1
                break

        # 5. Shipping information (good indicator)
        shipping_indicators = [
            soup.find_all(string=re.compile(r'shipping|delivery|dispatch|free\s+delivery|express\s+delivery', re.I)),
            soup.find_all(['div', 'section', 'p'], attrs={'class': re.compile(r'shipping|delivery', re.I)}),
            soup.find_all(['div', 'section', 'p'], attrs={'id': re.compile(r'shipping|delivery', re.I)}),
        ]

        for indicator_group in shipping_indicators:
            if indicator_group:
                product_score += 1
                break

        # 6. Product details/specifications (good indicator)
        detail_indicators = [
            soup.find_all(
                ['div', 'section'], attrs={'class': re.compile(r'product[-_]detail|specification|description', re.I)}
            ),
            soup.find_all(
                ['div', 'section'], attrs={'id': re.compile(r'product[-_]detail|specification|description', re.I)}
            ),
            soup.find_all(
                ['h2', 'h3', 'h4'], string=re.compile(r'product\s+detail|specification|description|feature', re.I)
            ),
        ]

        for indicator_group in detail_indicators:
            if indicator_group:
                product_score += 1
                break

        # 7. Price elements (strong indicator)
        price_indicators = [
            soup.find_all(['span', 'div', 'p'], attrs={'class': re.compile(r'price|cost|mrp', re.I)}),
            soup.find_all(['span', 'div', 'p'], attrs={'id': re.compile(r'price|cost|mrp', re.I)}),
            soup.find_all(string=re.compile(r'(\$|€|£|₹|\bUSD|\bEUR|\bGBP|\bINR)\s*\d+(\.\d{2})?', re.I)),
        ]

        for indicator_group in price_indicators:
            if indicator_group:
                product_score += 2
                break

        # 8. Product reviews (good indicator)
        review_indicators = [
            soup.find_all(['div', 'section'], attrs={'class': re.compile(r'review|rating|star', re.I)}),
            soup.find_all(['div', 'section'], attrs={'id': re.compile(r'review|rating|star', re.I)}),
            soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'review|rating|customer', re.I)),
        ]

        for indicator_group in review_indicators:
            if indicator_group:
                product_score += 1
                break

        # 9. Product image gallery (good indicator)
        gallery_indicators = [
            soup.find_all(['div', 'ul'], attrs={'class': re.compile(r'gallery|slider|product[-_]image', re.I)}),
            soup.find_all(['div', 'ul'], attrs={'id': re.compile(r'gallery|slider|product[-_]image', re.I)}),
            len(soup.find_all('img', attrs={'class': re.compile(r'product|item', re.I)})) > 2,
        ]

        for indicator_group in gallery_indicators:
            if indicator_group:
                product_score += 1
                break

        # 10. Product schema markup (very strong indicator)
        schema_script = soup.find('script', {'type': 'application/ld+json'}, string=re.compile(r'"@type":\s*"Product"'))
        if schema_script:
            product_score += 4

        # 11. Wishlist/favorites (moderate indicator)
        wishlist_indicators = [
            soup.find_all(string=re.compile(r'wishlist|favorite|save\s+for\s+later', re.I)),
            soup.find_all(['button', 'a'], attrs={'class': re.compile(r'wishlist|favorite|heart', re.I)}),
            soup.find_all(['button', 'a'], attrs={'id': re.compile(r'wishlist|favorite|heart', re.I)}),
        ]

        for indicator_group in wishlist_indicators:
            if indicator_group:
                product_score += 1
                break

        # 12. Stock status (good indicator)
        stock_indicators = [
            soup.find_all(string=re.compile(r'in\s+stock|out\s+of\s+stock|available|unavailable', re.I)),
            soup.find_all(['div', 'span'], attrs={'class': re.compile(r'stock|availability', re.I)}),
            soup.find_all(['div', 'span'], attrs={'id': re.compile(r'stock|availability', re.I)}),
        ]

        for indicator_group in stock_indicators:
            if indicator_group:
                product_score += 1
                break

        # === COLLECTION PAGE INDICATORS ===

        # 1. Product grid/list views
        collection_view_indicators = [
            soup.find_all(
                ['div', 'ul'], attrs={'class': re.compile(r'product[-_]grid|product[-_]list|products', re.I)}
            ),
            soup.find_all(['div', 'ul'], attrs={'id': re.compile(r'product[-_]grid|product[-_]list|products', re.I)}),
        ]

        for indicator_group in collection_view_indicators:
            if indicator_group:
                collection_score += 2
                break

        # 2. Filter/sort options
        filter_indicators = [
            soup.find_all(['div', 'form'], attrs={'class': re.compile(r'filter|sort|facet', re.I)}),
            soup.find_all(['div', 'form'], attrs={'id': re.compile(r'filter|sort|facet', re.I)}),
            soup.find_all(['select'], attrs={'name': re.compile(r'sort|filter', re.I)}),
            soup.find_all(string=re.compile(r'filter\s+by|sort\s+by', re.I)),
        ]

        for indicator_group in filter_indicators:
            if indicator_group:
                collection_score += 2
                break

        # 3. Pagination
        pagination_indicators = [
            soup.find_all(['div', 'ul', 'nav'], attrs={'class': re.compile(r'pagination|pager', re.I)}),
            soup.find_all(['div', 'ul', 'nav'], attrs={'id': re.compile(r'pagination|pager', re.I)}),
            soup.find_all(
                ['a'], string=re.compile(r'next|prev|previous|\d+', re.I), attrs={'class': re.compile(r'page', re.I)}
            ),
        ]

        for indicator_group in pagination_indicators:
            if indicator_group:
                collection_score += 2
                break

        # 4. Multiple product items with similar structure
        # Count product cards or items that might indicate a collection
        product_items = soup.find_all(['div', 'li'], attrs={'class': re.compile(r'product[-_]item|item|card', re.I)})
        if len(product_items) > 3:
            collection_score += len(product_items) // 3  # Higher score for more products

        # 5. Multiple "Add to Cart" buttons (indicates collection page with many products)
        add_cart_buttons = []
        for pattern in cart_button_patterns:
            add_cart_buttons.extend(soup.find_all(['button', 'a', 'input'], string=re.compile(pattern, re.I)))

        if len(add_cart_buttons) > 2:
            collection_score += 2

        # Count product links
        product_link_count = 0
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_href = urljoin(url, href)
            if any(re.search(pattern, urlparse(absolute_href).path.lower()) for pattern in self.product_url_patterns):
                product_link_count += 1

        if product_link_count > 5:
            collection_score += product_link_count // 5  # More product links means higher collection score

        # === MAKE DECISION ===

        # Log scores for debugging
        logger.debug(f"URL: {url}, Product Score: {product_score}, Collection Score: {collection_score}")

        # Decision logic:
        # 1. Strong product indicators (score >= 7) and product score > collection score
        # 2. Medium product indicators (score >= 4) and product score >= 2 * collection score
        # 3. URL matches product pattern and has some product indicators (score >= 2)

        if (
            (product_score >= 7 and product_score > collection_score)
            or (product_score >= 4 and product_score >= 2 * collection_score)
            or (await self.is_product_url(url) and product_score >= 2)
        ):
            return True
        else:
            return False

    async def fetch_url(self, session, url, visited_urls, max_retries=3, retry_delay=2):
        """
        Fetch a URL and return its HTML content

        Args:
            session (aiohttp.ClientSession): HTTP session
            url (str): URL to fetch

        Returns:
            str: HTML content or None if request failed
        """

        retries = 0
        while retries <= max_retries:
            try:
                async with session.get(url, timeout=self.timeout, allow_redirects=True) as response:
                    print(response.status)
                    if response.status == 200:
                        return await response.text()
                    else:
                        retries += 1
                        logger.warning(f"Failed to fetch {url}, status code: {response.status}")
                        return None
            except Exception as e:
                retries += 1
                await asyncio.sleep(retry_delay)

                logger.error(f"Error fetching {url} Retrying : {retries}: {str(e)}")
                # need to write logic for retry
                # if url in visited_urls:
                #     visited_urls.remove(url)
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
        collection_url = set()
        confirmed_product_urls = set()

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

                    # Process the batch
                    tasks = []
                    for url in current_batch:
                        if url not in visited_urls:
                            visited_urls.add(url)
                            # Add a small delay for rate limiting
                            await asyncio.sleep(1.0 / rate_limit)
                            tasks.append(
                                self.process_url(
                                    session,
                                    url,
                                    base_domain,
                                    visited_urls,
                                    to_visit,
                                    product_urls,
                                    collection_url,
                                    confirmed_product_urls,
                                )
                            )

                    await asyncio.gather(*tasks)
                    pbar.update(len(current_batch))

        logger.info(f"Found {len(confirmed_product_urls)} product URLs on {domain}")
        return list(confirmed_product_urls)

    async def process_url(
        self, session, url, base_domain, visited_urls, to_visit, product_urls, collection_urls, confirmed_product_urls
    ):
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
        html = await self.fetch_url(session, url, visited_urls)
        print("----------------URLS----------------", url)
        if not html:
            return

        # Check if this is a product URL (based on URL pattern)
        if await self.is_product_url(url):
            if await self.verify_product_page(html, url):
                confirmed_product_urls.add(url)
            product_urls.add(url)  # Keep track of URL-pattern-based products too

        # Check if this is a collection URL
        if await self.is_collection_url(url):
            collection_urls.add(url)

        links = await self.extract_links(html, url)
        for link in links:
            if link not in visited_urls and urlparse(link).netloc == base_domain:
                to_visit.append(link)

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

    def save_results(self, job_id):
        """
        Save the results to a CSV file

        Args:
            output_file (str): Path to the output file
        """

        for domain, urls in self.results.items():
            domain_name = urlparse(domain).netloc.replace('.', '_')
            domain_file = os.path.join(OUTPUT_DIR, f"{job_id}_{domain_name}.csv")
            domain_df = pd.DataFrame({'product_url': urls})
            domain_df.to_csv(domain_file, index=False)
            logger.info(f"Domain results saved to {domain_file}")


async def run_crawler(domains, max_pages, job_json, job_id):

    crawler = EcommerceProductCrawler(domains=domains, max_pages_per_domain=max_pages)

    logger.info("Starting crawler...")
    results = await crawler.crawl()
    crawler.save_results(job_id)

    with open(job_json, 'r') as f:
        status_data = json.load(f)
        status_data["status"] = "completed"
        with open(job_json, 'w') as f:
            json.dump(status_data, f)

    print("\nCrawling Complete - Summary:")
    for domain, urls in results.items():
        print(f"{domain}: {len(urls)} product URLs found")
        print(urls)
