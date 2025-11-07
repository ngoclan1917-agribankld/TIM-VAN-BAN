import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
from docx import Document
import chardet
import re
import tempfile
import os
import subprocess
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import nltk

# ==========================
# ⚙️ TẢI BỘ TÁCH CÂU CHO NLTK
# ==========================
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

# ==========================
# ⚙️ CẤU HÌNH GIAO DIỆN
# ==========================
st.set_page_config(page_title="📜 Tra cứu Văn bản Quy định", page_icon="📘", layout="wide")
st.title("📜 ỨNG DỤNG TRA CỨU NỘI DUNG VĂN BẢN QUY ĐỊNH")
st.markdown("📂 **Bên trái:** Tải file văn bản — 💬 **Bên phải:** Nhập từ khóa để tìm kiếm nội dung liên quan.")

# ==========================
# 🧠 SESSION STATE
# ==========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================
# 🎨 CSS TÙY CHỈNH
# ==========================
st.markdown(
    """
    <style>
    div[data-testid="column"]:first-child { margin-right: 60px !important; }
    .highlight-red { color: red; font-weight: bold; }
    .text-block { white-space: pre-wrap; font-family: 'Times New Roman', serif; line-height: 1.6; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# 📂 HÀM ĐỌC FILE
# ==========================
def read_text_from_file(file):
    """Đọc nội dung từ DOC/DOCX/TXT/PDF/ẢNH và giữ ngắt dòng"""
    text = ""
    ext = file.name.lower().split(".")[-1]

    try:
        if ext == "docx":
            doc = Document(file)
            text = "\n".join(p.text for p in doc.paragraphs)

        elif ext == "doc":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp_doc:
                tmp_doc.write(file.read())
                tmp_doc_path = tmp_doc.name
            tmp_docx_path = tmp_doc_path + "x"
            try:
                subprocess.run(
                    ["soffice", "--headless", "--convert-to", "docx",
                     "--outdir", os.path.dirname(tmp_docx_path), tmp_doc_path],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                doc = Document(tmp_docx_path)
                text = "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                st.error("❌ Không thể đọc file DOC. Cần cài LibreOffice (soffice).")
            finally:
                for path in [tmp_doc_path, tmp_docx_path]:
                    if os.path.exists(path):
                        os.remove(path)

        elif ext == "txt":
            raw = file.read()
            enc = chardet.detect(raw)["encoding"] or "utf-8"
            stringio = StringIO(raw.decode(enc, errors="ignore"))
            text = stringio.read()

        elif ext == "pdf":
            file_bytes = BytesIO(file.read())
            text = extract_text_from_pdf(file_bytes)

        elif ext in ["png", "jpg", "jpeg", "tiff"]:
            img = Image.open(file)
            text = pytesseract.image_to_string(img, lang="vie+eng")

        else:
            st.warning(f"⚠️ Định dạng {ext} chưa được hỗ trợ.")
    except Exception as e:
        st.error(f"❌ Lỗi đọc file {file.name}: {e}")

    return text.strip()


def extract_text_from_pdf(file_bytes):
    """Đọc PDF (ưu tiên text, fallback OCR nếu scan)"""
    text = ""
    try:
        with pdfplumber.open(file_bytes) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=1, y_tolerance=1)
                if page_text:
                    text += page_text + "\n\n"
    except Exception:
        pass

    if not text.strip():
        try:
            images = convert_from_bytes(file_bytes.getvalue())
            for img in images:
                text += pytesseract.image_to_string(img, lang="vie+eng") + "\n\n"
        except Exception as e:
            st.error(f"❌ Lỗi OCR PDF: {e}")

    return text.strip()

# ==========================
# 💬 HÀM TÌM KIẾM NỘI DUNG
# ==========================
def tim_trong_van_ban(keyword, dataframe):
    """Tìm đoạn văn chứa từ khóa, mở rộng ngữ cảnh đủ ý"""
    kw = keyword.strip().lower()
    results = []

    for _, row in dataframe.iterrows():
        sentences = nltk.sent_tokenize(row["NỘI_DUNG"])
        matched_blocks = []

        for i, sentence in enumerate(sentences):
            if kw in sentence.lower():
                # Mở rộng linh hoạt 1–3 câu tùy độ dài đoạn
                start = max(0, i - 2)
                end = min(len(sentences), i + 3)
                snippet = " ".join(sentences[start:end]).strip()
                matched_blocks.append(snippet)

        for block in matched_blocks:
            results.append({"TRICH_DOAN": block, "TÊN_FILE": row["TÊN_FILE"]})

    return pd.DataFrame(results)

# ==========================
# 🧭 2 CỘT GIAO DIỆN
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📁 CỘT TRÁI — TẢI FILE
# ==========================
with col1:
    st.subheader("📂 Tải file văn bản")

    uploaded_files = st.file_uploader(
        "Chọn file (PDF, DOC, DOCX, TXT, Ảnh)",
        type=["pdf", "docx", "doc", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                text_content = read_text_from_file(file)
                if text_content:
                    df = pd.DataFrame({"NỘI_DUNG": [text_content], "TÊN_FILE": [file.name]})
                    st.session_state.uploaded_files[file.name] = df
                    st.success(f"✅ Đã tải: {file.name}")
                else:
                    st.warning(f"⚠️ Không thể trích xuất nội dung từ: {file.name}")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file"):
            st.session_state.uploaded_files.clear()
            st.session_state.uploader_key += 1
            st.rerun()

# ==========================
# 💬 CỘT PHẢI — TRA CỨU
# ==========================
with col2:
    st.subheader("💬 Tra cứu nội dung")

    if st.session_state.uploaded_files:
        combined_df = pd.concat(st.session_state.uploaded_files.values(), ignore_index=True)

        user_input = st.text_input("🔎 Nhập từ khóa cần tìm (Enter hoặc nhấn nút):", key="search_input")
        search_btn = st.button("🔍 Tìm kiếm")

        if (user_input and st.session_state.search_input) or search_btn:
            keyword = user_input.strip()
            if keyword:
                results = tim_trong_van_ban(keyword, combined_df)
                if results.empty:
                    st.warning("❌ Không tìm thấy nội dung nào phù hợp.")
                else:
                    for _, row in results.iterrows():
                        highlighted = re.sub(
                            fr"({re.escape(keyword)})",
                            r'<span class="highlight-red">\1</span>',
                            row["TRICH_DOAN"],
                            flags=re.IGNORECASE
                        )
                        st.markdown(f'<div class="text-block">{highlighted}</div>', unsafe_allow_html=True)
                        st.caption(f"📁 Nguồn: *{row['TÊN_FILE']}*")
                        st.divider()
            else:
                st.info("⚠️ Nhập từ khóa để tìm kiếm.")
    else:
        st.info("📌 Hãy tải ít nhất một file văn bản để bắt đầu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.markdown("""
    - Tải file **PDF (kể cả scan)**, **DOC/DOCX**, **TXT** hoặc **ảnh (PNG/JPG)**.
    - Nhập từ khóa → nhấn **Enter** hoặc **🔍 Tìm kiếm**.
    - Ứng dụng hiển thị **đoạn văn chứa từ khóa**, mở rộng linh hoạt để đủ ý.
    - Giữ **ngắt dòng và bố cục gốc**.
    - Cụm từ khóa được **bôi đỏ, đậm** để dễ nhận biết.
    """)
