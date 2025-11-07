import streamlit as st
import pandas as pd
from io import BytesIO
from docx import Document
import tempfile
import os
import subprocess
import re
import nltk

# Tải bộ tách câu (nếu chưa có)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

# ==========================
# ⚙️ CẤU HÌNH GIAO DIỆN
# ==========================
st.set_page_config(page_title="📘 Tra cứu Văn bản Word", page_icon="📄", layout="wide")
st.title("📘 ỨNG DỤNG TRA CỨU NỘI DUNG VĂN BẢN WORD")
st.markdown("📂 **Bên trái:** Tải file DOC/DOCX — 💬 **Bên phải:** Nhập từ khóa để tìm kiếm nội dung.")

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
st.markdown("""
<style>
div[data-testid="column"]:first-child { margin-right: 60px !important; }
.highlight-red { color: red; font-weight: bold; }
.text-block { white-space: pre-wrap; font-family: 'Times New Roman', serif; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ==========================
# 📂 HÀM ĐỌC FILE DOC/DOCX
# ==========================
def read_text_from_file(file):
    """Đọc nội dung từ file DOC hoặc DOCX"""
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
            except Exception as e:
                st.error(f"❌ Không thể đọc file DOC ({file.name}): {e}")
            finally:
                for path in [tmp_doc_path, tmp_docx_path]:
                    if os.path.exists(path):
                        os.remove(path)
        else:
            st.warning("⚠️ Chỉ hỗ trợ file DOC hoặc DOCX.")
    except Exception as e:
        st.error(f"❌ Lỗi đọc file {file.name}: {e}")

    return text.strip()

# ==========================
# 🔍 HÀM TÌM KIẾM NGẮT CÂU ĐỦ Ý
# ==========================
def tim_trong_van_ban(keyword, dataframe):
    """Tìm đoạn văn có chứa từ khóa, ngắt câu đủ ý"""
    kw = keyword.strip().lower()
    results = []

    for _, row in dataframe.iterrows():
        sentences = nltk.sent_tokenize(row["NỘI_DUNG"])
        matched_blocks = []

        for i, sentence in enumerate(sentences):
            if kw in sentence.lower():
                # Mở rộng 1–3 câu tùy ngữ cảnh để đảm bảo đủ ý
                start = max(0, i - 2)
                end = min(len(sentences), i + 3)
                snippet = " ".join(sentences[start:end]).strip()
                matched_blocks.append(snippet)

        for block in matched_blocks:
            results.append({
                "TRICH_DOAN": block,
                "TÊN_FILE": row["TÊN_FILE"]
            })
    return pd.DataFrame(results)

# ==========================
# 🧭 2 CỘT GIAO DIỆN
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📁 CỘT TRÁI — TẢI FILE
# ==========================
with col1:
    st.subheader("📂 Tải file Word")

    uploaded_files = st.file_uploader(
        "Chọn file (.doc hoặc .docx, có thể nhiều)",
        type=["doc", "docx"],
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
        st.info("📌 Hãy tải ít nhất một file DOC/DOCX để bắt đầu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.markdown("""
    - Tải file **DOC hoặc DOCX** (có thể nhiều file cùng lúc).
    - Nhập **từ khóa** → nhấn **Enter** hoặc **🔍 Tìm kiếm**.
    - Ứng dụng hiển thị **đoạn văn chứa từ khóa**, mở rộng vài câu trước/sau để đủ ý.
    - Giữ nguyên **ngắt dòng, định dạng gốc**.
    - Cụm từ khóa được **bôi đỏ, in đậm** để dễ nhận biết.
    """)
