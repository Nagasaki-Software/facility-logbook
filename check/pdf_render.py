import io
import os
import pypdfium2 as pdfium  # PDFium（Apache-2.0 / BSD-3-Clause）

def _open(form_path):
    if not os.path.exists(form_path):
        raise FileNotFoundError(f"様式PDFがありません: {form_path}")
    return pdfium.PdfDocument(form_path)

def page_count(form_path):
    doc = _open(form_path)
    try:
        return len(doc)
    finally:
        doc.close()

def page_sizes(form_path):
    doc = _open(form_path)
    try:
        out = []
        for i in range(len(doc)):
            w, h = doc[i].get_size()
            out.append({"page": i, "w_pt": float(w), "h_pt": float(h)})
        return out
    finally:
        doc.close()

def render_page_png(form_path, page_no=0, zoom=2.0):
    doc = _open(form_path)
    try:
        page = doc[page_no]
        w, h = page.get_size()
        img = page.render(scale=zoom).to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {
            "png": buf.getvalue(),
            "page_w_pt": float(w),
            "page_h_pt": float(h),
            "img_w_px": int(img.width),
            "img_h_px": int(img.height),
        }
    finally:
        doc.close()
