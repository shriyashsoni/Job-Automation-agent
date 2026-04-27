import os
from docx import Document
import pdfplumber
import json

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)

def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def get_resume_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.docx':
        return extract_text_from_docx(file_path)
    elif ext == '.pdf':
        return extract_text_from_pdf(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

class ResumeParser:
    def __init__(self, ai_agent=None):
        self.ai_agent = ai_agent

    def parse(self, file_path):
        print(f"Extracting text from {file_path}...")
        text = get_resume_text(file_path)
        
        if self.ai_agent:
            print("Structuring resume data using AI...")
            return self.ai_agent.structure_resume(text)
        
        return {"raw_text": text}

if __name__ == "__main__":
    # Test extraction
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(get_resume_text(path))
