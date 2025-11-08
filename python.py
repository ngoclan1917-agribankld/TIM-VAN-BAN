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
    - 📂 **Bên trái:** Tải file `.doc`, `.docx` cần tra cứu  
    - 🔎 **Bên phải:** Nhập từ khóa → Nhấn **Enter** hoặc nút **"Tìm kiếm"** để xem các đoạn chứa từ khóa kèm ngữ cảnh 3–4 câu.
    """
)

# ==========================
# ⚙️ HẰNG SỐ
# ==========================
CONTEXT_BEFORE = 3   # số câu trước từ khóa
CONTEXT_AFTER = 3    # số câu sau từ khóa

# ==========================
# 🧩 HÀM XỬ LÝ CƠ BẢN
# ==========================

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Đọc nội dung từ file .docx, trả về text đơn giản, giữ xuống dòng."""
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_text_from_doc(file_bytes: bytes) -> str:
    """Đọc nội dung từ file .doc bằng mammoth, chuyển HTML -> text đơn giản."""
    result = mammoth.convert_to_html(io.BytesIO(file_bytes))
    html = result.value
    # Bỏ tag HTML đơn giản để lấy text
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def split_into_sentences(text: str):
    """
    Tách câu tối ưu cho văn bản quy định / tiếng Việt.
    Không hoàn hảo 100%, nhưng đủ nhanh & ổn định.
    """
    # Chuẩn hóa xuống dòng thành dấu phân tách nhẹ
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"\n+", "\n", normalized)

    # Tạm thời thay xuống dòng bằng ký hiệu đặc biệt để giữ cấu trúc đoạn
    placeholder = " <NL> "
    normalized = normalized.replace("\n", placeholder)

    # Regex tách câu: sau . ! ? … ; rồi có khoảng trắng + chữ cái/ số / mở ngoặc / ngoặc kép
    pattern = r'(?<=[\.!\?…;])\s+(?=[A-ZÀ-ỴÂÊÔƠƯĐ0-9“"(\[])'
    raw_sentences = re.split(pattern, normalized)

    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if not s:
            continue
        # Trả lại xuống dòng
        s = s.replace(placeholder, "\n")
        # Loại bỏ câu quá ngắn rác
        if len(s) > 1:
            sentences.append(s)
    return sentences


def normalize_for_search(text: str) -> str:
    """Chuẩn hóa để tìm kiếm: bỏ dấu, lower."""
    return unidecode(text).lower()


def highlight_keyword(text: str, keywords):
    """
    Tô đậm/bôi vàng từ khóa trong đoạn kết quả.
    keywords: list từ khóa gốc (giữ nguyên dấu).
    """
    if not keywords:
        return text

    # Sắp xếp từ khóa dài trước để tránh lồng nhau
    keywords_sorted = sorted(set([k for k in keywords if k.strip()]), key=len, reverse=True)

    def repl_factory(pattern):
        regex = re.compile(pattern, flags=re.IGNORECASE)

        def _repl(match):
            return f"<mark><b>{match.group(0)}</b></mark>"
        return regex, _repl

    result = text
    for kw in keywords_sorted:
        pattern = re.escape(kw)
        regex, repl = repl_factory(pattern)
        result = regex.sub(repl, result)

    return result


# ==========================
# 🧠 CACHE XỬ LÝ FILE
# ==========================

@st.cache_data(show_spinner=False)
def build_index(files_payload):
    """
    Từ danh sách (filename, bytes) → trả về cấu trúc:
    [
      {
        "file_name": str,
        "sentences": [str, ...],
        "norm_sentences": [str, ...]  # để tìm kiếm nhanh
      },
      ...
    ]
    """
    indexed_docs = []

    for file_name, file_bytes in files_payload:
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
            norm_sentences = [normalize_for_search(s) for s in sentences]

            if sentences:
                indexed_docs.append(
                    {
                        "file_name": file_name,
                        "sentences": sentences,
                        "norm_sentences": norm_sentences,
                    }
                )
        except Exception as e:
            # Ghi log ra UI nếu cần debug
            st.warning(f"Không đọc được file: {file_name}. Lỗi: {e}")

    return indexed_docs


