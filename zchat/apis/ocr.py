import os
import fitz  # PyMuPDF
import tempfile

import pytesseract

from PIL import Image
import io
import base64

# if mac
# from ocrmac import ocrmac

def convert_image_to_webp_base64(input_image_path):
    try:
        with Image.open(input_image_path) as img:
            byte_arr = io.BytesIO()
            img.save(byte_arr, format='webp')
            byte_arr = byte_arr.getvalue()
            base64_str = base64.b64encode(byte_arr).decode('utf-8')
            return base64_str
    except IOError:
        print(f"Error: Unable to open or convert the image {input_image_path}")
        return None

def ocr_with_llm(file_path):
    from zchat.apis.llm import get_response_from_llm
    from zchat.apis.llm import get_json_blocks_from_llm_response

    base64_image = convert_image_to_webp_base64(file_path)
    messages = [
        {
            "role": "system",
            "content": "你是一个OCR专家，请将图片中的文字提取出来，并返回对应的markdown格式。"
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                },
                {
                    "type": "text",
                    "text": "请将图片中的文字提取出来，并返回对应的markdown格式。"
                }
            ]
        }
    ]
    llm_response = get_response_from_llm(messages, 'qwen-2.5-32b-vl', max_tokens=4096, platform="siliconflow")
    return llm_response

def ocr_function(img_file_path, with_llm=False):
    if with_llm:
        return ocr_with_llm(img_file_path)

    # with ocrmac
    # result = ocrmac.OCR(img_file_path, language_preference=['zh-Hans', 'en-US']).recognize()
    # result = '\n'.join([a[0] for a in result])

    # with pytesseract
    result = pytesseract.image_to_string(img_file_path, lang='chi_sim+eng')
    result = result.replace(' ', '')
    return result

def ocr_file(file_path, with_llm=True):
    # Check if file is PDF
    if file_path.lower().endswith('.pdf'):
        pdf_document = fitz.open(file_path)
        all_text = []

        max_pages = 5

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
            page_text = ocr_function(temp_png_path, with_llm)
            all_text.append(page_text)

            # Clean up temporary file
            os.remove(temp_png_path)

        pdf_document.close()
        return '\n\n'.join(all_text)  # Join all pages with double newlines

    elif file_path.lower().endswith('.png') or file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
        return ocr_function(file_path, with_llm)
    else:
        raise ValueError('Unsupported file type')


if __name__ == '__main__':
    print(ocr_file('/Users/liuqian/mycode/github/sf/be/chat_server/resume.pdf', with_llm=True))
