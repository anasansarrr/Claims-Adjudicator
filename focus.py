import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

def extract_text(file_path: str) -> str:
    """
    Extracts text from image, PDF, or TXT files.
    
    Supported:
        - Images (jpg, jpeg, png, tif, tiff)
        - PDFs (text-based or scanned)
        - TXT files
    """

    # Get file extension
    ext = os.path.splitext(file_path)[1].lower()

    # --------------------------
    # Case 1: TXT files
    # --------------------------
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # --------------------------
    # Case 2: Image files
    # --------------------------
    image_extensions = [".jpg", ".jpeg", ".png", ".tif", ".tiff"]
    if ext in image_extensions:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)

    # --------------------------
    # Case 3: PDF files
    # --------------------------
    if ext == ".pdf":
        pages = convert_from_path(file_path)
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page) + "\n"
        return text

    # --------------------------
    # Unsupported
    # --------------------------
    raise ValueError(f"Unsupported file type: {ext}")
