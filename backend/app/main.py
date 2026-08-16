"""
PDF Footer Editor - Main FastAPI Application
"""
import os
import uuid
import tempfile
import threading
from contextlib import nullcontext
from typing import Dict, List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from .pdf.reader import PDFReader
from .pdf.renderer import PDFRenderer
from .pdf.text_detector import TextDetector
from .pdf.footer_detector import FooterDetector
from .pdf.text_replacer import TextReplacer
from .pdf.exporter import PDFExporter
from .pdf.smart_features import SmartFooterManager, PageNumberManager, ImageManager
from .models.pdf_models import (
    TextReplaceRequest,
    FooterReplaceRequest,
    BatchFooterRequest,
    ExportRequest,
    FindAcrossPagesRequest,
    FindAcrossPagesResponse,
    TextOccurrence,
    SmartFooterDetectResponse,
    SmartFooterReplaceRequest,
    FooterTemplateRequest,
    PageNumberRequest,
    ImageInsertRequest,
)

app = FastAPI(title="PDF Footer Editor", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for open PDFs
pdf_sessions: Dict[str, dict] = {}
session_locks: Dict[str, threading.Lock] = {}

# Configure upload directories
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


@app.post("/api/pdf/open")
async def open_pdf(file: UploadFile = File(...), password: Optional[str] = Form(None)):
    """Open a PDF file for editing."""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = os.path.join(UPLOAD_DIR, f"{session_id}.pdf")
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Open PDF
        reader = PDFReader(file_path)
        if not reader.open(password):
            os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail="PDF is password protected. Please provide the password."
            )
        
        # Get PDF info
        pdf_info = reader.get_info()
        
        # Store session
        pdf_sessions[session_id] = {
            "reader": reader,
            "renderer": PDFRenderer(reader.doc),
            "text_detector": TextDetector(),
            "footer_detector": FooterDetector(),
            "text_replacer": TextReplacer(),
            "file_path": file_path,
            "filename": file.filename
        }
        session_locks[session_id] = threading.Lock()
        
        return {
            "session_id": session_id,
            "info": pdf_info.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/info")
async def get_pdf_info(session_id: str):
    """Get PDF information."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    info = session["reader"].get_info()
    
    return {"info": info.model_dump()}


@app.get("/api/pdf/{session_id}/page/{page_number}")
async def get_page_image(session_id: str, page_number: int, zoom: float = 1.0):
    """Get rendered page image."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        if lock:
            with lock:
                image_bytes = session["renderer"].render_page(page_number, zoom)
        else:
            image_bytes = session["renderer"].render_page(page_number, zoom)
        return Response(content=image_bytes, media_type="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/page/{page_number}/thumbnail")
async def get_page_thumbnail(session_id: str, page_number: int):
    """Get page thumbnail."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        if lock:
            with lock:
                image_bytes = session["renderer"].render_page_thumbnail(page_number)
        else:
            image_bytes = session["renderer"].render_page_thumbnail(page_number)
        return Response(content=image_bytes, media_type="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/page/{page_number}/text")
async def get_page_text(session_id: str, page_number: int):
    """Get all text blocks from a page."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        if lock:
            with lock:
                blocks = session["reader"].get_page_text_blocks(page_number)
        else:
            blocks = session["reader"].get_page_text_blocks(page_number)
        return {
            "blocks": [b.model_dump() for b in blocks],
            "page_number": page_number
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/page/{page_number}/text-raw")
async def get_page_text_raw(session_id: str, page_number: int):
    """Get raw text from a page."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        if lock:
            with lock:
                text = session["reader"].get_page_text(page_number)
        else:
            text = session["reader"].get_page_text(page_number)
        return {"text": text, "page_number": page_number}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/page/{page_number}/footers")
async def detect_footers(session_id: str, page_number: int):
    """Detect footer text blocks on a page."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            # Get text blocks
            blocks = session["reader"].get_page_text_blocks(page_number)
            
            # Get page height
            page = session["reader"].doc[page_number - 1]
            page_height = page.rect.height
            
            # Detect footers
            footers = session["footer_detector"].detect_footers(blocks, page_height)
        
        return {
            "footers": [f.model_dump() for f in footers],
            "page_number": page_number,
            "page_height": page_height
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/find-across-pages")
async def find_across_pages(session_id: str, request: FindAcrossPagesRequest):
    """Find all occurrences of text across all pages."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        occurrences = []
        
        with lock if lock else nullcontext():
            doc = session["reader"].doc
            total_pages = len(doc)
            
            for page_num in range(1, total_pages + 1):
                blocks = session["reader"].get_page_text_blocks(page_num)
                
                for block in blocks:
                    search_text = request.search_text
                    block_text = block.text
                    
                    if not request.case_sensitive:
                        search_text = search_text.lower()
                        block_text = block_text.lower()
                    
                    if search_text in block_text:
                        occurrences.append(TextOccurrence(
                            text=block.text,
                            bbox=block.bbox,
                            page_number=page_num,
                            font_name=block.font_name,
                            font_size=block.font_size
                        ))
        
        return FindAcrossPagesResponse(
            search_text=request.search_text,
            occurrences=occurrences,
            total_count=len(occurrences)
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/replace-text")
async def replace_text(session_id: str, request: TextReplaceRequest):
    """Replace text in a PDF."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            # Get text blocks to find the original block
            blocks = session["reader"].get_page_text_blocks(request.page_number)
            
            # Find the matching block
            original_block = None
            for block in blocks:
                if block.text == request.original_text:
                    # Check if bbox matches if provided
                    if request.bbox:
                        if abs(block.bbox[0] - request.bbox[0]) < 1 and \
                           abs(block.bbox[1] - request.bbox[1]) < 1:
                            original_block = block
                            break
                    else:
                        original_block = block
                        break
            
            if not original_block:
                raise HTTPException(status_code=404, detail="Text block not found")
            
            # Replace text
            success = session["text_replacer"].replace_text(
                doc=session["reader"].doc,
                page_number=request.page_number,
                original_block=original_block,
                new_text=request.new_text
            )
        
        if success:
            return {"success": True, "message": "Text replaced successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to replace text")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/replace-footer")
async def replace_footer(session_id: str, request: FooterReplaceRequest):
    """Replace footer text on specified pages."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            doc = session["reader"].doc
            replacements = 0
        
        # Determine pages to process
        if request.pages:
            pages_to_process = request.pages
        else:
            pages_to_process = list(range(1, len(doc) + 1))
        
        for page_num in pages_to_process:
            if page_num < 1 or page_num > len(doc):
                continue
            
            # Get text blocks
            blocks = session["reader"].get_page_text_blocks(page_num)
            
            # Get page height
            page = doc[page_num - 1]
            page_height = page.rect.height
            
            # Find footer with matching text
            footers = session["footer_detector"].find_footer_by_content(
                blocks, page_height, request.search_text, request.case_sensitive
            )
            
            for footer in footers:
                success = session["text_replacer"].replace_text(
                    doc=doc,
                    page_number=page_num,
                    original_block=footer,
                    new_text=request.new_text
                )
                if success:
                    replacements += 1
        
        return {
            "success": True,
            "replacements": replacements,
            "message": f"Replaced {replacements} footer instances"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/replace-footer-all")
async def replace_footer_all_pages(session_id: str, request: FooterReplaceRequest):
    """Replace footer text on all pages."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            doc = session["reader"].doc
            
            # Use the text replacer's batch replacement
            replacements = session["text_replacer"].replace_text_on_all_pages(
                doc=doc,
                search_text=request.search_text,
                new_text=request.new_text,
                case_sensitive=request.case_sensitive
            )
        
        return {
            "success": True,
            "replacements": replacements,
            "message": f"Replaced {replacements} footer instances on all pages"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/export")
async def export_pdf(session_id: str, request: ExportRequest = ExportRequest()):
    """Export the edited PDF."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    
    try:
        exporter = PDFExporter(
            doc=session["reader"].doc,
            original_path=session["file_path"]
        )
        
        output_path = exporter.export_safe(
            output_dir=OUTPUT_DIR,
            filename=request.filename
        )
        
        return {
            "success": True,
            "output_path": output_path,
            "message": "PDF exported successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/{session_id}/download")
async def download_pdf(session_id: str):
    """Download the edited PDF."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    
    try:
        exporter = PDFExporter(
            doc=session["reader"].doc,
            original_path=session["file_path"]
        )
        
        # Export to temp location
        temp_path = os.path.join(TEMP_DIR, f"{session_id}_edited.pdf")
        exporter.export(temp_path)
        
        return FileResponse(
            path=temp_path,
            filename=f"{os.path.splitext(session['filename'])[0]}_edited.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/pdf/{session_id}")
async def close_pdf(session_id: str):
    """Close a PDF session and cleanup."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    
    try:
        # Close reader and cleanup
        session["reader"].close()
        
        # Remove uploaded file
        if os.path.exists(session["file_path"]):
            os.remove(session["file_path"])
        
        # Remove from sessions
        del pdf_sessions[session_id]
        if session_id in session_locks:
            del session_locks[session_id]
        
        return {"success": True, "message": "PDF session closed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/undo")
async def undo(session_id: str):
    """Undo last operation."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            success = session["text_replacer"].undo(session["reader"].doc)
        
        if success:
            return {"success": True, "message": "Operation undone"}
        else:
            return {"success": False, "message": "Nothing to undo"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/redo")
async def redo(session_id: str):
    """Redo last undone operation."""
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    
    try:
        with lock if lock else nullcontext():
            success = session["text_replacer"].redo(session["reader"].doc)
        
        if success:
            return {"success": True, "message": "Operation redone"}
        else:
            return {"success": False, "message": "Nothing to redo"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── SMART FOOTER ENDPOINTS ────────────────────────────────────────

@app.post("/api/pdf/{session_id}/smart-footer/detect")
async def detect_smart_footers(session_id: str, page_numbers: Optional[List[int]] = None):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = SmartFooterManager()
            elements = mgr.detect_footers_across_pages(session["reader"].doc, page_numbers)
        return {"elements": elements, "page_count": len(session["reader"].doc)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/smart-footer/replace")
async def replace_smart_footer(session_id: str, request: SmartFooterReplaceRequest):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = SmartFooterManager()
            count = mgr.replace_footer_element(session["reader"].doc, request.element, request.new_text, request.pages)
        return {"success": True, "replacements": count, "message": f"Replaced {count} footer instances"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/smart-footer/template")
async def apply_footer_template(session_id: str, request: FooterTemplateRequest):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = SmartFooterManager()
            template = {}
            if request.left: template["left"] = request.left
            if request.center: template["center"] = request.center
            if request.right: template["right"] = request.right
            count = mgr.apply_footer_template(session["reader"].doc, template, request.custom_vars, request.pages)
        return {"success": True, "count": count, "message": f"Applied footer to {count} locations"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── PAGE NUMBER ENDPOINTS ─────────────────────────────────────────

@app.post("/api/pdf/{session_id}/page-numbers/detect")
async def detect_page_numbers(session_id: str):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = PageNumberManager()
            existing = mgr.detect_existing_page_numbers(session["reader"].doc)
        return {"existing": existing, "count": len(existing)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/page-numbers/add")
async def add_page_numbers(session_id: str, request: PageNumberRequest):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = PageNumberManager()
            count = mgr.add_page_numbers(
                doc=session["reader"].doc, format_str=request.format_str,
                position=request.position, start_at=request.start_at,
                skip_pages=request.skip_pages, font_name=request.font_name,
                font_size=request.font_size, font_color=request.font_color,
                bold=request.bold, italic=request.italic, pages=request.pages,
            )
        return {"success": True, "count": count, "message": f"Added page numbers to {count} pages"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/page-numbers/replace")
async def replace_page_numbers(session_id: str, request: PageNumberRequest):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = PageNumberManager()
            count = mgr.replace_existing_page_numbers(
                doc=session["reader"].doc, format_str=request.format_str,
                start_at=request.start_at, skip_pages=request.skip_pages,
                font_name=request.font_name, font_size=request.font_size,
                font_color=request.font_color, pages=request.pages,
            )
        return {"success": True, "count": count, "message": f"Replaced {count} page numbers"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── IMAGE INSERT ENDPOINTS ────────────────────────────────────────

@app.post("/api/pdf/{session_id}/image/upload")
async def upload_image(session_id: str, file: UploadFile = File(...)):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
            raise HTTPException(status_code=400, detail="Unsupported image format")
        img_dir = os.path.join(os.path.dirname(session["file_path"]), "images")
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, f"{uuid.uuid4()}{ext}")
        content = await file.read()
        with open(img_path, "wb") as f:
            f.write(content)
        mgr = ImageManager()
        info = mgr.get_image_info(img_path)
        return {"success": True, "image_path": img_path, "filename": file.filename, "width": info["width"], "height": info["height"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf/{session_id}/image/insert")
async def insert_image_endpoint(session_id: str, image_path: str = Form(...),
                                page_number: int = Form(1), x: float = Form(100),
                                y: float = Form(100), width: Optional[float] = Form(None),
                                height: Optional[float] = Form(None), apply_to_all: bool = Form(False)):
    if session_id not in pdf_sessions:
        raise HTTPException(status_code=404, detail="PDF session not found")
    session = pdf_sessions[session_id]
    lock = session_locks.get(session_id)
    try:
        with lock if lock else nullcontext():
            mgr = ImageManager()
            if apply_to_all:
                results = mgr.insert_image_all_pages(session["reader"].doc, image_path, x, y, width, height)
                count = len(results)
            else:
                mgr.insert_image(session["reader"].doc, page_number, image_path, x, y, width, height)
                count = 1
        return {"success": True, "count": count, "message": f"Inserted image on {count} page(s)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


# Serve frontend static files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
