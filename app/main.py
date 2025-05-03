from fastapi import FastAPI, UploadFile, File
from app.pipeline import extract_and_process_pdf


app = FastAPI()

@app.get("/")
def home():
    return {'message':'Systematic Review Tool is running'}

@app.post('/upload')
async def upload_pdf(file:UploadFile = File(...)):
    pdf_bytes = await file.read()
    result = extract_and_process_pdf(pdf_bytes, filename = file.filename)
    return result


def main():
    print("Hello from ai4sr!")


if __name__ == "__main__":
    main()
