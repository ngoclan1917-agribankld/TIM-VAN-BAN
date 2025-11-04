import streamlit as st
from io import BytesIO
from docx import Document
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# =========================
# ⚙️ Cấu hình giao diện
# =========================
st.set_page_config(page_title="🔍 Tìm kiếm nội dung file", layout="wide")
st.title("🔍 Ứng dụng tìm kiếm nội dung trong file")
st.markdown("""
Ứng dụng hỗ trợ tìm kiếm từ khóa trong **PDF (text hoặc scan)**, **Word (.docx)** và **hình ảnh (.png, .jpg)**.
""")

# =========================
# 📥 Upload file
# =========================
uploaded_file = st.file_uploader("📂 Tải lên tệp (PDF, DOCX, hình ảnh)", 
                                 type=["pdf", "docx", "png", "jpg", "jpeg", "tiff"])
query = st.text_input("🔎 Nhập từ khóa cần tìm:")

# =========================
# 📖 Hàm đọc file
# =========================
def read_docx(file):
    try:
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"Lỗi đọc DOCX: {e}"

def read_pdf(file_bytes):
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(file_bytes) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception:
        # OCR fallback
        images = convert_from_bytes(file_bytes.getvalue(), dpi=150)
        for img in images:
            text += pytesseract.image_to_string(img)
    return text

def read_image(file):
    image = Image.open(file)
    return pytesseract.image_to_string(image)

# =========================
# 🔍 Xử lý tìm kiếm
# =========================
if uploaded_file and query:
    try:
        file_bytes = BytesIO(uploaded_file.read())
        ext = uploaded_file.name.lower().split(".")[-1]

        if ext == "pdf":
            text = read_pdf(file_bytes)
        elif ext == "docx":
            text = read_docx(file_bytes)
        elif ext in ["png", "jpg", "jpeg", "tiff"]:
            text = read_image(file_bytes)
        else:
            st.error("❌ Định dạng file không được hỗ trợ.")
            st.stop()

        if query.lower() in text.lower():
            st.success(f"✅ Tìm thấy từ khóa **'{query}'** trong file **{uploaded_file.name}**")
            st.text_area("📄 Nội dung trích xuất:", text[:5000], height=300)
        else:
            st.warning(f"⚠️ Không tìm thấy từ khóa '{query}' trong file {uploaded_file.name}")

    except Exception as e:
        st.error(f"❌ Lỗi đọc file {uploaded_file.name}: {str(e)}")
