import streamlit as st
import pandas as pd
from io import StringIO
from PIL import Image
import pytesseract
import tempfile
import os
from pdf2image import convert_from_bytes
from docx import Document
import docx2txt

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="Chatbot Tra cứu Văn bản", page_icon="📜", layout="wide")
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
st.markdown(
    """
    <style>
    div[data-testid="column"]:first-child {
        margin-right: 60px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# 📂 Đọc nội dung file
# ==========================
def read_text_from_file(file):
    """Đọc nội dung từ file PDF (kể cả scan), DOC, DOCX, TXT"""
    text = ""

    filename = file.name.lower()

    if filename.endswith(".pdf"):
        try:
            # Dùng pdf2image + pytesseract để đọc cả file scan
            with tempfile.TemporaryDirectory() as path:
                images = convert_from_bytes(file.read(), dpi=300, fmt="png")
                for img in images:
                    text += pytesseract.image_to_string(img, lang="vie+eng") + "\n"
        except Exception as e:
            st.error(f"❌ Lỗi khi đọc PDF: {e}")

    elif filename.endswith(".docx"):
        try:
            doc = Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            st.error(f"❌ Không thể đọc DOCX: {e}")

    elif filename.endswith(".doc"):
        try:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".doc")
            temp.write(file.read())
            temp.close()
            text = docx2txt.process(temp.name)
            os.unlink(temp.name)
        except Exception as e:
            st.error(f"❌ Không thể đọc DOC: {e}")

    elif filename.endswith(".txt"):
        try:
            stringio = StringIO(file.getvalue().decode("utf-8", errors="ignore"))
            text = stringio.read()
        except Exception:
            st.error(f"❌ Lỗi khi đọc file TXT: {file.name}")

    else:
        st.error("❌ Định dạng file không hỗ trợ. Vui lòng tải PDF, DOC, DOCX hoặc TXT.")
        return ""

    return text.strip()

# ==========================
# 🧭 GIAO DIỆN 2 CỘT
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
                text = read_text_from_file(file)
                df = pd.DataFrame({"NỘI DUNG": [text], "SOURCE_FILE": [file.name]})
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
    st.subheader("💬 Chatbot tra cứu nội dung")

    if st.session_state.uploaded_files:
        combined_df = pd.concat(st.session_state.uploaded_files.values(), ignore_index=True)
        user_input = st.text_input("🔎 Nhập từ khóa cần tìm (ví dụ: xử phạt hành chính, hợp đồng...)")
        search_btn = st.button("Tìm kiếm")

        if user_input or search_btn:
            keyword = user_input.strip().lower()
            results = []

            for _, row in combined_df.iterrows():
                text = row["NỘI DUNG"].lower()
                file_name = row["SOURCE_FILE"]
                if keyword in text:
                    idx = text.find(keyword)
                    start = max(0, idx - 200)
                    end = min(len(text), idx + 200)
                    snippet = row["NỘI DUNG"][start:end].replace("\n", " ").strip()
                    results.append({"TRÍCH ĐOẠN": snippet, "SOURCE_FILE": file_name})

            if results:
                for r in results:
                    highlighted = r["TRÍCH ĐOẠN"].replace(
                        user_input, f"**:orange[{user_input}]**"
                    )
                    st.markdown(f"**📜 Trích đoạn:** {highlighted}")
                    st.caption(f"📁 Nguồn: *{r['SOURCE_FILE']}*")
                    st.divider()
            else:
                st.warning("❌ Không tìm thấy nội dung nào phù hợp.")
    else:
        st.info("📌 Vui lòng tải ít nhất một file văn bản trước khi tra cứu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("- Có thể tải nhiều file định dạng **PDF, DOC, DOCX hoặc TXT**.")
    st.write("- Ứng dụng tự động nhận dạng văn bản trong file scan hoặc ảnh PDF.")
    st.write("- Khi nhập từ khóa, chương trình hiển thị đoạn có chứa từ đó và tên file nguồn.")
