import streamlit as st
import pandas as pd
from io import StringIO
from tempfile import NamedTemporaryFile
import os

from pypdf import PdfReader
from docx import Document
import docx2txt
from PIL import Image
import easyocr

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="Chatbot Tra cứu Văn bản OCR", page_icon="📜", layout="wide")
st.title("📜 Chatbot tra cứu Văn bản Quy định (có OCR)")
st.caption("💡 Hỗ trợ PDF (văn bản + scan ảnh), DOCX, DOC, TXT")

# ==========================
# 🧠 Bộ nhớ session
# ==========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}

# ==========================
# 🔤 OCR - EasyOCR
# ==========================
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(["vi", "en"], gpu=False)

ocr_reader = get_ocr_reader()

# ==========================
# 📖 Hàm đọc nội dung file
# ==========================
def extract_text(file):
    """Đọc nội dung từ PDF (văn bản hoặc scan), DOCX, DOC, TXT"""
    name = file.name.lower()
    text = ""

    try:
        if name.endswith(".pdf"):
            text = extract_text_from_pdf(file)

        elif name.endswith(".docx"):
            doc = Document(file)
            text = "\n".join(p.text for p in doc.paragraphs)

        elif name.endswith(".doc"):
            with NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
                tmp.write(file.getvalue())
                tmp.flush()
                text = docx2txt.process(tmp.name) or ""
                os.remove(tmp.name)

        elif name.endswith(".txt"):
            text = file.getvalue().decode("utf-8", errors="ignore")

        else:
            st.warning(f"⚠️ Định dạng không hỗ trợ: {file.name}")

    except Exception as e:
        st.error(f"❌ Lỗi đọc file {file.name}: {e}")

    return text.strip()


def extract_text_from_pdf(file):
    """Thử đọc PDF text, nếu không có thì dùng OCR"""
    try:
        reader = PdfReader(file)
        pages_text = []
        ocr_used = False
        for i, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt and txt.strip():
                pages_text.append(txt)
            else:
                # OCR fallback
                ocr_used = True
                img = page_to_image(file, i)
                if img:
                    ocr_text = ocr_reader.readtext(img, detail=0, paragraph=True)
                    pages_text.append("\n".join(ocr_text))
        if ocr_used:
            st.info("📸 Một số trang PDF được đọc bằng OCR (ảnh scan).")
        return "\n".join(pages_text)

    except Exception as e:
        st.error(f"❌ Lỗi đọc PDF: {e}")
        return ""


def page_to_image(file, page_num):
    """Chuyển trang PDF sang ảnh để OCR"""
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(file.getvalue(), first_page=page_num + 1, last_page=page_num + 1)
        return images[0]
    except Exception:
        return None


# ==========================
# 🧭 Giao diện
# ==========================
col1, col2 = st.columns([1, 2])

# === CỘT TRÁI: TẢI FILE ===
with col1:
    st.subheader("📂 Tải file văn bản (PDF, DOCX, DOC, TXT)")
    uploaded_files = st.file_uploader(
        "Chọn file (có thể nhiều)",
        type=["pdf", "docx", "doc", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                text = extract_text(file)
                if text:
                    st.session_state.uploaded_files[file.name] = text
        st.success(f"✅ Đã tải {len(st.session_state.uploaded_files)} file.")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file"):
            st.session_state.uploaded_files.clear()
            st.rerun()

# === CỘT PHẢI: TRA CỨU ===
with col2:
    st.subheader("🔎 Tìm kiếm trong văn bản")

    if not st.session_state.uploaded_files:
        st.info("📌 Vui lòng tải file trước khi tìm kiếm.")
    else:
        keyword = st.text_input("Nhập từ khóa cần tìm (ví dụ: xử phạt, hợp đồng lao động...)")

        if keyword:
            results = []
            for fname, text in st.session_state.uploaded_files.items():
                text_lower = text.lower()
                kw_lower = keyword.lower()
                idx = text_lower.find(kw_lower)
                while idx != -1:
                    start = max(0, idx - 200)
                    end = min(len(text), idx + len(keyword) + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    results.append((fname, snippet))
                    idx = text_lower.find(kw_lower, idx + len(keyword))

            if not results:
                st.warning("❌ Không tìm thấy kết quả.")
            else:
                st.success(f"🔍 Tìm thấy {len(results)} kết quả.")
                for fname, snippet in results[:50]:
                    highlight = snippet.replace(keyword, f"**:orange[{keyword}]**")
                    st.markdown(f"**📜 Trích đoạn:** {highlight}")
                    st.caption(f"📁 Nguồn: {fname}")
                    st.divider()

# === HƯỚNG DẪN ===
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("- Hỗ trợ **PDF thường, PDF scan, DOCX, DOC, TXT**.")
    st.write("- Nếu PDF là **ảnh scan**, hệ thống tự dùng OCR để nhận dạng.")
    st.write("- Nhập từ khóa → hiển thị đoạn văn có chứa từ khóa và nguồn file.")
    st.write("- Ví dụ: nhập “xử phạt” để tìm nội dung tương ứng trong các file đã tải.")
