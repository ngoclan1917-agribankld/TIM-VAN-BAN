import streamlit as st
from docx import Document
import mammoth
from unidecode import unidecode
import io
import re
import hashlib

# ==========================
# ⚙️ CẤU HÌNH GIAO DIỆN
# ==========================
st.set_page_config(
    page_title="📄 Tra cứu văn bản Word",
    page_icon="📘",
    layout="wide"
)

st.title("📄 ỨNG DỤNG TRA CỨU NỘI DUNG VĂN BẢN (.DOC, .DOCX)")
st.markdown(
    """
    - 📂 **Bên trái:** Tải file `.doc`, `.docx` cần tra cứu.  
    - 🔎 **Bên phải:** Nhập từ khóa → Nhấn **Enter** hoặc nút **"Tìm kiếm"** để xem các đoạn chứa từ khóa kèm ngữ cảnh 3–4 câu.
    """
)

# ==========================
# ⚙️ THAM SỐ
# ==========================
CONTEXT_BEFORE = 3   # số câu trước từ khóa
CONTEXT_AFTER = 3    # số câu sau từ khóa
MAX_RESULTS_PER_FILE = 200

# ==========================
# 🧩 CÁC HÀM XỬ LÝ
# ==========================

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Đọc nội dung từ file .docx, giữ xuống dòng giữa các đoạn."""
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_text_from_doc(file_bytes: bytes) -> str:
    """Đọc nội dung từ file .doc bằng mammoth, chuyển HTML sang text."""
    result = mammoth.convert_to_html(io.BytesIO(file_bytes))
    html = result.value or ""
    # Loại bỏ tag HTML đơn giản
    text = re.sub(r"<[^>]+>", " ", html)
    # Chuẩn hoá khoảng trắng & xuống dòng
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def split_into_sentences(text: str):
    """
    Tách câu đơn giản, ưu tiên nhanh & ổn định.
    Vẫn giữ xuống dòng bằng placeholder rồi trả lại.
    """
    if not text:
        return []

    # Chuẩn hoá xuống dòng
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"\n+", "\n", normalized)

    placeholder = "<NL>"
    normalized = normalized.replace("\n", f" {placeholder} ")

    # Tách sau các dấu . ! ? … ;
    parts = re.split(r'(?<=[\.!\?…;])\s+', normalized)

    sentences = []
    for part in parts:
        s = part.strip()
        if not s:
            continue
        s = s.replace(placeholder, "\n").strip()
        if len(s) > 0:
            sentences.append(s)

    # Nếu vì lý do nào đó không tách được, coi toàn bộ là 1 câu
    if not sentences and text.strip():
        sentences = [text.strip()]

    return sentences


def normalize_for_search(text: str) -> str:
    """Chuẩn hóa để so khớp: bỏ dấu, lower, remove dư khoảng trắng."""
    return re.sub(r"\s+", " ", unidecode(text).lower()).strip()


def highlight_keyword(text: str, raw_keywords):
    """
    Bôi vàng + in đậm các từ khóa trong đoạn kết quả.
    Dùng từ khóa gốc (giữ dấu), không ảnh hưởng tốc độ.
    """
    if not raw_keywords:
        return text

    # Lọc & sắp xếp từ khóa dài trước
    keywords = sorted(
        {kw.strip() for kw in raw_keywords if kw.strip()},
        key=len,
        reverse=True
    )

    result = text
    for kw in keywords:
        pattern = re.escape(kw)
        regex = re.compile(pattern, flags=re.IGNORECASE)
        result = regex.sub(lambda m: f"<mark><b>{m.group(0)}</b></mark>", result)

    return result


# ==========================
# 🧠 XÂY DỰNG CHỈ MỤC (CACHE)
# ==========================

@st.cache_data(show_spinner=False)
def build_index(files_meta):
    """
    files_meta: danh sách tuple (file_name, file_hash, file_bytes)

    Trả về:
    [
      {
        "file_name": str,              # tên hiển thị
        "sentences": [str, ...],
        "norm_sentences": [str, ...],  # để tìm nhanh
      },
      ...
    ]
    """
    indexed_docs = []

    for file_name, file_hash, file_bytes in files_meta:
        ext = file_name.lower().split(".")[-1]

        try:
            if ext == "docx":
                text = extract_text_from_docx(file_bytes)
            elif ext == "doc":
                text = extract_text_from_doc(file_bytes)
            else:
                continue

            if not text:
                continue

            sentences = split_into_sentences(text)
            if not sentences:
                continue

            norm_sentences = [normalize_for_search(s) for s in sentences]

            indexed_docs.append(
                {
                    "file_name": file_name,
                    "sentences": sentences,
                    "norm_sentences": norm_sentences,
                }
            )

        except Exception as e:
            st.warning(f"Không đọc được file: {file_name}. Lỗi: {e}")

    return indexed_docs


def search_keyword(indexed_docs, query_raw: str,
                   before=3, after=3, max_results_per_file=200):
    """
    Tìm theo từ khóa, OR giữa các từ khóa.
    query_raw: chuỗi, có thể nhiều từ khóa, phân tách ; hoặc ,
    """
    if not query_raw:
        return []

    # Tách danh sách từ khóa
    raw_parts = [p.strip() for p in re.split(r"[;,]", query_raw) if p.strip()]
    if not raw_parts:
        return []

    norm_keywords = [normalize_for_search(p) for p in raw_parts]

    results = []

    for doc in indexed_docs:
        file_name = doc["file_name"]
        sentences = doc["sentences"]
        norm_sentences = doc["norm_sentences"]

        hit_indices = []
        for i, s_norm in enumerate(norm_sentences):
            if any(kw and kw in s_norm for kw in norm_keywords):
                hit_indices.append(i)

        if not hit_indices:
            continue

        # Gom vùng ngữ cảnh, tránh trùng lặp
        merged_ranges = []
        for idx in hit_indices:
            start = max(0, idx - before)
            end = min(len(sentences), idx + after + 1)

            if merged_ranges and start <= merged_ranges[-1][1]:
                # Gộp với vùng trước
                merged_ranges[-1] = (
                    merged_ranges[-1][0],
                    max(merged_ranges[-1][1], end),
                )
            else:
                merged_ranges.append((start, end))

        file_count = 0
        for start, end in merged_ranges:
            snippet_sentences = sentences[start:end]
            if not snippet_sentences:
                continue

            snippet_text = " ".join(snippet_sentences)
            snippet_text = re.sub(r"\s{2,}", " ", snippet_text).strip()

            # Highlight từ khóa
            snippet_html = highlight_keyword(snippet_text, raw_parts)

            results.append(
                {
                    "file_name": file_name,
                    "context_html": snippet_html
                }
            )

            file_count += 1
            if file_count >= max_results_per_file:
                break

    return results


# ==========================
# 🖥️ GIAO DIỆN 2 CỘT
# ==========================

col1, col2 = st.columns([1, 2])

# --- CỘT TRÁI: UPLOAD ---
with col1:
    st.subheader("📂 Tải văn bản")
    uploaded_files = st.file_uploader(
        "Chọn một hoặc nhiều file .doc / .docx",
        type=["doc", "docx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"Đã tải {len(uploaded_files)} file:")
        for f in uploaded_files:
            st.markdown(f"- `{f.name}` ({f.size/1024:.1f} KB)")
    else:
        st.info("Vui lòng tải lên ít nhất một file để bắt đầu tra cứu.")

# --- CỘT PHẢI: TÌM KIẾM ---
with col2:
    st.subheader("🔍 Tra cứu từ khóa")

    with st.form("search_form", clear_on_submit=False):
        default_query = st.session_state.get("last_query", "")
        query = st.text_input(
            "Nhập từ khóa (có thể nhiều, cách nhau bởi ';' hoặc ',')",
            value=default_query,
            placeholder="Ví dụ: hạn mức tín dụng; tài sản bảo đảm; điều kiện vay"
        )
        submitted = st.form_submit_button("🔍 Tìm kiếm")

    if submitted:
        st.session_state["last_query"] = query

        if not uploaded_files:
            st.warning("Vui lòng tải file ở bên trái trước khi tìm kiếm.")
        elif not query.strip():
            st.warning("Vui lòng nhập từ khóa cần tra cứu.")
        else:
            # Chuẩn bị dữ liệu cho cache: dùng hash để nhận diện phiên bản file
            files_meta = []
            for uf in uploaded_files:
                content = uf.getvalue()
                file_hash = hashlib.md5(content).hexdigest()
                # KHÔNG chỉnh sửa tên file khi đọc đuôi, chỉ dùng hash cho cache
                files_meta.append((uf.name, file_hash, content))

            with st.spinner("Đang xử lý & tra cứu..."):
                indexed_docs = build_index(tuple(files_meta))
                results = search_keyword(
                    indexed_docs,
                    query_raw=query,
                    before=CONTEXT_BEFORE,
                    after=CONTEXT_AFTER,
                    max_results_per_file=MAX_RESULTS_PER_FILE
                )

            st.markdown("---")

            if not results:
                st.warning("Không tìm thấy kết quả nào chứa từ khóa trong các file đã tải.")
            else:
                st.success(f"Tìm thấy {len(results)} đoạn phù hợp trong các văn bản.")
                for i, item in enumerate(results, start=1):
                    st.markdown(
                        f"""
                        <div style="padding:10px; margin-bottom:10px; border-radius:6px; border:1px solid #ddd;">
                            <div style="font-size:12px; color:#666;">
                                <b>File:</b> {item['file_name']} | <b>Kết quả #{i}</b>
                            </div>
                            <div style="margin-top:6px; font-size:14px; line-height:1.6; text-align:justify;">
                                {item['context_html']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
