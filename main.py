import os
import io
import re
import easyocr
import textwrap
import requests
from PIL import Image
from io import BytesIO
from pypdf import PdfReader
from spire.doc import Document
from urllib.parse import urlparse
from flask import Flask,request,jsonify
from pdfminer.high_level import extract_text


app = Flask(__name__)

class PO_num_extracter:
    
    def __init__(self,pdf_path_or_url : str):
        self.pdf_path_or_url = pdf_path_or_url
        self.flag = bool
    
    def log(self,message:str,success_flag=True):
        if success_flag: print(f"\n\n###################   {message}   ###################")
        else: print(f"!!!!!!!!!!!!!!!!!!   {message}   !!!!!!!!!!!!!!!!!!!!") 
          
    def download_url(self):
        try:
            if self.pdf_path_or_url.startswith("http"):
                self.log("Downloading URL")
                response = requests.get(self.pdf_path_or_url)
                response.raise_for_status()  # Raise an exception for non-200 status codes
                self.flag = True
                if response.status_code == 200 :return response.content
            else:
                with open(self.pdf_path_or_url, 'rb') as f:
                    return f.read()
        except requests.exceptions.RequestException as e:
            self.log(f"Failed to download PDF from {self.pdf_path_or_url}", success_flag=False)
            return None
        except FileNotFoundError as e:
            self.log(f"File not found: {self.pdf_path_or_url}", success_flag=False)
            return None

            
    def extract_invoice_number(self,text: str):
            
        invoice_numbers = re.findall(r'\b\d{5}\b', text)
        if invoice_numbers: return invoice_numbers
        else:
            pattern = r'(?:invoice\s*(?:no(?:\.|:)?|number|num)?\s*:?)(\d{5})'
            invoice_numbers = re.search(pattern, text, re.IGNORECASE)
            if invoice_numbers:
                return invoice_numbers.group()
            else:
                return
            
    def get_text_pdf(self):
    
        pdf_data = self.download_url()
        
        if pdf_data:
            reader = PdfReader(io.BytesIO(pdf_data))
            text = ''.join([page.extract_text() for page in reader.pages])
            self.wrapped_text = textwrap.fill(text, width=120)
            
            if not self.flag:
                
                self.text = extract_text(self.pdf_path_or_url)
            
                return [self.wrapped_text,self.text]
            
            else: return [self.wrapped_text]
        else: return None
    
    def get_text_doc(self,file_path = "temp.docx"):
    
        data = self.download_url()
        
        if data:
            with open(file_path, "wb") as temp_file:
                temp_file.write(data)
            document = Document()
            document.LoadFromFile(file_path)
            document_text = document.GetText()
            document.Close()
            os.remove(file_path)
            self.wrapped_text = textwrap.fill(document_text, width=120)
            
            return self.wrapped_text
        
        else: return None
        
        
    def get_text_img(self):
        
        data = self.download_url()
        
        if data:
            image = Image.open(BytesIO(data))
            reader = easyocr.Reader(['en'])
            result = reader.readtext(image=image)
            detected_text = ' '.join([text for (bbox, text, prob) in result])
            
            return detected_text
        
        else: return None
    
    def get_text_csv(self):
        
        data = self.download_url()
        
        if data:
            data = data.decode('utf-8')
            
            return data
        else: return None
    
    def main(self):
        texts = self.get_text_pdf()
        invoice_numbers = []
        # print(texts[0])
        for text in texts:
            if self.extract_invoice_number(text):
                invoice_numbers.append(self.extract_invoice_number(text)[0])
                
        return invoice_numbers[0] if invoice_numbers else None
    
@app.route("/")
def explain():
    return """
    This method is not allowed for a private server!!
    <br><br>
    Please use one of the following endpoints:
    <br><br>
    <b>/extractPO</b> - Extracts the Purchase Order (PO) number using Regular Expressions. (POST method, JSON input: {"path_url": "URL or file path"})
    <br>
    Returns the extracted PO number. (JSON output: {"invoice_no": "PO number"})
    <br><br>
    <b>/get_text</b> - Returns the text extracted from the provided PDF , DOC, CSV or IMG file. (POST method, JSON input: {"path_url": "URL or file path"})
    <br>
    Supports PDF, DOCX, CSV, and image files (JPG, JPEG, PNG). (JSON output: {"text": "Extracted text"})
    """
@app.route("/extractPO",methods=['POST'])
def extractor():
        # Check if request data is JSON
    if request.is_json:
        data = request.json
        pth_url = data.get('path_url')
        if pth_url:
            obj = PO_num_extracter(pth_url)
            invoice_num = obj.main()
            return jsonify({'invoice_no': invoice_num}), 200
    else:
        return jsonify({'error': 'String parameter is missing'}), 400
    
@app.route("/get_text",methods=['POST'])
def text_parser():
        # Check if request data is JSON
    if request.is_json:
        data = request.json
        pth_url = data.get('path_url')
        
        if pth_url:
            
            obj = PO_num_extracter(pth_url)
            
            parsed_url = urlparse(pth_url)
            _, file_extension = os.path.splitext(parsed_url.path)
            
            if file_extension.lower() in ('.docx','.doc'):
                text = obj.get_text_doc()
            elif file_extension.lower() in ('.csv','.xlsx','.xls'):
                text = obj.get_text_csv()
            elif file_extension.lower() in ('.jpg', '.jpeg', '.png','.svg'):
                text = obj.get_text_img()
            elif file_extension.lower() == '.pdf':
                text = obj.get_text_pdf()
                text = text[0] if text else None
            else:
                url_type = "unknown"            
            
            if text:
                return jsonify({'text': text}), 200
            else:
                return jsonify({'error': "Can't extract data from the URL"}), 404

    else:
        return jsonify({'error': 'String parameter is missing'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
