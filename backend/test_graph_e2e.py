import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append("/Users/rushdabaqui/Desktop/Blog_Writting_Agent/backend")

from bwa_backend import app as graph_app, State

load_dotenv()

async def run():
    inputs = {
        "topic": "major announcements from Apple WWDC 2025 conference",
        "mode": "",
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "plan": None,
        "as_of": "2026-05-21",
        "recency_days": 7,
        "sections": [],
        "merged_md": "",
        "md_with_placeholders": "",
        "image_specs": [],
        "final": "",
    }
    
    print("Executing main graph directly...")
    try:
        async for event in graph_app.astream(inputs, stream_mode="updates"):
            print("\n================ NODE EVENT ================")
            print(event)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
