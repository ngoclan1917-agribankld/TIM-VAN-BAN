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
st.set_page_config(page_title="📚 Tìm kiếm nội dung văn bản", layout="wide")
st.title("📚 Ứng dụng tra cứu nội dung văn bản")
st.markdown("Tải lên nhiều file (PDF, DOC, DOCX, TXT, hình ảnh scan) và nhập từ khóa cần tìm.")

# =========================
# 🧠 Session State
# =========================
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}

# =========================
# 📏 Giao diện 2 cột
# =========================
col1, col2 = st.columns([1, 2])

# =========================
# 📂 CỘT TRÁI: TẢI FILE
# =========================
with col1:
    st.subheader("📂 Tải file văn bản")
    uploaded_files = st.file_uploader(
        "Chọn tệp (PDF, DOC, DOCX, TXT, PNG, JPG, JPEG, TIFF)",
        type=["pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True
    )

    def extract_text(file):
        ext = file.name.lower().split(".")[-1]
        text = ""

        try:
            # PDF (Text hoặc Scan)
            if ext == "pdf":
                file_bytes = BytesIO(file.read())
                try:
                    with pdfplumber.open(file_bytes) as pdf:
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                except Exception:
                    # OCR fallback nếu là PDF scan
                    images = convert_from_bytes(file_bytes.getvalue())
                    for img in images:
                        text += pytesseract.image_to_string(img)

            # DOC hoặc DOCX
            elif ext in ["docx", "doc"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                try:
                    if ext == "docx":
                        doc = Document(tmp_path)
                        text = "\n".join(p.text for p in doc.paragraphs)
                    else:
                        text = textract.process(tmp_path).decode("utf-8", errors="ignore")
                except Exception as e:
                    st.error(f"❌ Không thể đọc file {file.name}: {e}")

            # TXT
            elif ext == "txt":
                text = file.read().decode("utf-8", errors="ignore")

            # Hình ảnh
            elif ext in ["png", "jpg", "jpeg", "tiff"]:
                img = Image.open(file)
                text = pytesseract.image_to_string(img)

        except Exception as e:
            st.error(f"❌ Lỗi đọc file {file.name}: {e}")

        return text.strip()

    # Lưu file đã tải vào session
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.uploaded_files:
                text_content = extract_text(file)
                if text_content:
                    st.session_state.uploaded_files[file.name] = text_content
                    st.success(f"✅ Đã tải và xử lý xong: {file.name}")

    if st.session_state.uploaded_files:
        if st.button("🧹 Xóa tất cả file đã tải"):
            st.session_state.uploaded_files.clear()
            st.rerun()

# =========================
# 💬 CỘT PHẢI: TÌM KIẾM
# =========================
with col2:
    st.subheader("💬 Tra cứu nội dung văn bản")
    user_query = st.text_input("🔎 Nhập từ khóa hoặc câu hỏi:")
    search_btn = st.button("Tìm kiếm")

    if search_btn and user_query:
        if not st.session_state.uploaded_files:
            st.warning("📌 Vui lòng tải ít nhất một file trước khi tìm kiếm.")
        else:
            results = []
            for fname, content in st.session_state.uploaded_files.items():
                if user_query.lower() in content.lower():
                    idx = content.lower().find(user_query.lower())
                    start = max(0, idx - 200)
                    end = min(len(content), idx + 200)
                    snippet = content[start:end].replace("\n", " ").strip()
                    results.append({"SOURCE_FILE": fname, "TRICH_DOAN": snippet})

            if results:
                st.success(f"✅ Tìm thấy {len(results)} kết quả chứa từ khóa **'{user_query}'**.")
                for r in results:
                    highlighted = r["TRICH_DOAN"].replace(
                        user_query, f"**:orange[{user_query}]**"
                    )
                    st.markdown(f"**📜 Trích đoạn:** {highlighted}")
                    st.caption(f"📁 Nguồn: *{r['SOURCE_FILE']}*")
                    st.divider()
            else:
                st.warning("❌ Không tìm thấy nội dung nào phù hợp.")

# =========================
# 📘 HƯỚNG DẪN
# =========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.write("""
    - Có thể tải **nhiều file** định dạng PDF, DOC, DOCX, TXT, PNG, JPG, JPEG, TIFF.
    - Nếu là **PDF scan hoặc ảnh**, hệ thống sẽ tự nhận diện chữ bằng OCR.
    - Sau khi tải xong, nhập **từ khóa hoặc câu hỏi** ở cột bên phải để tra cứu nội dung.
    - Kết quả sẽ hiển thị trích đoạn và nguồn file.
    """)
