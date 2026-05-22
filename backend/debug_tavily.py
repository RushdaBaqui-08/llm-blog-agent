import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

client = TavilyClient()
query = "Apple WWDC 2025 major announcements"
print(f"Searching Tavily for query: '{query}'...")
response = client.search(query=query, max_results=5)
results = response.get("results") or []

print(f"Total results: {len(results)}")
for idx, r in enumerate(results):
    print(f"\nResult {idx+1}:")
    print(f"Title: {r.get('title')}")
    print(f"URL: {r.get('url')}")
    print(f"Published Date: {r.get('published_date')}")
    print(f"Content length: {len(r.get('content') or '')} chars")
