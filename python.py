import streamlit as st
import docx
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from PIL import Image
import tempfile
import re
from io import BytesIO

# ==========================
# ⚙️ CẤU HÌNH GIAO DIỆN
# ==========================
st.set_page_config(page_title="🔍 Tra cứu văn bản đa định dạng", layout="wide")
st.title("🔍 ỨNG DỤNG TRA CỨU VĂN BẢN NHIỀU ĐỊNH DẠNG")
st.markdown("📂 **Bên trái:** Tải file văn bản — 💬 **Bên phải:** Nhập từ khóa để tìm kiếm trong nội dung.")

# ==========================
# 📦 HÀM ĐỌC FILE
# ==========================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def read_txt(file):
    return file.read().decode("utf-8", errors="ignore")

def read_pdf(file):
    """Đọc PDF, nếu không có text thì OCR"""
    text = ""
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception:
        pass

    if not text.strip():
        # OCR fallback
        file.seek(0)
        images = convert_from_bytes(file.read())
        for img in images:
            text += pytesseract.image_to_string(img, lang="vie+eng") + "\n"
    return text

def read_image(file):
    """Đọc hình ảnh bằng OCR"""
    img = Image.open(file)
    return pytesseract.image_to_string(img, lang="vie+eng")

def extract_text(uploaded_file):
    """Tự động nhận dạng định dạng file"""
    if not uploaded_file:
        return ""
    name = uploaded_file.name.lower()
    if name.endswith((".docx", ".doc")):
        return read_docx(uploaded_file)
    elif name.endswith(".txt"):
        return read_txt(uploaded_file)
    elif name.endswith(".pdf"):
        return read_pdf(uploaded_file)
    elif name.endswith((".png", ".jpg", ".jpeg", ".tiff")):
        return read_image(uploaded_file)
    else:
        st.warning(f"⚠️ Định dạng không được hỗ trợ: {name}")
        return ""

# ==========================
# 🔍 HÀM TÌM KIẾM
# ==========================
def highlight_keyword(text, keyword):
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='color:red;font-weight:bold'>{m.group(0)}</span>", text)

def find_relevant_context(text, keyword):
    """Tìm đoạn chứa từ khóa, mở rộng ngữ cảnh đầy đủ ý"""
    paragraphs = re.split(r'\n+', text.strip())
    results = []
    for para in paragraphs:
        if re.search(keyword, para, re.IGNORECASE):
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for i, s in enumerate(sentences):
                if re.search(keyword, s, re.IGNORECASE):
                    start = max(0, i - 1)
                    end = min(len(sentences), i + 2)
                    snippet = " ".join(sentences[start:end])
                    snippet = highlight_keyword(snippet, keyword)
                    results.append(snippet)
    return results

# ==========================
# 🧭 GIAO DIỆN STREAMLIT
# ==========================
col1, col2 = st.columns([1, 2])

# --- CỘT TRÁI: TẢI FILE ---
with col1:
    st.subheader("📤 Tải nhiều file văn bản")
    uploaded_files = st.file_uploader(
        "Chọn nhiều tệp (PDF, DOC, DOCX, TXT, hình ảnh)",
        type=["pdf", "docx", "doc", "txt", "png", "jpg", "jpeg", "tiff"],
        accept_multiple_files=True
    )

    file_texts = {}
    if uploaded_files:
        for f in uploaded_files:
            with st.spinner(f"⏳ Đang xử lý {f.name}..."):
                text = extract_text(f)
                if text.strip():
                    file_texts[f.name] = text
                    st.success(f"✅ Đã đọc xong: {f.name}")
                else:
                    st.warning(f"⚠️ Không trích xuất được nội dung: {f.name}")

# --- CỘT PHẢI: TRA CỨU ---
with col2:
    st.subheader("💬 Tìm kiếm nội dung")

    keyword = st.text_input("🔎 Nhập từ khóa cần tìm", placeholder="Nhập từ khóa rồi nhấn Enter hoặc nút tìm kiếm...")
    search_btn = st.button("🔍 Tìm kiếm")

    if (search_btn or keyword) and uploaded_files:
        if not keyword.strip():
            st.warning("⚠️ Hãy nhập từ khóa để tìm.")
        else:
            found_any = False
            for fname, text in file_texts.items():
                with st.spinner(f"🔍 Đang tìm trong {fname}..."):
                    results = find_relevant_context(text, keyword)
                    if results:
                        found_any = True
                        st.markdown(f"### 📘 Kết quả trong **{fname}**:")
                        for r in results:
                            st.markdown(
                                f"<div style='background:#f9f9f9;padding:10px;border-radius:8px;margin-bottom:10px;line-height:1.6'>{r}</div>",
                                unsafe_allow_html=True
                            )
                        st.divider()
            if not found_any:
                st.info("❌ Không tìm thấy nội dung chứa từ khóa trong các tệp đã tải.")
    elif keyword and not uploaded_files:
        st.warning("⚠️ Hãy tải lên ít nhất một tệp để tìm kiếm.")

# ==========================
# 📘 HƯỚNG DẪN
# ==========================
with st.expander("📘 Hướng dẫn sử dụng"):
    st.markdown("""
    - Tải **nhiều file cùng lúc**: PDF, DOC, DOCX, TXT hoặc ảnh (PNG/JPG).
    - Hỗ trợ **PDF scan**, tự động OCR.
    - Nhập **từ khóa**, bấm **Enter hoặc nút 🔍 Tìm kiếm**.
    - Ứng dụng hiển thị **đoạn chứa từ khóa**, có thể mở rộng vài câu trước/sau để đủ ý.
    - **Từ khóa được tô đỏ và in đậm** để dễ nhận biết.
    - Giữ nguyên **ngắt dòng, bố cục nội dung gốc**.
    """)
