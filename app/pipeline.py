from dotenv import load_dotenv
import os
from datetime import datetime
import json
from app.utils import extract_text_from_pdf, clean_text, split_into_sections
load_dotenv()  # This loads .env from the current working directory

def extract_and_process_pdf(pdf_bytes:bytes, filename:str)->dict:
    text = extract_text_from_pdf(pdf_bytes)
    text = clean_text(text)
    sections = split_into_sections(text)


    result = {
            "filename":filename,
            "timestamp":datetime.utcnow().isoformat(),
            "text_lenght":len(text),
            "text_sample": text[:500],
            "sections": sections
            }
    save_path = os.path.join("data",filename + ".json")
    os.makedirs("data", exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(result, f, indent=2)

    return result

