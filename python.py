import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
from docx import Document
import chardet
import tempfile
import re
import os
import subprocess

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="📜 Tra cứu Văn bản", page_icon="📚", layout="wide")
st.title("📜 ỨNG DỤNG TRA CỨU NỘI DUNG VĂN BẢN QUY ĐỊNH")
st.markdown("📂 **Bên trái:** Tải file văn bản — 💬 **Bên phải:** Nhập từ khóa để tra cứu nhanh.")

# ==========================
# 🧠 Khởi tạo session
# ==========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================
# 📏 Căn chỉnh lề
# ==========================
st.markdown(
    """
    <style>
    div[data-testid="column"]:first-child {
        margin-right: 60px !important;
    }
    .highlight-red {
        color: red;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# 🧭 2 CỘT GIAO DIỆN
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📂 CỘT TRÁI: TẢI FILE
# ==========================
with col1:
    st.subheader("📂 Tải file văn bản (DOC, DOCX, TXT)")

    def read_text_from_file(file):
        """Đọc nội dung từ file DOC, DOCX hoặc TXT"""
        text = ""
        ext = file.name.lower().split(".")[-1]
        try:
            if ext == "docx":
                doc = Document(file)
                text = "\n".join([p.text for p in doc.paragraphs])
            elif ext == "doc":
                # Chuyển file .doc sang .docx tạm thời (cần libreoffice)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp_doc:
                    tmp_doc.write(file.read())
                    tmp_doc_path = tmp_doc.name
                tmp_docx_path = tmp_doc_path + "x"
                try:
                    subprocess.run(
                        ["soffice", "--headless", "--convert-to", "docx", "--outdir", os.path.dirname(tmp_docx_path), tmp_doc_path],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    doc = Document(tmp_docx_path)
                    text = "\n".join([p.text for p in doc.paragraphs])
                except Exception as e:
                    st.error("❌ Không thể đọc file DOC. Cần cài LibreOffice (soffice).")
                finally:
                    if os.path.exists(tmp_doc_path):
                        os.remove(tmp_doc_path)
                    if os.path.exists(tmp_docx_path):
                        os.remove(tmp_docx_path)
            elif ext == "txt":
                raw = file.read()
                enc = chardet.detect(raw)["encoding"] or "utf-8"
                stringio = StringIO(raw.decode(enc, errors="ignore"))
                text = stringio.read()
            else:
                st.warning("⚠️ Chỉ hỗ trợ DOC, DOCX hoặc TXT.")
        except Exception as e:
            st.error(f"❌ Lỗi đọc file {file.name}: {e}")
        return text.strip()

    uploaded_files = st.file_uploader(
        "Chọn file văn bản",
        type=["docx", "doc", "txt"],
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
                    st.warning(f"⚠️ Không đọc được nội dung: {file.name}")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file đã tải"):
            st.session_state.uploaded_files.clear()
            st.session_state.uploader_key += 1
            st.rerun()

# ==========================
# 💬 CỘT PHẢI: TRA CỨU
# ==========================
with col2:
    st.subheader("💬 Tra cứu nội dung")

    if st.session_state.uploaded_files:
        combined_df = pd.concat(st.session_state.uploaded_files.values(), ignore_index=True)

        user_input = st.text_input(
            "🔎 Nhập từ khóa cần tìm (bấm Enter hoặc nút Tìm kiếm):",
            key="search_input"
        )

        search_btn = st.button("🔍 Tìm kiếm")

        def tim_trong_van_ban(keyword, dataframe):
            kw = keyword.strip().lower()
            results = []
            for _, row in dataframe.iterrows():
                text = row["NỘI_DUNG"]
                matches = [m.start() for m in re.finditer(re.escape(kw), text.lower())]
                for idx in matches:
                    start = max(0, idx - 150)
                    end = min(len(text), idx + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    results.append({
                        "TRICH_DOAN": snippet,
                        "TÊN_FILE": row["TÊN_FILE"]
                    })
            return pd.DataFrame(results)

        if (user_input and st.session_state.search_input) or search_btn:
            keyword = user_input.strip()
            if keyword:
                results = tim_trong_van_ban(keyword, combined_df)
                if results.empty:
                    st.warning("❌ Không tìm thấy nội dung nào phù hợp.")
                else:
                    for _, row in results.iterrows():
                        snippet = row["TRICH_DOAN"]
                        # Bôi đậm và tô đỏ cụm từ khóa
                        highlighted = re.sub(
                            fr"({re.escape(keyword)})",
                            r'<span class="highlight-red">\1</span>',
                            snippet,
                            flags=re.IGNORECASE
                        )
                        st.markdown(f"**📜 Trích đoạn:**<br>{highlighted}", unsafe_allow_html=True)
                        st.caption(f"📁 Nguồn: *{row['TÊN_FILE']}*")
                        st.divider()
            else:
                st.info("⚠️ Vui lòng nhập từ khóa để tìm kiếm.")
    else:
        st.info("📌 Hãy tải ít nhất một file DOC, DOCX hoặc TXT để bắt đầu tra cứu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.markdown("""
    - Có thể tải nhiều file **DOC, DOCX hoặc TXT** cùng lúc.
    - Ứng dụng tự động đọc toàn bộ nội dung các file.
    - Nhập từ khóa và bấm **Enter** hoặc **nút Tìm kiếm** để tra cứu.
    - Từ khóa trong kết quả sẽ được **bôi đậm màu đỏ** để dễ nhận diện.
    """)
