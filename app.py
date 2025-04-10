from flask import Flask, render_template, request, send_file
from datetime import datetime
from xhtml2pdf import pisa
import os

app = Flask(__name__)
PDF_DIR = 'generated_reports'

# Create folder if it doesn't exist
if not os.path.exists(PDF_DIR):
    os.makedirs(PDF_DIR)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Collect form data
        data = {
            'disaster_type': request.form['disaster_type'],
            'disaster_location': request.form['disaster_location'],
            'employees_present': request.form['employees_present'],
            'people_affected': request.form['people_affected'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(PDF_DIR, filename)

        # Render the HTML for PDF
        html = render_template('report.html', **data)

        # Create the PDF
        with open(pdf_path, "w+b") as pdf_file:
            pisa.CreatePDF(html, dest=pdf_file)

        # Download the PDF
        return send_file(pdf_path, as_attachment=True)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
