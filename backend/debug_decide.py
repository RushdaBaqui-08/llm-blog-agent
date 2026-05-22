import os
import sys
from dotenv import load_dotenv

sys.path.append("/Users/rushdabaqui/Desktop/Blog_Writting_Agent/backend")

from bwa_backend import decide_images, State, Plan, Task

load_dotenv()

# Read the merged markdown
merged_md = open("/Users/rushdabaqui/Desktop/Blog_Writting_Agent/google_io_2026_latest_key_updates_from_the_conference.md").read()

state = {
    "topic": "latest key update in of 2026 google I/O meeting",
    "mode": "open_book",
    "needs_research": True,
    "queries": [],
    "evidence": [],
    "plan": Plan(
        blog_title="Google I/O 2026: Latest Key Updates from the Conference",
        audience="Developers and tech enthusiasts",
        tone="Informative",
        blog_kind="news_roundup",
        tasks=[]
    ),
    "recency_days": 7,
    "sections": [],
    "merged_md": merged_md,
    "md_with_placeholders": "",
    "image_specs": [],
    "final": ""
}

print("Running decide_images node...")
res = decide_images(state)
print("\n--- Image Specs ---")
print(res.get("image_specs"))
print("\n--- Markdown with Placeholders ---")
print(res.get("md_with_placeholders"))
