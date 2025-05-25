from io import BytesIO
from PyPDF2 import PdfReader
from tqdm import tqdm
import re
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


def clean_text(text:str)->str:
    #remove common arts
    text = text.replace('\ufb01', 'fi').replace('\ufb02', 'fl')

    # normalize text
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()
def split_into_sections(text:str)-> dict:
    section_headers = [
        "abstract", "introduction", "methods", "materials and methods",
        "results", "discussion", "conclusion", "references"
    ]

    pattern = r'\n(?P<header>' + '|'.join(section_headers) + r')\b'
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    sections = {}

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i +1 < len(matches) else len(text)
        header = (match.group('header')).lower()
        sections[header] = text[start:end].strip()
    return sections