def search_keyword(indexed_docs, query_raw: str, before=3, after=3, max_results_per_file=200):
    """
    Tìm kiếm theo từ khóa, trả về danh sách kết quả:
    [
      {
        "file_name": ...,
        "context": "đoạn trích 3-4 câu trước/sau có highlight"
      },
      ...
    ]
    Hỗ trợ nhập nhiều từ khóa, ngăn cách bằng dấu ; hoặc ,
    Điều kiện: câu chứa BẤT KỲ từ khóa nào (OR).
    """
    if not query_raw:
        return []

    # Tách nhiều từ khóa nếu có
    raw_parts = [p.strip() for p in re.split(r"[;,]", query_raw) if p.strip()]
    if not raw_parts:
        return []

    norm_keywords = [normalize_for_search(p) for p in raw_parts]

    results = []

    for doc in indexed_docs:
        file_name = doc["file_name"]
        sentences = doc["sentences"]
        norm_sentences = doc["norm_sentences"]

        hits = []

        for i, s_norm in enumerate(norm_sentences):
            if any(kw in s_norm for kw in norm_keywords):
                hits.append(i)

        if not hits:
            continue

        # Gom và tạo context
        used_ranges = []
        file_results = []

        for hit_idx in hits:
            start = max(0, hit_idx - before)
            end = min(len(sentences), hit_idx + after + 1)

            # Tránh trùng lặp vùng với kết quả trước
            if used_ranges and start <= used_ranges[-1][1]:
                # merge
                used_ranges[-1] = (used_ranges[-1][0], max(used_ranges[-1][1], end))
            else:
                used_ranges.append((start, end))

        for (start, end) in used_ranges:
            snippet_sentences = sentences[start:end]
            snippet_text = " ".join(snippet_sentences).strip()
            snippet_text = re.sub(r"\s{2,}", " ", snippet_text)
            snippet_html = highlight_keyword(snippet_text, raw_parts)
            file_results.append(snippet_html)
            if len(file_results) >= max_results_per_file:
                break

        for snippet_html in file_results:
            results.append(
                {
                    "file_name": file_name,
                    "context_html": snippet_html
                }
            )

    return results


# ==========================
# 🖥️ GIAO DIỆN 2 CỘT
# ==========================

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📂 Tải văn bản")
    uploaded_files = st.file_uploader(
        "Chọn một hoặc nhiều file .doc / .docx",
        type=["doc", "docx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"Đã tải {len(uploaded_files)} file.")
        for f in uploaded_files:
            st.markdown(f"- {f.name} ({f.size/1024:.1f} KB)")
    else:
        st.info("Vui lòng tải lên ít nhất một file để bắt đầu tra cứu.")

with col2:
    st.subheader("🔍 Tra cứu từ khóa")

    # Form để hỗ trợ Enter = Submit
    with st.form("search_form", clear_on_submit=False):
        default_query = st.session_state.get("last_query", "")
        query = st.text_input(
            "Nhập từ khóa (có thể nhập nhiều, cách nhau bởi dấu ';' hoặc ',')",
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
            # Chuẩn bị dữ liệu cho cache: (tên, bytes)
            files_payload = []
            for uf in uploaded_files:
                content = uf.getvalue()
                # để cache hiệu quả hơn: thêm hash
                file_hash = hashlib.md5(content).hexdigest()
                files_payload.append((f"{uf.name}::{file_hash}", content))

            with st.spinner("Đang xử lý & tra cứu..."):
                indexed_docs = build_index(files_payload)
                results = search_keyword(
                    indexed_docs,
                    query_raw=query,
                    before=CONTEXT_BEFORE,
                    after=CONTEXT_AFTER
                )

            st.markdown("---")
            if not results:
                st.warning("Không tìm thấy kết quả nào chứa từ khóa trong các file đã tải.")
            else:
                st.success(f"Tìm thấy {len(results)} đoạn phù hợp trong các văn bản.")
                for i, item in enumerate(results, start=1):
                    st.markdown(
                        f"""
                        <div style="padding:10px; margin-bottom:8px; border-radius:6px; border:1px solid #ddd;">
                            <div style="font-size:13px; color:#555;">
                                <b>File:</b> {item['file_name'].split("::")[0]} &nbsp;|&nbsp; <b>Kết quả #{i}</b>
                            </div>
                            <div style="margin-top:4px; font-size:14px; line-height:1.6;">
                                {item['context_html']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
