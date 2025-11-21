"""
Medical OPD Document Generator
Generates realistic medical documents (prescriptions, bills, reports) with PDF output,
handwriting simulation, and OCR testing features.

Requirements:
pip install reportlab pillow numpy
"""

import random
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas
from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
import io
import numpy as np

# Sample Data
STATES = ['KA', 'MH', 'DL', 'TN', 'UP', 'WB', 'GJ', 'RJ']
DOCTORS = [
    {'name': 'Dr. Rajesh Kumar', 'qualification': 'MBBS, MD (Medicine)', 'specialty': 'General Medicine'},
    {'name': 'Dr. Priya Sharma', 'qualification': 'MBBS, MS (Surgery)', 'specialty': 'Surgery'},
    {'name': 'Dr. Anil Mehta', 'qualification': 'MBBS, DM (Cardiology)', 'specialty': 'Cardiology'},
    {'name': 'Dr. Sneha Patel', 'qualification': 'MBBS, MD (Pediatrics)', 'specialty': 'Pediatrics'},
]

DIAGNOSES = [
    'Viral Fever', 'Upper Respiratory Tract Infection', 'Gastroenteritis',
    'Hypertension', 'Type 2 Diabetes Mellitus', 'Migraine', 'Allergic Rhinitis',
    'Lower Back Pain', 'Urinary Tract Infection', 'Acute Bronchitis'
]

MEDICINES = [
    {'name': 'Paracetamol', 'strength': '650mg', 'type': 'Tab', 'dosage': '1-0-1', 'price': 5},
    {'name': 'Amoxicillin', 'strength': '500mg', 'type': 'Cap', 'dosage': '1-0-1', 'price': 12},
    {'name': 'Azithromycin', 'strength': '500mg', 'type': 'Tab', 'dosage': '1-0-0', 'price': 25},
    {'name': 'Omeprazole', 'strength': '20mg', 'type': 'Cap', 'dosage': '1-0-0', 'price': 8},
    {'name': 'Cetirizine', 'strength': '10mg', 'type': 'Tab', 'dosage': '0-0-1', 'price': 3},
    {'name': 'Metformin', 'strength': '500mg', 'type': 'Tab', 'dosage': '1-0-1', 'price': 6},
    {'name': 'Amlodipine', 'strength': '5mg', 'type': 'Tab', 'dosage': '0-0-1', 'price': 4},
]

TESTS = [
    {'name': 'Complete Blood Count (CBC)', 'price': 300},
    {'name': 'Blood Sugar (Fasting)', 'price': 80},
    {'name': 'Lipid Profile', 'price': 500},
    {'name': 'Liver Function Test (LFT)', 'price': 600},
    {'name': 'Kidney Function Test (KFT)', 'price': 550},
    {'name': 'Thyroid Profile', 'price': 450},
    {'name': 'Urine Routine', 'price': 150},
    {'name': 'X-Ray Chest', 'price': 400},
    {'name': 'ECG', 'price': 200},
]

PATIENT_NAMES = ['Ramesh Singh', 'Anjali Desai', 'Vikram Reddy', 'Pooja Iyer', 'Suresh Joshi']


