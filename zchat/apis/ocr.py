from ocrmac import ocrmac
import os
import fitz  # PyMuPDF
import tempfile

def ocr_file(file_path):
    # Check if file is PDF
    if file_path.lower().endswith('.pdf'):
        pdf_document = fitz.open(file_path)
        all_text = []

        # Process each page individually
        for page_num in range(len(pdf_document)):
            # Create a temporary file for the PNG
            temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_png_path = temp_png.name
            temp_png.close()

            # Get the page and render to PNG
            page = pdf_document[page_num]
            pix = page.get_pixmap(alpha=False)
            pix.save(temp_png_path)

            # OCR the PNG file
            annotations = ocrmac.OCR(temp_png_path, language_preference=['zh-Hans']).recognize()
            page_text = '\n'.join([a[0] for a in annotations])
            all_text.append(page_text)

            # Clean up temporary file
            os.remove(temp_png_path)

        pdf_document.close()
        return '\n\n'.join(all_text)  # Join all pages with double newlines

    elif file_path.lower().endswith('.png') or file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
        annotations = ocrmac.OCR(file_path, language_preference=['zh-Hans']).recognize()
        return '\n'.join([a[0] for a in annotations])
    else:
        raise ValueError('Unsupported file type')


if __name__ == '__main__':
    print(ocr_file('/Users/liuqian/mycode/github/sf/be/chat_server/zchat/resume_optimize/resume.pdf'))
