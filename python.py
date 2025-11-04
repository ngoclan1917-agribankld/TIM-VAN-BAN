import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
import pdfplumber
from docx import Document
import textract
import tempfile

# =========================
# ⚙️ Cấu hình giao diện
# =========================
st.set_page_config(page_title="📚 Tra cứu văn bản thông minh", layout="wide")
st.title("📚 Ứng dụng tra cứu nội dung văn bản")
st.markdown("Hỗ trợ đọc và tìm kiếm trong **PDF (scan/text)**, **Word (DOC, DOCX)**, **TXT**, **hình ảnh (JPG, PNG, TIFF)**.")

# =========================
# 🧠 Quản lý trạng thái
# =========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}

# =========================
# 🧭 Giao diện 2 cột
# =========================
col1, col2 = st.columns([1, 2])

# =========================
# 📂 CỘT TRÁI: TẢI FILE
# =========================
with col1:
    st.subheader("📂 Tải file văn bản")
    uploaded_files = st.file_uploader(
        "Chọn tệp (PDF, DOC, DOCX, TXT, PNG, JPG, TIFF)",
        type=["pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True
    )

    # --------- HÀM ĐỌC FILE ---------
    def extract_text(file):
        ext = file.name.lower().split(".")[-1]
        text = ""

        try:
            # --- PDF (Text hoặc Scan) ---
            if ext == "pdf":
                file_bytes = BytesIO(file.read())
                try:
                    with pdfplumber.open(file_bytes) as pdf:
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                except Exception:
                    # OCR fallback cho PDF scan
                    images = convert_from_bytes(file_bytes.getvalue())
                    for img in images:
                        text += pytesseract.image_to_string(img)

            # --- DOC hoặc DOCX ---
            elif ext in ["doc", "docx"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                if ext == "docx":
                    doc = Document(tmp_path)
                    text = "\n".join(p.text for p in doc.paragraphs)
                else:
                    text = textract.process(tmp_path).decode("utf-8", errors="ignore")

            # --- TXT ---
            elif ext == "txt":
                text = file.read().decode("utf-8", errors="ignore")

            # --- Ảnh (JPG, PNG, TIFF) ---
            elif ext in ["jpg", "jpeg", "png", "tiff"]:
                img = Image.open(file)
                text = pytesseract.image_to_string(img)

        except Exception as e:
            st.error(f"❌ Lỗi khi đọc file {file.name}: {e}")
        return text.strip()

    # --------- ĐỌC & LƯU FILE ---------
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                content = extract_text(file)
                if content:
                    st.session_state.uploaded_files[file.name] = content
                    st.success(f"✅ Đã xử lý: {file.name}")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file"):
            st.session_state.uploaded_files.clear()
            st.rerun()

# =========================
# 💬 CỘT PHẢI: TRA CỨU
# =========================
with col2:
    st.subheader("💬 Tra cứu nội dung văn bản")
    query = st.text_input("🔎 Nhập từ khóa hoặc cụm từ cần tìm:")
    search_btn = st.button("Tìm kiếm")

    if search_btn and query:
        if not st.session_state.uploaded_files:
            st.warning("📌 Hãy tải ít nhất một file trước khi tìm kiếm.")
        else:
            results = []
            for fname, content in st.session_state.uploaded_files.items():
                if query.lower() in content.lower():
                    idx = content.lower().find(query.lower())
                    start = max(0, idx - 150)
                    end = min(len(content), idx + 150)
                    snippet = content[start:end].replace("\n", " ").strip()
                    results.append({"SOURCE_FILE": fname, "TRICH_DOAN": snippet})

            if results:
                st.success(f"✅ Tìm thấy {len(results)} kết quả chứa **'{query}'**.")
                for r in results:
                    highlighted = r["TRICH_DOAN"].replace(
                        query, f"**:orange[{query}]**"
                    )
                    st.markdown(f"**📜 Trích đoạn:** {highlighted}")
                    st.caption(f"📁 Nguồn: *{r['SOURCE_FILE']}*")
                    st.divider()
            else:
                st.warning("❌ Không tìm thấy nội dung phù hợp.")

# =========================
# 📘 HƯỚNG DẪN
# =========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("""
    - Tải nhiều tệp định dạng **PDF, DOC, DOCX, TXT, PNG, JPG, TIFF**.
    - Hệ thống tự nhận dạng chữ trong **PDF scan / ảnh (OCR)**.
    - Nhập từ khóa cần tìm để trích xuất đoạn có chứa cụm từ đó.
    - Có thể xóa tất cả file đã tải bằng nút 🧹.
    """)
