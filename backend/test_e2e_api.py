import json
import httpx
import sys
import os

def main():
    payload = {
        "topic": "latest key update in of 2026 google I/O meeting",
        "as_of": "2026-05-21"
    }
    print("Sending POST request to /api/generate...")
    
    # We will read line-by-line. The SSE format sends data like:
    # event: update
    # data: {...}
    # and is separated by a blank line.
    
    current_event = None
    
    try:
        with httpx.stream("POST", "http://localhost:8000/api/generate", json=payload, timeout=300.0) as r:
            if r.status_code != 200:
                print(f"Error: status code {r.status_code}")
                try:
                    print(r.read())
                except Exception:
                    pass
                sys.exit(1)
            
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                        if data.get("error"):
                            print(f"\n[STREAM ERROR] {data.get('error')}")
                            continue
                            
                        node = data.get("node")
                        mode = data.get("mode")
                        needs_research = data.get("needs_research")
                        evidence_count = data.get("evidence_count")
                        plan = data.get("plan")
                        sections_count = data.get("sections_count")
                        image_specs = data.get("image_specs")
                        
                        print(f"\n--- Event: {current_event} (Node: {node}) ---")
                        print(f"Mode: {mode}, Needs Research: {needs_research}, Evidence Count: {evidence_count}")
                        if plan:
                            print(f"Plan Title: {plan.get('blog_title')}")
                            print(f"Tasks Outline:")
                            for task in plan.get("tasks", []):
                                print(f"  - [{task.get('id')}] {task.get('title')} (bullets: {task.get('bullets')})")
                        if image_specs:
                            print(f"Image Specs Count: {len(image_specs)}")
                            for idx, img in enumerate(image_specs):
                                print(f"  - Image {idx+1}: {img.get('filename')} | Alt: {img.get('alt')} | Caption: {img.get('caption')}")
                                print(f"    Prompt: {img.get('prompt')}")
                        if data.get("final"):
                            print(f"Final output generated! Length: {len(data.get('final'))} chars")
                            
                    except Exception as parse_err:
                        print(f"Could not parse data line: {data_str[:200]}... Error: {parse_err}")
    except Exception as e:
        print(f"HTTP request failed: {e}")

if __name__ == "__main__":
    main()
