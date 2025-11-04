import streamlit as st
import pandas as pd
from PIL import Image
from pdf2image import convert_from_bytes
import pdfplumber
from docx import Document
import pytesseract
import chardet
from io import BytesIO
import tempfile
import os

# ==============================
# ⚙️ Cấu hình giao diện
# ==============================
st.set_page_config(page_title="📚 Tra cứu văn bản", layout="wide")
st.title("📚 Ứng dụng tra cứu nội dung văn bản (PDF, Word, TXT, Ảnh)")
st.markdown("Hỗ trợ cả **PDF scan**, **ảnh chụp**, và **file văn bản**.")

# ==============================
# 🧭 Bố cục 2 cột
# ==============================
col1, col2 = st.columns([1, 2])

# ==============================
# 📂 CỘT TRÁI — TẢI FILE
# ==============================
with col1:
    st.subheader("📂 Tải file văn bản")
    files = st.file_uploader(
        "Chọn tệp (PDF, DOCX, TXT, PNG, JPG, JPEG, TIFF)",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True,
    )

    if "data_store" not in st.session_state:
        st.session_state.data_store = {}

    def read_file(file):
        ext = file.name.lower().split(".")[-1]
        text = ""
        try:
            if ext == "pdf":
                file_bytes = BytesIO(file.read())
                # Thử đọc PDF có text
                with pdfplumber.open(file_bytes) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                # Nếu không có text -> OCR
                if not text.strip():
                    images = convert_from_bytes(file_bytes.getvalue())
                    for img in images:
                        text += pytesseract.image_to_string(img)

            elif ext == "docx":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                doc = Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs)

            elif ext == "txt":
                raw = file.read()
                enc = chardet.detect(raw)["encoding"] or "utf-8"
                text = raw.decode(enc, errors="ignore")

            elif ext in ["png", "jpg", "jpeg", "tiff"]:
                img = Image.open(file)
                text = pytesseract.image_to_string(img)

        except Exception as e:
            st.error(f"Lỗi khi đọc {file.name}: {e}")
        return text.strip()

    if files:
        for f in files:
            if f.name not in st.session_state.data_store:
                content = read_file(f)
                if content:
                    st.session_state.data_store[f.name] = content
                    st.success(f"✅ Đã xử lý: {f.name}")

    if st.session_state.data_store:
        if st.button("🧹 Xóa tất cả file"):
            st.session_state.data_store.clear()
            st.rerun()

# ==============================
# 💬 CỘT PHẢI — TRA CỨU
# ==============================
with col2:
    st.subheader("🔍 Tra cứu nội dung")
    keyword = st.text_input("Nhập từ khóa cần tìm:")
    if st.button("Tìm kiếm") and keyword:
        results = []
        for fname, text in st.session_state.data_store.items():
            if keyword.lower() in text.lower():
                idx = text.lower().find(keyword.lower())
                start = max(0, idx - 150)
                end = min(len(text), idx + 150)
                snippet = text[start:end].replace("\n", " ")
                results.append((fname, snippet))

        if results:
            st.success(f"Tìm thấy {len(results)} kết quả:")
            for fname, snippet in results:
                highlight = snippet.replace(keyword, f"**:orange[{keyword}]**")
                st.markdown(f"📁 **{fname}**: {highlight}")
                st.divider()
        else:
            st.warning("Không tìm thấy từ khóa trong các file.")

# ==============================
# 📘 HƯỚNG DẪN
# ==============================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("""
    - Tải các tệp PDF, DOCX, TXT, hoặc ảnh (JPG, PNG, TIFF).
    - Hệ thống sẽ tự động nhận dạng chữ bằng OCR nếu cần.
    - Nhập từ khóa để tìm đoạn chứa từ đó trong các tài liệu.
    """)