class MedicalDocumentGenerator:
    def __init__(self, output_dir='generated_docs'):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_random_patient(self):
        """Generate random patient details"""
        return {
            'name': random.choice(PATIENT_NAMES),
            'age': random.randint(18, 75),
            'sex': random.choice(['M', 'F']),
            'contact': f'+91 {random.randint(7000000000, 9999999999)}',
            'address': f'{random.randint(1, 999)}, {random.choice(["MG Road", "Park Street", "Nehru Nagar"])}, {random.choice(["Mumbai", "Delhi", "Bangalore"])}'
        }
    
    def generate_registration_number(self):
        """Generate doctor registration number"""
        state = random.choice(STATES)
        number = random.randint(10000, 99999)
        year = random.randint(2010, 2023)
        return f'{state}/{number}/{year}'
    
    def generate_prescription(self, filename='prescription.pdf', add_noise=False):
        """Generate a medical prescription"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Header Style
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a5490'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        # Select doctor
        doctor = random.choice(DOCTORS)
        patient = self.generate_random_patient()
        reg_no = self.generate_registration_number()
        
        # Header
        story.append(Paragraph(f"<b>{doctor['name']}</b>", header_style))
        story.append(Paragraph(doctor['qualification'], styles['Normal']))
        story.append(Paragraph(f"Reg. No: {reg_no}", styles['Normal']))
        story.append(Paragraph(f"Specialty: {doctor['specialty']}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Date
        date = datetime.now() - timedelta(days=random.randint(0, 30))
        story.append(Paragraph(f"Date: {date.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Patient Details
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Age/Sex:</b> {patient['age']}/{patient['sex']}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Diagnosis
        diagnosis = random.choice(DIAGNOSES)
        story.append(Paragraph(f"<b>Diagnosis:</b> {diagnosis}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Prescription
        story.append(Paragraph("<b>Rx (Prescription):</b>", styles['Heading2']))
        num_medicines = random.randint(2, 5)
        selected_meds = random.sample(MEDICINES, num_medicines)
        
        for i, med in enumerate(selected_meds, 1):
            duration = random.choice(['5 days', '7 days', '10 days', '14 days'])
            story.append(Paragraph(
                f"{i}. {med['type']}. {med['name']} {med['strength']}<br/>"
                f"   {med['dosage']} x {duration}",
                styles['Normal']
            ))
        
        story.append(Spacer(1, 0.2*inch))
        
        # Investigations
        if random.random() > 0.5:
            story.append(Paragraph("<b>Investigations Advised:</b>", styles['Heading2']))
            num_tests = random.randint(1, 3)
            for test in random.sample(TESTS, num_tests):
                story.append(Paragraph(f"- {test['name']}", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Follow-up
        followup = date + timedelta(days=random.randint(7, 21))
        story.append(Paragraph(f"<b>Follow-up:</b> {followup.strftime('%d/%m/%Y')}", styles['Normal']))
        
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"<i>{doctor['name']}</i>", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Add noise if requested
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_medical_bill(self, filename='medical_bill.pdf', add_noise=False):
        """Generate a medical bill/invoice"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Header
        header_style = ParagraphStyle(
            'BillHeader',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        clinic_name = random.choice(['City Hospital', 'HealthCare Clinic', 'MediPlus Hospital'])
        story.append(Paragraph(f"<b>{clinic_name}</b>", header_style))
        story.append(Paragraph("Medical Bill/Invoice", styles['Heading2']))
        story.append(Spacer(1, 0.2*inch))
        
        # Bill details
        bill_no = random.randint(10000, 99999)
        date = datetime.now() - timedelta(days=random.randint(0, 30))
        patient = self.generate_random_patient()
        
        story.append(Paragraph(f"Bill No: <b>{bill_no}</b>  |  Date: <b>{date.strftime('%d/%m/%Y')}</b>", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Contact:</b> {patient['contact']}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Bill items table
        data = [['S.No', 'Particulars', 'Amount (₹)']]
        
        # Consultation fee
        consultation_fee = random.choice([500, 700, 1000, 1500])
        data.append(['1', 'Consultation Fee', f'{consultation_fee:.2f}'])
        
        subtotal = consultation_fee
        row_num = 2
        
        # Add tests
        if random.random() > 0.3:
            num_tests = random.randint(1, 3)
            for test in random.sample(TESTS, num_tests):
                data.append([str(row_num), test['name'], f'{test["price"]:.2f}'])
                subtotal += test['price']
                row_num += 1
        
        # Add medicines
        if random.random() > 0.4:
            num_meds = random.randint(2, 4)
            for med in random.sample(MEDICINES, num_meds):
                qty = random.randint(5, 30)
                amount = med['price'] * qty
                data.append([str(row_num), f"{med['name']} {med['strength']} x{qty}", f'{amount:.2f}'])
                subtotal += amount
                row_num += 1
        
        # Totals
        data.append(['', '', ''])
        data.append(['', 'Sub Total:', f'{subtotal:.2f}'])
        gst = subtotal * 0.18
        data.append(['', 'GST (18%):', f'{gst:.2f}'])
        total = subtotal + gst
        data.append(['', '<b>TOTAL:</b>', f'<b>{total:.2f}</b>'])
        
        # Create table
        table = Table(data, colWidths=[0.8*inch, 4*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -4), 1, colors.black),
            ('LINEABOVE', (1, -3), (-1, -3), 1, colors.black),
            ('LINEABOVE', (1, -1), (-1, -1), 2, colors.black),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        # Payment details
        payment_mode = random.choice(['Cash', 'Card', 'UPI'])
        story.append(Paragraph(f"<b>Payment Mode:</b> {payment_mode}", styles['Normal']))
        
        if payment_mode in ['Card', 'UPI']:
            trans_id = ''.join(random.choices('0123456789ABCDEF', k=12))
            story.append(Paragraph(f"<b>Transaction ID:</b> {trans_id}", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_diagnostic_report(self, filename='diagnostic_report.pdf', add_noise=False):
        """Generate a diagnostic test report"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Header
        story.append(Paragraph("<b>DIAGNOSTIC CENTER</b>", styles['Title']))
        story.append(Paragraph("NABL Accredited Lab", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Patient details
        patient = self.generate_random_patient()
        date = datetime.now() - timedelta(days=random.randint(0, 7))
        report_id = f"RPT{random.randint(100000, 999999)}"
        
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Age/Sex:</b> {patient['age']}/{patient['sex']}", styles['Normal']))
        story.append(Paragraph(f"<b>Report ID:</b> {report_id}", styles['Normal']))
        story.append(Paragraph(f"<b>Date:</b> {date.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Test results
        story.append(Paragraph("<b>COMPLETE BLOOD COUNT (CBC)</b>", styles['Heading2']))
        
        # CBC results table
        cbc_data = [
            ['Test Name', 'Result', 'Normal Range', 'Unit'],
            ['Hemoglobin', f'{random.uniform(12, 16):.1f}', '13-17', 'g/dL'],
            ['WBC Count', f'{random.randint(4000, 11000)}', '4000-11000', '/cumm'],
            ['RBC Count', f'{random.uniform(4.5, 5.5):.2f}', '4.5-5.5', 'million/cumm'],
            ['Platelets', f'{random.randint(150000, 450000)}', '150000-450000', '/cumm'],
        ]
        
        table = Table(cbc_data, colWidths=[2*inch, 1.2*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("<i>End of Report</i>", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def add_noise_to_pdf(self, pdf_path):
        """Convert PDF to image and add noise for OCR testing"""
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=150)
            
            for i, img in enumerate(images):
                # Convert to numpy array
                img_array = np.array(img)
                
                # Add Gaussian noise
                noise = np.random.normal(0, 10, img_array.shape)
                noisy_img = np.clip(img_array + noise, 0, 255).astype(np.uint8)
                
                # Convert back to PIL Image
                noisy_pil = PILImage.fromarray(noisy_img)
                
                # Apply slight blur
                noisy_pil = noisy_pil.filter(ImageFilter.GaussianBlur(radius=0.5))
                
                # Save
                output_path = pdf_path.replace('.pdf', f'_noisy_page{i+1}.png')
                noisy_pil.save(output_path)
                print(f"Noisy image saved: {output_path}")
        except ImportError:
            print("pdf2image not installed. Skipping noise addition. Install with: pip install pdf2image")
    
    def generate_pharmacy_bill(self, filename='pharmacy_bill.pdf', patient_info=None, medicines_list=None, add_noise=False):
        """Generate a pharmacy bill"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Header
        header_style = ParagraphStyle(
            'PharmacyHeader',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#16a085'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        pharmacy_name = random.choice(['MedPlus Pharmacy', 'Apollo Pharmacy', 'NetMeds Retail'])
        story.append(Paragraph(f"<b>{pharmacy_name}</b>", header_style))
        story.append(Paragraph("Licensed Retail Pharmacy", styles['Normal']))
        
        # License details
        license_no = f"DL-{random.randint(10000, 99999)}"
        gst_no = f"{random.randint(10, 99)}XXXXX{random.randint(1000, 9999)}Z{random.randint(1, 9)}"
        story.append(Paragraph(f"Drug License No: {license_no}", styles['Normal']))
        story.append(Paragraph(f"GST No: {gst_no}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Bill details
        bill_no = random.randint(10000, 99999)
        date = datetime.now() - timedelta(days=random.randint(0, 30))
        
        if patient_info is None:
            patient_info = self.generate_random_patient()
        
        story.append(Paragraph(f"Bill No: <b>PH-{bill_no}</b>  |  Date: <b>{date.strftime('%d/%m/%Y %H:%M')}</b>", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(f"<b>Customer:</b> {patient_info['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Contact:</b> {patient_info['contact']}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Medicines table
        data = [['S.No', 'Medicine Name', 'Batch', 'Exp', 'Qty', 'MRP', 'Amount']]
        
        if medicines_list is None:
            medicines_list = random.sample(MEDICINES, random.randint(2, 5))
        
        subtotal = 0
        for i, med in enumerate(medicines_list, 1):
            batch = f"{random.choice(['AB', 'CD', 'XY'])}{random.randint(100, 999)}"
            exp_month = random.randint(1, 12)
            exp_year = random.randint(25, 27)
            exp_date = f"{exp_month:02d}/{exp_year}"
            qty = random.randint(5, 30)
            mrp = med['price']
            amount = mrp * qty
            subtotal += amount
            
            data.append([
                str(i),
                f"{med['name']} {med['strength']}",
                batch,
                exp_date,
                str(qty),
                f"₹{mrp}",
                f"₹{amount}"
            ])
        
        # Add totals
        data.append(['', '', '', '', '', '', ''])
        data.append(['', '', '', '', '', 'Sub Total:', f'₹{subtotal}'])
        
        discount = subtotal * random.choice([0, 0.05, 0.10])
        if discount > 0:
            data.append(['', '', '', '', '', 'Discount:', f'-₹{discount:.2f}'])
            subtotal -= discount
        
        gst = subtotal * 0.12  # 12% GST for medicines
        data.append(['', '', '', '', '', 'GST (12%):', f'₹{gst:.2f}'])
        total = subtotal + gst
        data.append(['', '', '', '', '', '<b>Net Amount:</b>', f'<b>₹{total:.2f}</b>'])
        
        # Create table
        table = Table(data, colWidths=[0.5*inch, 2*inch, 0.7*inch, 0.7*inch, 0.5*inch, 0.8*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -len(data)+6), 1, colors.black),
            ('LINEABOVE', (5, -5), (-1, -5), 1, colors.black),
            ('LINEABOVE', (5, -1), (-1, -1), 2, colors.black),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        # Payment details
        payment_mode = random.choice(['Cash', 'Card', 'UPI', 'Digital Wallet'])
        story.append(Paragraph(f"<b>Payment Mode:</b> {payment_mode}", styles['Normal']))
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("<i>Thank you for your purchase!</i>", styles['Normal']))
        story.append(Paragraph("<i>Keep medicines away from children</i>", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_complete_claimant_set(self, claimant_name=None, claimant_folder=None, add_noise=False):
        """Generate all 4 documents for a single claimant"""
        # Generate or use provided patient info
        if claimant_name:
            patient = self.generate_random_patient()
            patient['name'] = claimant_name
        else:
            patient = self.generate_random_patient()
        
        # Create folder for this claimant
        if claimant_folder is None:
            claimant_folder = patient['name'].replace(' ', '_')
        
        claimant_path = f"{self.output_dir}/{claimant_folder}"
        import os
        os.makedirs(claimant_path, exist_ok=True)
        
        # Store original output_dir
        original_output = self.output_dir
        self.output_dir = claimant_path
        
        print(f"\n{'='*60}")
        print(f"Generating documents for: {patient['name']}")
        print(f"{'='*60}")
        
        # Select medicines and tests (to be consistent across documents)
        selected_medicines = random.sample(MEDICINES, random.randint(3, 5))
        selected_tests = random.sample(TESTS, random.randint(1, 3))
        diagnosis = random.choice(DIAGNOSES)
        
        # 1. Generate Prescription
        print("  [1/4] Generating Prescription...")
        prescription_path = self.generate_prescription_for_claimant(
            'prescription.pdf', 
            patient, 
            selected_medicines, 
            selected_tests,
            diagnosis,
            add_noise
        )
        
        # 2. Generate Lab Results
        print("  [2/4] Generating Lab Results...")
        lab_path = self.generate_diagnostic_report_for_claimant(
            'lab_results.pdf',
            patient,
            selected_tests,
            add_noise
        )
        
        # 3. Generate Medical Bill
        print("  [3/4] Generating Medical Bill...")
        medical_bill_path = self.generate_medical_bill_for_claimant(
            'medical_bill.pdf',
            patient,
            selected_tests,
            add_noise
        )
        
        # 4. Generate Pharmacy Bill
        print("  [4/4] Generating Pharmacy Bill...")
        pharmacy_bill_path = self.generate_pharmacy_bill(
            'pharmacy_bill.pdf',
            patient,
            selected_medicines,
            add_noise
        )
        
        # Restore original output_dir
        self.output_dir = original_output
        
        print(f"✓ Complete set generated in: {claimant_path}/")
        
        return {
            'claimant': patient['name'],
            'folder': claimant_path,
            'documents': {
                'prescription': prescription_path,
                'lab_results': lab_path,
                'medical_bill': medical_bill_path,
                'pharmacy_bill': pharmacy_bill_path
            }
        }
    
    def generate_prescription_for_claimant(self, filename, patient, medicines, tests, diagnosis, add_noise):
        """Generate prescription with specific patient and medicines"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a5490'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        doctor = random.choice(DOCTORS)
        reg_no = self.generate_registration_number()
        
        # Header
        story.append(Paragraph(f"<b>{doctor['name']}</b>", header_style))
        story.append(Paragraph(doctor['qualification'], styles['Normal']))
        story.append(Paragraph(f"Reg. No: {reg_no}", styles['Normal']))
        story.append(Paragraph(f"Specialty: {doctor['specialty']}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        date = datetime.now() - timedelta(days=random.randint(0, 7))
        story.append(Paragraph(f"Date: {date.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Patient Details
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Age/Sex:</b> {patient['age']}/{patient['sex']}", styles['Normal']))
        story.append(Paragraph(f"<b>Contact:</b> {patient['contact']}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Diagnosis
        story.append(Paragraph(f"<b>Diagnosis:</b> {diagnosis}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Prescription
        story.append(Paragraph("<b>Rx (Prescription):</b>", styles['Heading2']))
        for i, med in enumerate(medicines, 1):
            duration = random.choice(['5 days', '7 days', '10 days', '14 days'])
            story.append(Paragraph(
                f"{i}. {med['type']}. {med['name']} {med['strength']}<br/>"
                f"   {med['dosage']} x {duration}",
                styles['Normal']
            ))
        
        story.append(Spacer(1, 0.2*inch))
        
        # Investigations
        story.append(Paragraph("<b>Investigations Advised:</b>", styles['Heading2']))
        for test in tests:
            story.append(Paragraph(f"- {test['name']}", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        followup = date + timedelta(days=14)
        story.append(Paragraph(f"<b>Follow-up:</b> {followup.strftime('%d/%m/%Y')}", styles['Normal']))
        
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"<i>{doctor['name']}</i>", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_diagnostic_report_for_claimant(self, filename, patient, tests, add_noise):
        """Generate diagnostic report for specific patient and tests"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        story.append(Paragraph("<b>DIAGNOSTIC CENTER</b>", styles['Title']))
        story.append(Paragraph("NABL Accredited Lab", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        date = datetime.now() - timedelta(days=random.randint(0, 5))
        report_id = f"RPT{random.randint(100000, 999999)}"
        
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Age/Sex:</b> {patient['age']}/{patient['sex']}", styles['Normal']))
        story.append(Paragraph(f"<b>Contact:</b> {patient['contact']}", styles['Normal']))
        story.append(Paragraph(f"<b>Report ID:</b> {report_id}", styles['Normal']))
        story.append(Paragraph(f"<b>Date:</b> {date.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Generate results for each test
        for test in tests:
            story.append(Paragraph(f"<b>{test['name'].upper()}</b>", styles['Heading2']))
            
            if 'CBC' in test['name'] or 'Blood Count' in test['name']:
                cbc_data = [
                    ['Test Name', 'Result', 'Normal Range', 'Unit'],
                    ['Hemoglobin', f'{random.uniform(12, 16):.1f}', '13-17', 'g/dL'],
                    ['WBC Count', f'{random.randint(4000, 11000)}', '4000-11000', '/cumm'],
                    ['RBC Count', f'{random.uniform(4.5, 5.5):.2f}', '4.5-5.5', 'million/cumm'],
                    ['Platelets', f'{random.randint(150000, 450000)}', '150000-450000', '/cumm'],
                ]
            elif 'Lipid' in test['name']:
                cbc_data = [
                    ['Test Name', 'Result', 'Normal Range', 'Unit'],
                    ['Total Cholesterol', f'{random.randint(150, 240)}', '<200', 'mg/dL'],
                    ['HDL Cholesterol', f'{random.randint(40, 60)}', '>40', 'mg/dL'],
                    ['LDL Cholesterol', f'{random.randint(70, 160)}', '<100', 'mg/dL'],
                    ['Triglycerides', f'{random.randint(80, 180)}', '<150', 'mg/dL'],
                ]
            elif 'Sugar' in test['name'] or 'Blood Sugar' in test['name']:
                cbc_data = [
                    ['Test Name', 'Result', 'Normal Range', 'Unit'],
                    ['Fasting Blood Sugar', f'{random.randint(80, 126)}', '70-100', 'mg/dL'],
                ]
            else:
                cbc_data = [
                    ['Test Name', 'Result', 'Status'],
                    [test['name'], 'Normal', '✓ Within Range'],
                ]
            
            table = Table(cbc_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("<i>End of Report</i>", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_medical_bill_for_claimant(self, filename, patient, tests, add_noise):
        """Generate medical bill for specific patient and tests"""
        doc = SimpleDocTemplate(f'{self.output_dir}/{filename}', pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        header_style = ParagraphStyle(
            'BillHeader',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        clinic_name = random.choice(['City Hospital', 'HealthCare Clinic', 'MediPlus Hospital'])
        story.append(Paragraph(f"<b>{clinic_name}</b>", header_style))
        story.append(Paragraph("Medical Bill/Invoice", styles['Heading2']))
        story.append(Spacer(1, 0.2*inch))
        
        bill_no = random.randint(10000, 99999)
        date = datetime.now() - timedelta(days=random.randint(0, 7))
        
        story.append(Paragraph(f"Bill No: <b>MB-{bill_no}</b>  |  Date: <b>{date.strftime('%d/%m/%Y')}</b>", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(f"<b>Patient Name:</b> {patient['name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Contact:</b> {patient['contact']}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Bill items table
        data = [['S.No', 'Particulars', 'Amount (₹)']]
        
        consultation_fee = random.choice([500, 700, 1000, 1500])
        data.append(['1', 'Consultation Fee', f'{consultation_fee:.2f}'])
        
        subtotal = consultation_fee
        row_num = 2
        
        for test in tests:
            data.append([str(row_num), test['name'], f'{test["price"]:.2f}'])
            subtotal += test['price']
            row_num += 1
        
        data.append(['', '', ''])
        data.append(['', 'Sub Total:', f'{subtotal:.2f}'])
        gst = subtotal * 0.18
        data.append(['', 'GST (18%):', f'{gst:.2f}'])
        total = subtotal + gst
        data.append(['', '<b>TOTAL:</b>', f'<b>{total:.2f}</b>'])
        
        table = Table(data, colWidths=[0.8*inch, 4*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -4), 1, colors.black),
            ('LINEABOVE', (1, -3), (-1, -3), 1, colors.black),
            ('LINEABOVE', (1, -1), (-1, -1), 2, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        payment_mode = random.choice(['Cash', 'Card', 'UPI'])
        story.append(Paragraph(f"<b>Payment Mode:</b> {payment_mode}", styles['Normal']))
        
        doc.build(story)
        
        if add_noise:
            self.add_noise_to_pdf(f'{self.output_dir}/{filename}')
        
        return f'{self.output_dir}/{filename}'
    
    def generate_batch_claimants(self, num_claimants=5, claimant_names=None, add_noise=False):
        """Generate complete document sets for multiple claimants"""
        results = []
        
        print(f"\n{'#'*60}")
        print(f"  GENERATING DOCUMENTS FOR {num_claimants} CLAIMANTS")
        print(f"{'#'*60}")
        
        for i in range(num_claimants):
            if claimant_names and i < len(claimant_names):
                claimant_name = claimant_names[i]
            else:
                claimant_name = None
            
            result = self.generate_complete_claimant_set(
                claimant_name=claimant_name,
                add_noise=add_noise
            )
            results.append(result)
        
        print(f"\n{'#'*60}")
        print(f"  ✓ ALL DOCUMENTS GENERATED SUCCESSFULLY")
        print(f"{'#'*60}\n")
        
        # Print summary
        print("SUMMARY:")
        for result in results:
            print(f"\n  Claimant: {result['claimant']}")
            print(f"  Folder: {result['folder']}")
            print(f"    - Prescription: ✓")
            print(f"    - Lab Results: ✓")
            print(f"    - Medical Bill: ✓")
            print(f"    - Pharmacy Bill: ✓")
        
        return results


# Example usage
if __name__ == "__main__":
    generator = MedicalDocumentGenerator(output_dir='medical_docs')
    
    # ============================================================
    # OPTION 1: Generate complete sets for multiple claimants
    # ============================================================
    
    # Generate for 5 claimants with random names
    generator.generate_batch_claimants(num_claimants=5, add_noise=False)
    
    # OR generate with specific claimant names
    # claimant_names = ['Rajesh Kumar', 'Priya Sharma', 'Amit Patel', 'Sunita Reddy']
    # generator.generate_batch_claimants(num_claimants=4, claimant_names=claimant_names, add_noise=False)
    
    # ============================================================
    # OPTION 2: Generate complete set for a single claimant
    # ============================================================
    # result = generator.generate_complete_claimant_set(claimant_name='Vikram Singh', add_noise=False)
    # print(f"\nDocuments generated in: {result['folder']}")
    
    # ============================================================
    # OPTION 3: Generate individual documents (old method)
    # ============================================================
    # generator.generate_prescription('sample_prescription.pdf')
    # generator.generate_medical_bill('sample_bill.pdf')
    # generator.generate_diagnostic_report('sample_report.pdf')
    # generator.generate_pharmacy_bill('sample_pharmacy.pdf')
    
    print("\n✓ Document generation complete! Check the 'medical_docs' folder.")