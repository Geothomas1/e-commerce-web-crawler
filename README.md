# shoppin-task-web-crawler

ecommerce website crawler

# assignment 6 : backend engineer role

Problem Statement: Crawler for Discovering Product URLs on E-commerce Websites

**Objective:**
Design and implement a web crawler whose primary task is to discover and list all product URLs across multiple e-commerce websites. You will be provided with a list of domains belonging to various e-commerce platforms. The output should be a comprehensive list of product URLs found on each of the given websites.

**Requirements:**

**Input:**

The crawler should be able to handle these 4 domains at a bare minimum and also be able to scale to handle potentially hundreds.

required domains:
[[https://www.virgio.com/,](https://www.virgio.com/) [https://www.tatacliq.com/,](https://www.tatacliq.com/) [https://nykaafashion.com/,](https://nykaafashion.com/) https://www.westside.com/]

**Key Features:**

- ⁠ ⁠URL Discovery: The crawler should intelligently discover product pages, considering different URL patterns that might be used by different websites (e.g., /product/, /item/, /p/).
  •⁠ ⁠Scalability: The solution should be able to handle large websites with deep hierarchies and a large number of products efficiently.
  •⁠ ⁠Performance: The crawler should be able to execute in parallel or asynchronously to minimize runtime, especially for large sites.
  •⁠ ⁠Robustness: Handle edge cases such as: - Variations in URL structures across different e-commerce platforms.

**Output:**

the output should be strictly:

1. Github repo with all the code along with documentation of the approach on finding the “product” urls
2. A structured list or file that contains all the discovered product URLs for each domain. The output should map each domain to its corresponding list of “product” URLs.
   The URLs should be unique and must point directly to product pages (e.g., [www.example.com/product/12345](http://www.example.com/product/12345)).
3. Video recording (use [loom.com](http://loom.com) preferrably) explaining the approach and a walkthrough of the code.
