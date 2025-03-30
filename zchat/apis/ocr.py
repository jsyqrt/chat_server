import os
import fitz  # PyMuPDF
import tempfile

import pytesseract

# if mac
# from ocrmac import ocrmac

def ocr_function(img_file_path):
    # with ocrmac
    # result = ocrmac.OCR(img_file_path, language_preference=['zh-Hans', 'en-US']).recognize()
    # result = '\n'.join([a[0] for a in result])

    # with pytesseract
    result = pytesseract.image_to_string(img_file_path, lang='chi_sim+eng')
    result = result.replace(' ', '')
    return result

def ocr_file(file_path):
    # Check if file is PDF
    if file_path.lower().endswith('.pdf'):
        pdf_document = fitz.open(file_path)
        all_text = []

        max_pages = 3

        # Process each page individually
        for page_num in range(min(len(pdf_document), max_pages)):
            # Create a temporary file for the PNG
            temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_png_path = temp_png.name
            temp_png.close()

            # Get the page and render to PNG
            page = pdf_document[page_num]
            pix = page.get_pixmap(alpha=False)
            pix.save(temp_png_path)

            # OCR the PNG file
            page_text = ocr_function(temp_png_path)
            all_text.append(page_text)

            # Clean up temporary file
            os.remove(temp_png_path)

        pdf_document.close()
        return '\n\n'.join(all_text)  # Join all pages with double newlines

    elif file_path.lower().endswith('.png') or file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
        return ocr_function(file_path)
    else:
        raise ValueError('Unsupported file type')


if __name__ == '__main__':
    print(ocr_file('/Users/liuqian/mycode/github/sf/be/chat_server/zchat/resume_optimize/resume.pdf'))
