import streamlit as st
import pandas as pd
from io import StringIO
from pdf2image import convert_from_bytes
from pypdf import PdfReader
from PIL import Image
from docx import Document
import docx2txt
import pytesseract
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="Chatbot tra cứu Văn bản", page_icon="📜", layout="wide")
st.title("📜 Chatbot tra cứu Văn bản Quy định")
st.markdown("📂 **Trái:** Tải file văn bản — 💬 **Phải:** Tra cứu nội dung chứa từ khóa.")

# ==========================
# 🧠 Session State
# ==========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================
# 📏 Căn lề
# ==========================
st.markdown("""
<style>
div[data-testid="column"]:first-child { margin-right: 60px !important; }
</style>
""", unsafe_allow_html=True)

# ==========================
# 📚 Hàm đọc file
# ==========================
@st.cache_data(show_spinner=False)
def read_text_from_file(file_bytes, filename):
    """Đọc nhanh nội dung từ PDF (text hoặc scan), DOC, DOCX, TXT"""
    text = ""
    name = filename.lower()

    try:
        if name.endswith(".pdf"):
            reader = PdfReader(file_bytes)
            # Thử đọc text trước
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
            text = text.strip()
            # Nếu PDF không có text → dùng OCR
            if len(text) < 20:
                st.info(f"🔍 Đang OCR file scan: {filename}")
                images = convert_from_bytes(file_bytes, dpi=200, fmt="png")
                with ThreadPoolExecutor() as ex:
                    ocr_texts = list(ex.map(lambda img: pytesseract.image_to_string(img, lang="vie+eng"), images))
                text = "\n".join(ocr_texts)

        elif name.endswith(".docx"):
            doc = Document(file_bytes)
            text = "\n".join([p.text for p in doc.paragraphs])

        elif name.endswith(".doc"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            text = docx2txt.process(tmp_path)
            os.unlink(tmp_path)

        elif name.endswith(".txt"):
            stringio = StringIO(file_bytes.decode("utf-8", errors="ignore"))
            text = stringio.read()

        else:
            st.warning(f"⚠️ Định dạng {filename} không được hỗ trợ.")
            return ""

    except Exception as e:
        st.error(f"❌ Lỗi đọc file {filename}: {e}")

    return text.strip()


# ==========================
# 🧭 Giao diện 2 cột
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📂 CỘT TRÁI: TẢI FILE
# ==========================
with col1:
    st.subheader("📂 Tải file văn bản")
    uploaded_files = st.file_uploader(
        "Chọn file (PDF, DOC, DOCX, TXT, có thể nhiều)",
        type=["pdf", "doc", "docx", "txt"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                text_content = read_text_from_file(file.read(), file.name)
                df = pd.DataFrame({"NỘI DUNG": [text_content], "SOURCE_FILE": [file.name]})
                st.session_state.uploaded_files[file.name] = df

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file đã tải"):
            st.session_state.uploaded_files.clear()
            st.session_state.uploader_key += 1
            st.rerun()

# ==========================
# 💬 CỘT PHẢI: TRA CỨU
# ==========================
with col2:
    st.subheader("💬 Tra cứu nội dung văn bản")

    if st.session_state.uploaded_files:
        combined_df = pd.concat(st.session_state.uploaded_files.values(), ignore_index=True)
        user_input = st.text_input("🔎 Nhập từ khóa cần tìm (ví dụ: xử phạt hành chính, hợp đồng...)")
        search_btn = st.button("Tìm kiếm")

        if user_input or search_btn:
            kw = user_input.lower().strip()
            results = []
            for _, row in combined_df.iterrows():
                text = row["NỘI DUNG"].lower()
                if kw in text:
                    idx = text.find(kw)
                    start = max(0, idx - 150)
                    end = min(len(text), idx + 150)
                    snippet = row["NỘI DUNG"][start:end].replace("\n", " ").strip()
                    results.append({"TRÍCH ĐOẠN": snippet, "SOURCE_FILE": row["SOURCE_FILE"]})

            if results:
                for r in results:
                    highlighted = r["TRÍCH ĐOẠN"].replace(user_input, f"**:orange[{user_input}]**")
                    st.markdown(f"**📜 Trích đoạn:** {highlighted}")
                    st.caption(f"📁 Nguồn: *{r['SOURCE_FILE']}*")
                    st.divider()
            else:
                st.warning("❌ Không tìm thấy nội dung phù hợp.")
    else:
        st.info("📌 Hãy tải ít nhất một file trước khi tra cứu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("- Có thể tải nhiều file định dạng **PDF, DOC, DOCX, hoặc TXT**.")
    st.write("- Hệ thống tự động nhận dạng nội dung trong file scan.")
    st.write("- Khi nhập từ khóa, chương trình hiển thị đoạn có chứa từ đó và tên file gốc.")
