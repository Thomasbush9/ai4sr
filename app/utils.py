from io import BytesIO
from PyPDF2 import PdfReader
from tqdm import tqdm
def extract_text_from_pdf(pdf_bytes:bytes)-> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    all_text = []
    for page in tqdm(reader.pages, desc="extracting text from pdf"):
        try:
            text = page.extract_text()
            if text:
                all_text.append(text.strip())
        except Exception:
            continue

    return "\n\n".join(all_text)

