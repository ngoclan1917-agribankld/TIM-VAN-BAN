import streamlit as st
import pandas as pd
from io import StringIO
import pdfplumber
from docx import Document
from PIL import Image
import pytesseract
import textract
import tempfile
import os

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="Chatbot Tra cứu Văn bản", page_icon="📜", layout="wide")
st.title("📜 Chatbot tra cứu Văn bản Quy định (PDF / DOC / DOCX / Ảnh / TXT)")
st.markdown("📂 **Trái:** Tải các file văn bản hoặc hình ảnh — 💬 **Phải:** Tra cứu nội dung chứa từ khóa.")

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
# 🧭 GIAO DIỆN 2 CỘT
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📂 CỘT TRÁI: TẢI FILE
# ==========================
with col1:
    st.subheader("📂 Tải file văn bản hoặc hình ảnh")

    def read_text_from_file(file):
        """Đọc nội dung từ PDF (text hoặc scan), DOC, DOCX, TXT, hoặc hình ảnh"""
        text = ""
        fname = file.name.lower()

        try:
            # ===== PDF =====
            if fname.endswith(".pdf"):
                with pdfplumber.open(file) as pdf:
                    text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                # Nếu không có text (PDF scan)
                if not text.strip():
                    st.warning(f"⚠️ {file.name} có thể là file scan — đang nhận dạng bằng OCR...")
                    with pdfplumber.open(file) as pdf:
                        for page in pdf.pages:
                            img = page.to_image(resolution=300).original
                            text += pytesseract.image_to_string(img, lang="vie+eng") + "\n"

            # ===== DOCX =====
            elif fname.endswith(".docx"):
                doc = Document(file)
                text = "\n".join([p.text for p in doc.paragraphs])

            # ===== DOC =====
            elif fname.endswith(".doc"):
                # Lưu file tạm để textract đọc
                with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                try:
                    text = textract.process(tmp_path).decode("utf-8", errors="ignore")
                except Exception as e:
                    st.error(f"Lỗi đọc file .doc ({file.name}): {e}")
                finally:
                    os.remove(tmp_path)

            # ===== TXT =====
            elif fname.endswith(".txt"):
                stringio = StringIO(file.getvalue().decode("utf-8", errors="ignore"))
                text = stringio.read()

            # ===== ẢNH =====
            elif fname.endswith((".jpg", ".jpeg", ".png")):
                image = Image.open(file)
                text = pytesseract.image_to_string(image, lang="vie+eng")

            else:
                raise ValueError("❌ Định dạng không hỗ trợ. Hãy tải PDF, DOC, DOCX, TXT, JPG hoặc PNG.")

        except Exception as e:
            st.error(f"❌ Lỗi đọc file {file.name}: {e}")

        return text.strip()

    uploaded_files = st.file_uploader(
        "Chọn file (PDF, DOC, DOCX, TXT, JPG, PNG — có thể nhiều)",
        type=["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                text_content = read_text_from_file(file)
                if text_content:
                    df = pd.DataFrame({"NỘI DUNG": [text_content], "SOURCE_FILE": [file.name]})
                    st.session_state.uploaded_files[file.name] = df
                else:
                    st.warning(f"⚠️ Không trích xuất được nội dung từ {file.name}")

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

        def tim_trong_van_ban(keyword, dataframe):
            kw = keyword.lower().strip()
            results = []
            for _, row in dataframe.iterrows():
                text = row["NỘI DUNG"]
                idx = text.lower().find(kw)
                while idx != -1:
                    start = max(0, idx - 200)
                    end = min(len(text), idx + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    results.append({"TRICH_DOAN": snippet, "SOURCE_FILE": row["SOURCE_FILE"]})
                    idx = text.lower().find(kw, idx + 1)
            return pd.DataFrame(results)

        if search_btn and user_input:
            results = tim_trong_van_ban(user_input, combined_df)
            if results.empty:
                st.warning("❌ Không tìm thấy nội dung nào phù hợp.")
            else:
                for _, row in results.iterrows():
                    highlighted = row["TRICH_DOAN"].replace(
                        user_input, f"**:orange[{user_input}]**"
                    )
                    st.markdown(f"**📜 Trích đoạn:** {highlighted}")
                    st.caption(f"📁 Nguồn: *{row['SOURCE_FILE']}*")
                    st.divider()
    else:
        st.info("📌 Vui lòng tải ít nhất một file trước khi tra cứu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("- Có thể tải nhiều file định dạng **PDF, DOC, DOCX, TXT, JPG, PNG**.")
    st.write("- Hệ thống tự động OCR nếu file là ảnh hoặc PDF scan.")
    st.write("- Nhập từ khóa để tìm đoạn văn liên quan trong các file đã tải lên.")
    st.write("- Ví dụ: nhập 'xử phạt' để tìm điều khoản có chứa từ này.")
