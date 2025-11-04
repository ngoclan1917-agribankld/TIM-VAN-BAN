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

# =================================
# ⚙️ Cấu hình giao diện
# =================================
st.set_page_config(page_title="🔎 Tra cứu văn bản", layout="wide")
st.title("🔎 Tra cứu nội dung tài liệu (PDF, DOCX, TXT, Ảnh)")
st.markdown("Ứng dụng hỗ trợ cả **PDF scan**, **ảnh chụp**, và **file Word, text**.")

# =================================
# 🧭 Bố cục 2 cột
# =================================
col1, col2 = st.columns([1, 2])

# =================================
# 📂 CỘT TRÁI — TẢI FILE
# =================================
with col1:
    st.subheader("📁 Tải tệp")
    files = st.file_uploader(
        "Chọn tệp (PDF, DOCX, TXT, PNG, JPG, JPEG, TIFF)",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True,
    )

    if "data_store" not in st.session_state:
        st.session_state.data_store = {}

    def extract_text_from_pdf(file_bytes):
        """Đọc PDF — kết hợp pdfplumber + OCR fallback"""
        text = ""
        with pdfplumber.open(file_bytes) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if not text.strip():
            # Nếu không có text thì OCR
            images = convert_from_bytes(file_bytes.getvalue())
            for img in images:
                text += pytesseract.image_to_string(img, lang="vie")

        return text.strip()

    def extract_text_from_file(uploaded_file):
        ext = uploaded_file.name.lower().split(".")[-1]
        text = ""
        try:
            if ext == "pdf":
                bytes_data = BytesIO(uploaded_file.read())
                text = extract_text_from_pdf(bytes_data)

            elif ext == "docx":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                doc = Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs)

            elif ext == "txt":
                raw = uploaded_file.read()
                enc = chardet.detect(raw)["encoding"] or "utf-8"
                text = raw.decode(enc, errors="ignore")

            elif ext in ["png", "jpg", "jpeg", "tiff"]:
                img = Image.open(uploaded_file)
                text = pytesseract.image_to_string(img, lang="vie")

        except Exception as e:
            st.error(f"❌ Lỗi khi đọc {uploaded_file.name}: {e}")
        return text

    if files:
        for f in files:
            if f.name not in st.session_state.data_store:
                content = extract_text_from_file(f)
                if content:
                    st.session_state.data_store[f.name] = content
                    st.success(f"✅ Đã xử lý: {f.name}")
                else:
                    st.warning(f"⚠️ Không đọc được nội dung từ {f.name}")

    if st.session_state.data_store:
        if st.button("🧹 Xóa tất cả file"):
            st.session_state.data_store.clear()
            st.rerun()

# =================================
# 🔍 CỘT PHẢI — TÌM KIẾM
# =================================
with col2:
    st.subheader("🔍 Tìm kiếm nội dung")
    keyword = st.text_input("Nhập từ khóa:")
    if st.button("Tìm"):
        results = []
        for fname, text in st.session_state.data_store.items():
            if keyword.lower() in text.lower():
                idx = text.lower().find(keyword.lower())
                snippet = text[max(0, idx-100): idx+200].replace("\n", " ")
                results.append((fname, snippet))

        if results:
            st.success(f"Tìm thấy {len(results)} kết quả:")
            for fname, snippet in results:
                st.markdown(f"**📄 {fname}:** ...{snippet.replace(keyword, f'**🟠{keyword}**')}...")
                st.divider()
        else:
            st.warning("Không tìm thấy từ khóa trong tài liệu.")

# =================================
# 📘 HƯỚNG DẪN
# =================================
with st.expander("📘 Hướng dẫn"):
    st.markdown("""
    - Tải các file PDF (gốc hoặc scan), DOCX, TXT hoặc ảnh.
    - Ứng dụng tự nhận dạng text và OCR khi cần.
    - Hỗ trợ tiếng Việt (cần có gói `tesseract-ocr-vie` trong `packages.txt`).
    """)
