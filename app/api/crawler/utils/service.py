import asyncio
import os
import re
import json
from urllib.parse import urljoin, urlparse
import time
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from .files import OUTPUT_DIR
from .logger import logger


class EcommerceProductCrawler:
    def __init__(self, domains, max_pages_per_domain=None, timeout=10):
        """
        E-commerce Product Crawler
        Args:
            domains (list): List of e-commerce domains to crawl
            max_pages_per_domain (int): Maximum pages to crawl per domain [optional] - to scrape all the ursl pass value as null
        """
        self.domains = domains
        self.max_pages_per_domain = max_pages_per_domain
        self.results = {}
        self.timeout = timeout

        self.product_url_patterns = [
            r'/product[s]?/[^/]+/?$',
            r'/item[s]?/[^/]+/?$',
            r'/p/[^/]+/?$',
            r'/pd/[^/]+/?$',
            r'/detail/[^/]+/?$',
            r'/dp/[A-Z0-9]{10}/?$',
            r'/-pr-[^/]+/?$',
            r'/[^/]+/[^/]+\d+\.html$',
            r'/productdetail/[^/]+/?$',
            r'/product-detail/[^/]+/?$',
            r".+/p-mp\d+$",
            r".+/p/\d+$",
            r"^/products/.+",
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
            r'/orders',
            r'/payments[s]?/[^/]+/?$',
            r'shopping-faq',
        ]

    async def create_driver(self):
        """
        Create and return a configured Selenium WebDriver
        """
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Add scripts to evade detection
        driver.execute_script(
            """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
            """
        )

        return driver

    async def is_exclude_url(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        if any(re.search(pattern, path) for pattern in self.exclude_patterns):
            return True
        return False

    async def verify_product_page(self, html, url):
        """
        Verify if a page is a product page based on various factors
        Args:
            html (str): HTML content
            url (str): URL of the page

        Returns:
            bool: True if confirmed as a product page, otherwise False
        """
        if not html:
            return False

        soup = BeautifulSoup(html, 'html.parser')

        product_score = 0
        collection_score = 0

        # Add to Cart/Bag buttons
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
            cart_buttons = soup.find_all(['button', 'a', 'input'], string=re.compile(pattern, re.I))
            cart_inputs = soup.find_all('input', {'value': re.compile(pattern, re.I)})
            cart_elements = soup.find_all(attrs={'class': re.compile(pattern, re.I)})
            cart_elements.extend(soup.find_all(attrs={'id': re.compile(pattern, re.I)}))

            if cart_buttons or cart_inputs or cart_elements:
                product_score += 3
                break

        # 2. Size selection
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

        # 3. Pincode/Zipcode
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
                product_score += 3
                break

        # 4. Bank offers/payment
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

        # 5. Shipping information
        shipping_indicators = [
            soup.find_all(string=re.compile(r'shipping|delivery|dispatch|free\s+delivery|express\s+delivery', re.I)),
            soup.find_all(['div', 'section', 'p'], attrs={'class': re.compile(r'shipping|delivery', re.I)}),
            soup.find_all(['div', 'section', 'p'], attrs={'id': re.compile(r'shipping|delivery', re.I)}),
        ]

        for indicator_group in shipping_indicators:
            if indicator_group:
                product_score += 1
                break

        # 6. Product details/specifications
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

        # 7. Price elements
        price_indicators = [
            soup.find_all(['span', 'div', 'p'], attrs={'class': re.compile(r'price|cost|mrp', re.I)}),
            soup.find_all(['span', 'div', 'p'], attrs={'id': re.compile(r'price|cost|mrp', re.I)}),
            soup.find_all(string=re.compile(r'(\$|€|£|₹|\bUSD|\bEUR|\bGBP|\bINR)\s*\d+(\.\d{2})?', re.I)),
        ]

        for indicator_group in price_indicators:
            if indicator_group:
                product_score += 2
                break

        # 8. Product reviews
        review_indicators = [
            soup.find_all(['div', 'section'], attrs={'class': re.compile(r'review|rating|star', re.I)}),
            soup.find_all(['div', 'section'], attrs={'id': re.compile(r'review|rating|star', re.I)}),
            soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'review|rating|customer', re.I)),
        ]

        for indicator_group in review_indicators:
            if indicator_group:
                product_score += 1
                break

        # 9. Product images or gallery
        gallery_indicators = [
            soup.find_all(['div', 'ul'], attrs={'class': re.compile(r'gallery|slider|product[-_]image', re.I)}),
            soup.find_all(['div', 'ul'], attrs={'id': re.compile(r'gallery|slider|product[-_]image', re.I)}),
            len(soup.find_all('img', attrs={'class': re.compile(r'product|item', re.I)})) > 2,
        ]

        for indicator_group in gallery_indicators:
            if indicator_group:
                product_score += 1
                break

        # 10. Product schema markup
        schema_script = soup.find('script', {'type': 'application/ld+json'}, string=re.compile(r'"@type":\s*"Product"'))
        if schema_script:
            product_score += 4

        # 11. Wishlist or favorites
        wishlist_indicators = [
            soup.find_all(string=re.compile(r'wishlist|favorite|save\s+for\s+later', re.I)),
            soup.find_all(['button', 'a'], attrs={'class': re.compile(r'wishlist|favorite|heart', re.I)}),
            soup.find_all(['button', 'a'], attrs={'id': re.compile(r'wishlist|favorite|heart', re.I)}),
        ]

        for indicator_group in wishlist_indicators:
            if indicator_group:
                product_score += 1
                break

        # 12. Stock status
        stock_indicators = [
            soup.find_all(string=re.compile(r'in\s+stock|out\s+of\s+stock|available|unavailable', re.I)),
            soup.find_all(['div', 'span'], attrs={'class': re.compile(r'stock|availability', re.I)}),
            soup.find_all(['div', 'span'], attrs={'id': re.compile(r'stock|availability', re.I)}),
        ]

        for indicator_group in stock_indicators:
            if indicator_group:
                product_score += 1
                break

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

        # Count product links
        product_link_count = 0
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_href = urljoin(url, href)
            if any(re.search(pattern, urlparse(absolute_href).path.lower()) for pattern in self.product_url_patterns):
                product_link_count += 1

        if product_link_count > 5:
            collection_score += product_link_count // 5  # means its higher collection score

        logger.info(f"URL: {url}, Product Score: {product_score}, Collection Score: {collection_score}")

        # simple scoring logic

        if (
            (product_score >= 7 and product_score > collection_score)
            or (product_score >= 5 and product_score >= 2 * collection_score)
            or (await self.is_product_url(url) and product_score >= 5)
        ):
            return True
        else:
            return False

    async def is_product_url(self, url: str) -> bool:
        path = urlparse(url).path

        return any(re.match(pattern, path) for pattern in self.product_url_patterns)

    async def fetch_url(self, driver, url, max_retries=3, retry_delay=2):
        """
        Fetch a URL and return its HTML content

        Args:
            Selenium driver
            url (str): URL to fetch

        Returns:
            str: HTML content or None if request failed
        """

        retries = 0
        while retries <= max_retries:
            try:
                driver.get(url)

                WebDriverWait(driver, self.timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                driver.implicitly_wait(2)

                if driver.page_source and len(driver.page_source) > 100:
                    return driver.page_source
                else:
                    retries += 1
                    logger.warning(f"Failed to fetch content from {url}")
                    time.sleep(retry_delay)
            except Exception as e:
                retries += 1
                time.sleep(retry_delay)
                logger.error(f"Error fetching {url} Retrying : {retries}: {str(e)}")

        return None

    async def extract_links(self, html, base_url):
        """
        Extract all links from HTML content

        Args:
            html (str): HTML content
            base_url (str): Base URL

        Returns:
            list: List of links extracted from a href
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        links = []

        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            absolute_url = urljoin(base_url, href)
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                links.append(absolute_url)

        return links

    async def process_domain(self, domain):
        """
        Process a single domain to find product URL's

        Args:
            domain (str): Domain to crawl

        Returns:
            list: List of product URL's
        """
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain

        visited_urls = set()
        to_visit = [domain]
        confirmed_product_urls = set()

        base_domain = urlparse(domain).netloc

        driver = await self.create_driver()

        try:
            with tqdm(total=len(to_visit), desc=f"Crawling {base_domain}") as pbar:
                while to_visit and (self.max_pages_per_domain is None or len(visited_urls) < self.max_pages_per_domain):
                    batch_size = len(to_visit)
                    current_batch = to_visit[:batch_size]
                    to_visit = to_visit[batch_size:]

                    tasks = []
                    for url in current_batch:
                        if url not in visited_urls:
                            visited_urls.add(url)
                            # await asyncio.sleep(0.05)
                            tasks.append(
                                self.process_url(
                                    driver,
                                    url,
                                    base_domain,
                                    visited_urls,
                                    to_visit,
                                    confirmed_product_urls,
                                )
                            )

                    await asyncio.gather(*tasks)
                    pbar.update(len(current_batch))
        finally:
            driver.quit()

        logger.info(f"Found {len(confirmed_product_urls)} product URLs on {domain}")
        return list(confirmed_product_urls)

    async def process_url(self, driver, url, base_domain, visited_urls, to_visit, confirmed_product_urls):
        """
        Process a single URL - fetch it, check if it's a product, and extract more links

        Args:
            driver : Selenium driver
            url (str): URL to process
            base_domain (str): Base domain being crawled
            visited_urls (set): Set of already visited URLs
            to_visit (list): List of URLs to visit
            product_urls (set): Set of product URLs found
        """
        html = await self.fetch_url(driver, url)
        if not html:
            return

        if await self.is_exclude_url(url):
            logger.info("Excluded URL")
            return

        if await self.is_product_url(url):
            # need to check - have to remove it or not
            if await self.verify_product_page(html, url):
                confirmed_product_urls.add(url)

        links = await self.extract_links(html, url)
        for link in links:
            if link not in visited_urls and urlparse(link).netloc == base_domain:
                to_visit.append(link)

    async def crawl(self):
        """
        Crawl all domains to find product URL's

        Returns:
            dict: Dictionary mapping domains to lists of product URLs
        """
        tasks = []
        for domain in self.domains:
            clean_domain = domain.strip('/')
            tasks.append(self.process_domain(clean_domain))

        results = await asyncio.gather(*tasks)

        for i, domain in enumerate(self.domains):
            self.results[domain] = results[i]

        return self.results

    def save_results(self, job_id):
        """
        Save the results to a CSV file

        Args:
            job_id (uuid): job_id
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
