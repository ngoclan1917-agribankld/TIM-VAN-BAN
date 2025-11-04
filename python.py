import streamlit as st
import pandas as pd
from io import StringIO
from PyPDF2 import PdfReader
from docx import Document

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="Chatbot Văn bản Quy định", page_icon="📜", layout="wide")
st.title("📜 Chatbot tra cứu Văn bản Quy định")
st.markdown("📂 **Trái:** Vui lòng tải các file văn bản quy định — 💬 **Phải:** Tra cứu nội dung chứa từ khóa.")

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
# 🧭 2 CỘT GIAO DIỆN
# ==========================
col1, col2 = st.columns([1, 2])

# ==========================
# 📂 CỘT TRÁI: TẢI FILE VĂN BẢN
# ==========================
with col1:
    st.subheader("📂 Tải file văn bản")

    def read_text_from_file(file):
        """Đọc nội dung từ file PDF, DOCX hoặc TXT"""
        text = ""
        if file.name.lower().endswith(".pdf"):
            reader = PdfReader(file)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        elif file.name.lower().endswith(".docx"):
            doc = Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif file.name.lower().endswith(".txt"):
            stringio = StringIO(file.getvalue().decode("utf-8", errors="ignore"))
            text = stringio.read()
        else:
            raise ValueError("Định dạng file không hỗ trợ. Hãy tải PDF, DOCX hoặc TXT.")
        return text

    uploaded_files = st.file_uploader(
        "Chọn file văn bản (PDF, DOCX, TXT, có thể nhiều)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                try:
                    text_content = read_text_from_file(file)
                    # Mỗi file lưu thành dataframe 1 cột
                    df = pd.DataFrame({"NỘI DUNG": [text_content], "SOURCE_FILE": [file.name]})
                    st.session_state.uploaded_files[file.name] = df
                except Exception as e:
                    st.error(f"Lỗi đọc file {file.name}: {e}")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file đã tải"):
            st.session_state.uploaded_files.clear()
            st.session_state.uploader_key += 1
            st.rerun()

# ==========================
# 💬 CỘT PHẢI: CHATBOT TRA CỨU
# ==========================
with col2:
    st.subheader("💬 Chatbot tra cứu nội dung văn bản")

    if st.session_state.uploaded_files:
        combined_df = pd.concat(st.session_state.uploaded_files.values(), ignore_index=True)

        user_input = st.text_input(
            "🔎 Nhập từ khóa cần tìm (ví dụ: xử phạt hành chính, hợp đồng lao động...)"
        )
        search_btn = st.button("Tìm kiếm")

        def tim_trong_van_ban(keyword, dataframe):
            kw = keyword.lower().strip()
            results = []
            for _, row in dataframe.iterrows():
                text = row["NỘI DUNG"]
                # Cắt đoạn quanh từ khóa để hiển thị ngắn gọn
                if kw in text.lower():
                    idx = text.lower().index(kw)
                    start = max(0, idx - 200)
                    end = min(len(text), idx + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    results.append({"TRICH_DOAN": snippet, "SOURCE_FILE": row["SOURCE_FILE"]})
            return pd.DataFrame(results)

        if user_input or search_btn:
            if user_input:
                results = tim_trong_van_ban(user_input, combined_df)
                if results.empty:
                    st.warning("❌ Không tìm thấy nội dung nào phù hợp.")
                else:
                    for _, row in results.iterrows():
                        st.markdown(f"**📜 Trích đoạn:** {row['TRICH_DOAN']}")
                        st.caption(f"📁 Nguồn: *{row['SOURCE_FILE']}*")
                        st.divider()
    else:
        st.info("📌 Vui lòng tải ít nhất một file văn bản trước khi tra cứu.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("- Có thể tải nhiều file văn bản định dạng **PDF, DOCX, hoặc TXT**.")
    st.write("- Hệ thống sẽ đọc toàn bộ nội dung của từng file.")
    st.write("- Khi nhập từ khóa, chương trình sẽ hiển thị đoạn văn có chứa từ khóa và nguồn file.")
    st.write("- Ví dụ: nhập 'xử phạt' để tìm các điều khoản liên quan trong các văn bản tải lên.")
