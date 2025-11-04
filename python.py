import streamlit as st
import docx
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
import tempfile
import re
import io

# ==========================
# ⚙️ Cấu hình giao diện
# ==========================
st.set_page_config(page_title="🔍 Tìm kiếm nội dung tài liệu", layout="wide")
st.title("🔍 Tìm kiếm nội dung trong tài liệu")
st.markdown("📂 **Trái:** Tải file tài liệu — 💬 **Phải:** Nhập từ khóa cần tìm và xem kết quả")

# ==========================
# 🔧 Hàm trích xuất văn bản
# ==========================
def read_docx(file):
    doc = docx.Document(file)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)

def read_txt(file):
    return file.read().decode("utf-8", errors="ignore")

def read_pdf(file):
    text = ""
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    except:
        # Nếu PDF là scan, dùng OCR
        file.seek(0)
        images = convert_from_bytes(file.read())
        for image in images:
            text += pytesseract.image_to_string(image, lang="vie+eng") + "\n"
    return text

def extract_text(uploaded_file):
    if uploaded_file is None:
        return ""
    filename = uploaded_file.name.lower()
    if filename.endswith((".docx", ".doc")):
        return read_docx(uploaded_file)
    elif filename.endswith(".txt"):
        return read_txt(uploaded_file)
    elif filename.endswith(".pdf"):
        return read_pdf(uploaded_file)
    else:
        st.error("❌ Định dạng không được hỗ trợ.")
        return ""

# ==========================
# 🧩 Tìm kiếm nội dung
# ==========================
def highlight_keyword(context, keyword):
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='color:red;font-weight:bold'>{m.group(0)}</span>", context)

def find_relevant_paragraphs(text, keyword):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    results = []
    for i, sentence in enumerate(sentences):
        if re.search(keyword, sentence, re.IGNORECASE):
            # Lấy thêm câu trước/sau nếu cần, đảm bảo đủ ý
            start = max(0, i - 1)
            end = min(len(sentences), i + 2)
            snippet = " ".join(sentences[start:end])
            snippet = highlight_keyword(snippet, keyword)
            results.append(snippet)
    return results

# ==========================
# 📂 Giao diện tải file
# ==========================
col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader("📤 Tải tài liệu (PDF, DOCX, TXT)", type=["pdf", "docx", "doc", "txt"])
    if uploaded_file:
        with st.spinner("⏳ Đang đọc nội dung..."):
            text_content = extract_text(uploaded_file)
            st.success("✅ Tải và đọc thành công!")

with col2:
    keyword = st.text_input("🔎 Nhập từ khóa cần tìm", "", placeholder="Ví dụ: Agribank, báo cáo, kế hoạch...")
    search_button = st.button("Tìm kiếm")

    if keyword or search_button:
        if uploaded_file is None:
            st.warning("⚠️ Vui lòng tải tệp trước khi tìm kiếm.")
        elif keyword.strip() == "":
            st.warning("⚠️ Nhập từ khóa cần tìm.")
        else:
            with st.spinner("🔍 Đang tìm..."):
                results = find_relevant_paragraphs(text_content, keyword)
                if results:
                    st.markdown("### 📚 Kết quả tìm thấy:")
                    for i, res in enumerate(results, start=1):
                        st.markdown(f"<div style='background:#f9f9f9;padding:8px;border-radius:6px;margin-bottom:8px'>{res}</div>", unsafe_allow_html=True)
                else:
                    st.info("❌ Không tìm thấy nội dung chứa từ khóa.")
