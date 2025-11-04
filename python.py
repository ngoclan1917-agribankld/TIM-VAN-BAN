import streamlit as st
import pandas as pd
from io import StringIO
from tempfile import NamedTemporaryFile
import os

# ưu tiên import PyPDF2 or pypdf
try:
    # new package name is pypdf, older is PyPDF2; try both
    from pypdf import PdfReader  # try pypdf first
except Exception:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        PdfReader = None

# docx reader
try:
    from docx import Document
except Exception:
    Document = None

# doc (old .doc) fallback using docx2txt if available
try:
    import docx2txt
except Exception:
    docx2txt = None

st.set_page_config(page_title="Chatbot Tra cứu Văn bản", page_icon="📜", layout="wide")
st.title("📜 Chatbot tra cứu Văn bản (PDF / DOCX / DOC / TXT)")
st.caption("Lưu ý: phiên bản này không sử dụng OCR — nếu file là ảnh/scan, app sẽ không trích được text")

# session state to keep uploaded content (as text)
if "files_text" not in st.session_state:
    st.session_state.files_text = {}  # {filename: text}

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📁 Tải file (PDF, DOCX, DOC, TXT)")
    uploaded = st.file_uploader(
        "Chọn file (hỗ trợ: .pdf .docx .doc .txt) — có thể nhiều file",
        type=["pdf", "docx", "doc", "txt"],
        accept_multiple_files=True
    )

    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.files_text:
                continue  # đã có
            fname = f.name.lower()
            extracted = ""

            # ===== PDF =====
            if fname.endswith(".pdf"):
                if PdfReader is None:
                    st.error("Module `pypdf`/`PyPDF2` chưa được cài — thêm vào requirements.txt (`pypdf` hoặc `PyPDF2`).")
                    continue
                try:
                    reader = PdfReader(f)
                    pages = []
                    for p in reader.pages:
                        # extract_text may be None on scanned PDF
                        txt = p.extract_text()
                        pages.append(txt or "")
                    extracted = "\n".join(pages).strip()
                    if not extracted:
                        st.warning(f"⚠️ Không trích được text từ {f.name}. Có thể là PDF dạng ảnh/scan.")
                except Exception as e:
                    st.error(f"Lỗi khi đọc PDF {f.name}: {e}")
                    continue

            # ===== DOCX =====
            elif fname.endswith(".docx"):
                if Document is None:
                    st.error("Module `python-docx` chưa được cài — thêm `python-docx` vào requirements.txt.")
                    continue
                try:
                    doc = Document(f)
                    extracted = "\n".join([p.text for p in doc.paragraphs]).strip()
                except Exception as e:
                    st.error(f"Lỗi khi đọc DOCX {f.name}: {e}")
                    continue

            # ===== DOC (old) =====
            elif fname.endswith(".doc"):
                if docx2txt is None:
                    st.warning(f"Không có `docx2txt` để đọc .doc — bạn có thể chuyển .doc sang .docx trước khi tải lên.")
                    # thử dùng textract nếu có (không bao gồm ở đây vì yêu cầu hệ thống)
                    # lưu tạm và tiếp tục (không trích được)
                    extracted = ""
                else:
                    try:
                        # docx2txt.process cần đường dẫn file
                        with NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
                            tmp.write(f.getvalue())
                            tmp_path = tmp.name
                        try:
                            extracted = docx2txt.process(tmp_path) or ""
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                    except Exception as e:
                        st.error(f"Lỗi khi đọc .doc {f.name}: {e}")
                        continue

            # ===== TXT =====
            elif fname.endswith(".txt"):
                try:
                    extracted = StringIO(f.getvalue().decode("utf-8", errors="ignore")).read()
                except Exception:
                    try:
                        extracted = f.getvalue().decode("latin-1", errors="ignore")
                    except Exception as e:
                        st.error(f"Lỗi đọc TXT {f.name}: {e}")
                        continue
            else:
                st.warning(f"Định dạng không hỗ trợ: {f.name}")
                continue

            # lưu nếu có nội dung (dù rỗng - vẫn lưu tên file để thông báo)
            st.session_state.files_text[f.name] = extracted

    if st.session_state.files_text:
        if st.button("🧹 Xóa tất cả file đã tải"):
            st.session_state.files_text.clear()
            st.experimental_rerun()

with col2:
    st.subheader("🔎 Tìm kiếm nội dung trong các file đã tải")
    if not st.session_state.files_text:
        st.info("📌 Vui lòng tải file lên bên trái trước khi tìm kiếm.")
    else:
        keyword = st.text_input("Nhập từ khóa cần tìm (không phân biệt hoa thường)")
        search_btn = st.button("Tìm kiếm")

        if (keyword and search_btn) or (keyword and not search_btn and st.session_state.get("auto_search", True)):
            kw = keyword.strip().lower()
            if not kw:
                st.warning("Vui lòng nhập từ khóa hợp lệ.")
            else:
                results = []
                for fname, text in st.session_state.files_text.items():
                    if not text:
                        continue
                    t_lower = text.lower()
                    start_idx = 0
                    while True:
                        idx = t_lower.find(kw, start_idx)
                        if idx == -1:
                            break
                        start = max(0, idx - 200)
                        end = min(len(text), idx + len(kw) + 200)
                        snippet = text[start:end].replace("\n", " ").strip()
                        results.append({"file": fname, "snippet": snippet})
                        start_idx = idx + len(kw)

                if not results:
                    st.warning("❌ Không tìm thấy kết quả nào.")
                else:
                    st.success(f"🔎 Tìm thấy {len(results)} kết quả.")
                    for r in results:
                        # highlight (simple)
                        display_snip = r["snippet"].replace(keyword, f"**:orange[{keyword}]**")
                        st.markdown(f"**📜 Trích đoạn:** {display_snip}")
                        st.caption(f"📁 Nguồn: {r['file']}")
                        st.divider()

# Hướng dẫn nhỏ
with st.expander("📘 Ghi chú"):
    st.write("- App này **không** dùng pdfplumber/pytesseract nên dễ deploy trên Streamlit Cloud.")
    st.write("- Nếu PDF là **scan/ảnh**, PyPDF2/Pypdf sẽ không trích text được — cần OCR.")
    st.write("- Để hỗ trợ OCR trên môi trường deploy, bạn phải cài phần mềm hệ thống (ví dụ tesseract), điều này thường không có trong Streamlit Cloud.")
    st.write("- Nếu bạn cần đọc .doc (cũ) tốt hơn, upload file .docx thay thế hoặc chuyển .doc → .docx rồi thử lại.")
