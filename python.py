import streamlit as st
import docx
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
import tempfile
import re
from io import BytesIO

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="🔍 Tìm kiếm nội dung tài liệu", layout="wide")
st.title("🔍 Tìm kiếm nội dung trong tài liệu")
st.markdown("📂 **Bên trái:** Tải tài liệu — 💬 **Bên phải:** Nhập từ khóa cần tìm và xem kết quả")

# ==========================
# 🔧 Hàm trích xuất văn bản
# ==========================
def read_docx(file):
    """Đọc file Word"""
    doc = docx.Document(file)
    text = [para.text for para in doc.paragraphs]
    return "\n".join(text)

def read_txt(file):
    """Đọc file TXT"""
    return file.read().decode("utf-8", errors="ignore")

def read_pdf(file):
    """Đọc PDF, hỗ trợ OCR nếu là file scan"""
    text = ""
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception:
        pass  # fallback xuống OCR nếu đọc lỗi
    if not text.strip():
        # PDF scan (ảnh)
        file.seek(0)
        images = convert_from_bytes(file.read())
        for image in images:
            text += pytesseract.image_to_string(image, lang="vie+eng") + "\n"
    return text

def extract_text(uploaded_file):
    """Xác định loại file và đọc nội dung"""
    if not uploaded_file:
        return ""
    filename = uploaded_file.name.lower()
    if filename.endswith((".docx", ".doc")):
        return read_docx(uploaded_file)
    elif filename.endswith(".txt"):
        return read_txt(uploaded_file)
    elif filename.endswith(".pdf"):
        return read_pdf(uploaded_file)
    else:
        st.error("❌ Định dạng không được hỗ trợ. Hãy tải lên PDF, DOCX hoặc TXT.")
        return ""

# ==========================
# 🔍 Xử lý tìm kiếm và tô màu
# ==========================
def highlight_keyword(text, keyword):
    """Tô đỏ và đậm từ khóa"""
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='color:red;font-weight:bold'>{m.group(0)}</span>", text)

def find_relevant_context(text, keyword):
    """Tìm đoạn chứa từ khóa và lấy thêm ngữ cảnh đủ ý"""
    paragraphs = re.split(r'\n+', text.strip())
    results = []
    for para in paragraphs:
        if re.search(keyword, para, re.IGNORECASE):
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for i, s in enumerate(sentences):
                if re.search(keyword, s, re.IGNORECASE):
                    start = max(0, i - 1)
                    end = min(len(sentences), i + 2)
                    context = " ".join(sentences[start:end])
                    context = highlight_keyword(context, keyword)
                    results.append(context)
    return results

# ==========================
# 📂 Giao diện Streamlit
# ==========================
col1, col2 = st.columns([1, 2])

# --- Bên trái: tải file ---
with col1:
    uploaded_file = st.file_uploader("📤 Tải tài liệu (PDF, DOCX, TXT)", type=["pdf", "docx", "doc", "txt"])
    text_content = ""
    if uploaded_file:
        with st.spinner("⏳ Đang đọc nội dung tài liệu..."):
            text_content = extract_text(uploaded_file)
            st.success("✅ Đã tải và đọc xong tệp!")

# --- Bên phải: nhập từ khóa và tìm kiếm ---
with col2:
    keyword = st.text_input("🔎 Nhập từ khóa cần tìm", "", placeholder="Ví dụ: Agribank, báo cáo, kế hoạch...")

    if st.button("Tìm kiếm") or (keyword and st.session_state.get("keyword") != keyword):
        st.session_state["keyword"] = keyword
        if not uploaded_file:
            st.warning("⚠️ Hãy tải lên một tệp trước khi tìm kiếm.")
        elif not keyword.strip():
            st.warning("⚠️ Nhập từ khóa để tìm.")
        else:
            with st.spinner("🔍 Đang tìm kiếm..."):
                results = find_relevant_context(text_content, keyword)
                if results:
                    st.markdown("### 📚 Kết quả tìm thấy:")
                    for res in results:
                        st.markdown(
                            f"<div style='background:#f9f9f9;padding:10px;border-radius:8px;margin-bottom:10px;line-height:1.5'>{res}</div>",
                            unsafe_allow_html=True)
                else:
                    st.info("❌ Không tìm thấy nội dung chứa từ khóa.")
