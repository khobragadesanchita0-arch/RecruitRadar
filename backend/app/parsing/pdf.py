import fitz  # PyMuPDF
from typing import Any, Dict, List, Tuple
from app.parsing.hidden_text import detect_unicode_hidden_chars, strip_hidden_unicode

def parse_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parses PDF bytes, extracting visible text and flagging hidden text
    (white-on-white, <2pt font, off-page coordinates, zero-width chars).
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Corrupt or unreadable PDF: {str(e)}")
        
    if doc.is_encrypted:
        raise ValueError("Password-protected or encrypted PDF")
        
    page_count = len(doc)
    if page_count > 15:
        raise ValueError(f"PDF exceeds 15 page limit ({page_count} pages)")
        
    visible_text_parts = []
    hidden_text_items = []
    
    for page_num in range(page_count):
        page = doc[page_num]
        rect = page.rect
        page_w = rect.width
        page_h = rect.height
        
        # Extract text blocks with span-level styling details
        page_dict = page.get_text("dict")
        
        for block in page_dict.get("blocks", []):
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue
                        
                    font_size = span.get("size", 12.0)
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    color_int = span.get("color", 0)  # integer sRGB
                    
                    # Convert color_int to RGB components
                    r = (color_int >> 16) & 255
                    g = (color_int >> 8) & 255
                    b = color_int & 255
                    is_white_text = (r > 240 and g > 240 and b > 240)
                    
                    x0, y0, x1, y1 = bbox
                    is_off_page = (x1 < 0 or y1 < 0 or x0 > page_w or y0 > page_h)
                    is_tiny_font = (font_size < 2.0)
                    
                    # Check unicode hidden characters
                    u_hidden = detect_unicode_hidden_chars(span_text)
                    if u_hidden:
                        hidden_text_items.extend(u_hidden)
                        
                    cleaned_span_text = strip_hidden_unicode(span_text)
                    
                    if is_tiny_font or is_white_text or is_off_page:
                        reason = []
                        if is_tiny_font:
                            reason.append(f"tiny_font_{font_size:.1f}pt")
                        if is_white_text:
                            reason.append("white_on_white")
                        if is_off_page:
                            reason.append("off_page_coords")
                            
                        hidden_text_items.append({
                            "text": cleaned_span_text,
                            "reason": ", ".join(reason),
                            "font_size": font_size,
                            "bbox": bbox,
                            "page": page_num + 1,
                        })
                    else:
                        visible_text_parts.append(cleaned_span_text)
                        
    full_visible_text = " ".join(visible_text_parts).strip()
    
    # Calculate parse confidence based on extracted text length and readability
    parse_confidence = 1.0
    if len(full_visible_text) < 100:
        parse_confidence = 0.4  # Scanned or empty PDF
    elif len(full_visible_text) < 300:
        parse_confidence = 0.7
        
    return {
        "visible_text": full_visible_text,
        "hidden_text_items": hidden_text_items,
        "page_count": page_count,
        "parse_confidence": parse_confidence,
    }
