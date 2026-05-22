import os
import sys
import json
import zipfile
import re
from pathlib import Path
from datetime import date
from typing import Dict, Any, List, Optional
from io import BytesIO

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Add current directory and parent directory to sys.path so we can import bwa_backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bwa_backend import app as graph_app, EvidenceItem, Plan

# Locate root directory (parent of backend/)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Initialize FastAPI
app = FastAPI(title="Blog Writing Agent API")

# Enable CORS for Next.js frontend running on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount images directory if it exists
IMAGES_DIR = ROOT_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


class GenerateRequest(BaseModel):
    topic: str
    as_of: Optional[str] = None


def safe_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"


def bundle_zip(md_text: str, md_filename: str, images_dir: Path) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(md_filename, md_text.encode("utf-8"))

        if images_dir.exists() and images_dir.is_dir():
            for p in images_dir.rglob("*"):
                if p.is_file():
                    # Place inside an "images" directory in the zip
                    z.write(p, arcname=f"images/{p.name}")
    return buf.getvalue()


def images_zip(images_dir: Path) -> Optional[bytes]:
    if not images_dir.exists() or not images_dir.is_dir():
        return None
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in images_dir.rglob("*"):
            if p.is_file():
                z.write(p, arcname=p.name)
    return buf.getvalue()


def extract_title_from_md(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            t = line[2:].strip()
            return t or fallback
    return fallback


def extract_latest_state(current_state: Dict[str, Any], step_payload: Any) -> Dict[str, Any]:
    if isinstance(step_payload, dict):
        # LangGraph updates return {node_name: {state_delta}}
        # If it's a subgraph, it might be {subgraph_node: {inner_node: {state_delta}}}
        # Let's recursively merge or check keys
        for key, value in step_payload.items():
            if isinstance(value, dict):
                # Check if it contains State keys, otherwise go one level deeper
                state_keys = {"topic", "mode", "needs_research", "queries", "evidence", "plan", "sections", "merged_md", "md_with_placeholders", "image_specs", "final"}
                if any(k in value for k in state_keys):
                    # Value is the state update
                    for sk, sv in value.items():
                        if sk == "sections" and isinstance(sv, list):
                            if "sections" not in current_state or not isinstance(current_state["sections"], list):
                                current_state["sections"] = []
                            # Avoid duplicates by checking task ID (sections is list of [id, md])
                            existing_ids = {item[0] for item in current_state["sections"]}
                            for item in sv:
                                if item[0] not in existing_ids:
                                    current_state["sections"].append(item)
                        elif sk == "evidence" and isinstance(sv, list):
                            seen_urls = set()
                            unique_evidence = []
                            for item in sv:
                                url = item.get("url") if isinstance(item, dict) else getattr(item, "url", "")
                                if url not in seen_urls:
                                    seen_urls.add(url)
                                    unique_evidence.append(item)
                            current_state["evidence"] = unique_evidence
                        else:
                            current_state[sk] = sv
                else:
                    # Try to merge recursively
                    extract_latest_state(current_state, value)
            else:
                current_state[key] = value
    return current_state


@app.post("/api/generate")
async def generate_blog(request: Request, body: GenerateRequest):
    as_of_val = body.as_of or date.today().isoformat()
    
    inputs = {
        "topic": body.topic.strip(),
        "mode": "",
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "plan": None,
        "as_of": as_of_val,
        "recency_days": 7,
        "sections": [],
        "merged_md": "",
        "md_with_placeholders": "",
        "image_specs": [],
        "final": "",
    }

    async def event_generator():
        current_state = {
            "topic": body.topic.strip(),
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "as_of": as_of_val,
            "recency_days": 7,
            "sections": [],
            "merged_md": "",
            "md_with_placeholders": "",
            "image_specs": [],
            "final": "",
        }
        
        try:
            # We run the graph stream
            async for event_chunk in graph_app.astream(inputs, stream_mode="updates"):
                # Update current accumulated state
                current_state = extract_latest_state(current_state, event_chunk)
                
                # Format chunk state for UI
                # Plan and Evidence are pydantic models or dicts, serialize properly
                plan_dict = None
                if current_state.get("plan"):
                    p = current_state["plan"]
                    plan_dict = p.model_dump() if hasattr(p, "model_dump") else p

                evidence_list = []
                for e in (current_state.get("evidence") or []):
                    evidence_list.append(e.model_dump() if hasattr(e, "model_dump") else e)

                payload = {
                    "node": list(event_chunk.keys())[0] if event_chunk else None,
                    "mode": current_state.get("mode"),
                    "needs_research": current_state.get("needs_research"),
                    "queries": current_state.get("queries"),
                    "evidence_count": len(evidence_list),
                    "evidence": evidence_list,
                    "plan": plan_dict,
                    "sections_count": len(current_state.get("sections") or []),
                    "image_specs": current_state.get("image_specs"),
                    "final": current_state.get("final"),
                }
                
                yield {
                    "event": "update",
                    "data": json.dumps(payload, default=str)
                }

            # After stream completes, send final completed state
            plan_dict = None
            if current_state.get("plan"):
                p = current_state["plan"]
                plan_dict = p.model_dump() if hasattr(p, "model_dump") else p

            evidence_list = []
            for e in (current_state.get("evidence") or []):
                evidence_list.append(e.model_dump() if hasattr(e, "model_dump") else e)

            final_payload = {
                "node": "end",
                "mode": current_state.get("mode"),
                "needs_research": current_state.get("needs_research"),
                "queries": current_state.get("queries"),
                "evidence_count": len(evidence_list),
                "evidence": evidence_list,
                "plan": plan_dict,
                "sections_count": len(current_state.get("sections") or []),
                "image_specs": current_state.get("image_specs"),
                "final": current_state.get("final"),
            }
            yield {
                "event": "final",
                "data": json.dumps(final_payload, default=str)
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


@app.get("/api/blogs")
async def list_blogs():
    files = [p for p in ROOT_DIR.glob("*.md") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    blogs = []
    for p in files:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            title = extract_title_from_md(content, p.stem)
            mtime = p.stat().st_mtime
        except Exception:
            title = p.stem
            mtime = 0
            
        blogs.append({
            "filename": p.name,
            "title": title,
            "updated_at": mtime
        })
    return blogs


@app.get("/api/blogs/{filename}")
async def get_blog(filename: str):
    file_path = ROOT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Blog not found")
        
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        title = extract_title_from_md(content, file_path.stem)
        
        # Load metadata sidecar if it exists
        metadata = None
        json_path = file_path.with_suffix(".json")
        if json_path.exists() and json_path.is_file():
            try:
                metadata = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        return {
            "filename": filename,
            "title": title,
            "content": content,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading blog: {str(e)}")


@app.get("/api/blogs/{filename}/download")
async def download_blog(filename: str):
    file_path = ROOT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Blog not found")
    return FileResponse(
        path=str(file_path),
        media_type="text/markdown",
        filename=filename
    )


@app.get("/api/blogs/{filename}/bundle")
async def download_bundle(filename: str):
    file_path = ROOT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Blog not found")
        
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        zip_bytes = bundle_zip(content, filename, IMAGES_DIR)
        
        return StreamingResponse(
            BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={file_path.stem}_bundle.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error bundling blog: {str(e)}")


@app.get("/api/blogs/{filename}/images-zip")
async def download_images(filename: str):
    try:
        zip_bytes = images_zip(IMAGES_DIR)
        if not zip_bytes:
            raise HTTPException(status_code=404, detail="No images found to zip")
            
        return StreamingResponse(
            BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=images.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating images zip: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Set reload=True for development convenience
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
