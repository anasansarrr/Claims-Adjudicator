"""
Medical Document Generator
Generates sample OPD documents: Prescriptions, Bills, Lab Reports, Pharmacy Bills
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import json

# Sample Data
DOCTORS = [
    {"name": "Dr. Rajesh Kumar", "qual": "MBBS, MD", "reg": "KA/12345/2015", "specialty": "General Medicine"},
    {"name": "Dr. Priya Sharma", "qual": "MBBS, DNB", "reg": "MH/67890/2018", "specialty": "Pediatrics"},
    {"name": "Dr. Amit Patel", "qual": "MBBS, MS", "reg": "DL/34567/2020", "specialty": "Orthopedics"},
    {"name": "Dr. Sunita Reddy", "qual": "MBBS, DM", "reg": "TN/45678/2016", "specialty": "Cardiology"},
    {"name": "Dr. Vikram Singh", "qual": "MBBS, MD", "reg": "UP/23456/2019", "specialty": "Dermatology"},
]

HOSPITALS = [
    {"name": "City Care Hospital", "addr": "123 MG Road, Bangalore 560001", "gst": "29AABCT1234F1ZP", "phone": "080-12345678"},
    {"name": "LifeLine Medical Center", "addr": "456 Link Road, Mumbai 400050", "gst": "27AABCL5678G1ZQ", "phone": "022-87654321"},
    {"name": "Apollo Clinic", "addr": "789 Nehru Place, Delhi 110019", "gst": "07AABCA9012H1ZR", "phone": "011-23456789"},
    {"name": "Fortis Healthcare", "addr": "321 Anna Nagar, Chennai 600040", "gst": "33AABCF3456I1ZS", "phone": "044-98765432"},
]

PHARMACIES = [
    {"name": "MedPlus Pharmacy", "license": "KA-BLR-2345", "gst": "29AABCM1234J1ZT"},
    {"name": "Apollo Pharmacy", "license": "MH-MUM-6789", "gst": "27AABCA5678K1ZU"},
    {"name": "Netmeds Store", "license": "DL-DEL-3456", "gst": "07AABCN9012L1ZV"},
]

DIAGNOSES = [
    ("Viral Fever", ["Fever", "Body ache", "Fatigue"]),
    ("Upper Respiratory Tract Infection", ["Cough", "Cold", "Sore throat"]),
    ("Gastroenteritis", ["Loose stools", "Abdominal pain", "Nausea"]),
    ("Migraine", ["Headache", "Nausea", "Photophobia"]),
    ("Allergic Rhinitis", ["Sneezing", "Runny nose", "Itchy eyes"]),
    ("Lower Back Pain", ["Back pain", "Stiffness", "Limited mobility"]),
    ("Hypertension", ["Headache", "Dizziness", "Routine checkup"]),
    ("Type 2 Diabetes", ["Increased thirst", "Frequent urination", "Fatigue"]),
]

MEDICINES = [
    {"name": "Paracetamol", "strength": "500mg", "form": "Tab", "price": 2.5},
    {"name": "Paracetamol", "strength": "650mg", "form": "Tab", "price": 3.0},
    {"name": "Amoxicillin", "strength": "500mg", "form": "Cap", "price": 12.0},
    {"name": "Azithromycin", "strength": "500mg", "form": "Tab", "price": 45.0},
    {"name": "Omeprazole", "strength": "20mg", "form": "Cap", "price": 8.0},
    {"name": "Cetirizine", "strength": "10mg", "form": "Tab", "price": 3.5},
    {"name": "Metformin", "strength": "500mg", "form": "Tab", "price": 2.0},
    {"name": "Amlodipine", "strength": "5mg", "form": "Tab", "price": 4.5},
    {"name": "Pantoprazole", "strength": "40mg", "form": "Tab", "price": 10.0},
    {"name": "Ibuprofen", "strength": "400mg", "form": "Tab", "price": 5.0},
    {"name": "Ondansetron", "strength": "4mg", "form": "Tab", "price": 15.0},
    {"name": "Ranitidine", "strength": "150mg", "form": "Tab", "price": 6.0},
]

LAB_TESTS = {
    "CBC": [
        ("Hemoglobin", "g/dL", 12.0, 17.0),
        ("WBC Count", "/cumm", 4000, 11000),
        ("RBC Count", "million/cumm", 4.5, 5.5),
        ("Platelets", "/cumm", 150000, 450000),
        ("PCV", "%", 36, 50),
    ],
    "LFT": [
        ("SGPT (ALT)", "U/L", 10, 40),
        ("SGOT (AST)", "U/L", 10, 40),
        ("Bilirubin Total", "mg/dL", 0.2, 1.2),
        ("Alkaline Phosphatase", "U/L", 44, 147),
        ("Total Protein", "g/dL", 6.0, 8.3),
    ],
    "KFT": [
        ("Blood Urea", "mg/dL", 15, 40),
        ("Serum Creatinine", "mg/dL", 0.7, 1.3),
        ("Uric Acid", "mg/dL", 3.5, 7.2),
        ("Sodium", "mEq/L", 136, 145),
        ("Potassium", "mEq/L", 3.5, 5.1),
    ],
    "Lipid Profile": [
        ("Total Cholesterol", "mg/dL", 125, 200),
        ("Triglycerides", "mg/dL", 50, 150),
        ("HDL Cholesterol", "mg/dL", 40, 60),
        ("LDL Cholesterol", "mg/dL", 60, 130),
        ("VLDL", "mg/dL", 10, 40),
    ],
    "Blood Sugar": [
        ("Fasting Blood Sugar", "mg/dL", 70, 100),
        ("Post Prandial Blood Sugar", "mg/dL", 80, 140),
        ("HbA1c", "%", 4.0, 5.6),
    ],
}

PATIENT_NAMES = [
    "Rahul Verma", "Sneha Gupta", "Mohammed Ali", "Lakshmi Iyer", "Deepak Joshi",
    "Ananya Singh", "Karthik Nair", "Pooja Mehta", "Suresh Babu", "Fatima Khan",
    "Vijay Kumar", "Meera Patel", "Arjun Reddy", "Divya Sharma", "Ravi Shankar",
]

def random_date(start_days_ago=30, end_days_ago=0):
    """Generate random date within range"""
    days = random.randint(end_days_ago, start_days_ago)
    return datetime.now() - timedelta(days=days)

def generate_batch_number():
    return f"{random.choice('ABCDEFGHIJ')}{random.choice('KLMNOPQRST')}{random.randint(100,999)}"

def generate_expiry_date():
    months = random.randint(6, 36)
    exp = datetime.now() + timedelta(days=months*30)
    return exp.strftime("%m/%Y")

# Document Generators
class PrescriptionGenerator:
    @staticmethod
    def generate() -> dict:
        doctor = random.choice(DOCTORS)
        hospital = random.choice(HOSPITALS)
        diagnosis, symptoms = random.choice(DIAGNOSES)
        patient = random.choice(PATIENT_NAMES)
        age = random.randint(18, 75)
        sex = random.choice(["M", "F"])
        date = random_date()
        
        # Select medicines
        num_meds = random.randint(2, 5)
        prescribed_meds = random.sample(MEDICINES, num_meds)
        
        prescriptions = []
        for med in prescribed_meds:
            dosage = random.choice(["1-0-1", "1-1-1", "0-0-1", "1-0-0", "SOS"])
            duration = random.choice([3, 5, 7, 10, 14, 30])
            prescriptions.append({
                "medicine": f"{med['form']}. {med['name']} {med['strength']}",
                "dosage": dosage,
                "duration": f"{duration} days",
                "instructions": random.choice(["After food", "Before food", "With food", ""])
            })
        
        # Investigations
        investigations = random.sample(list(LAB_TESTS.keys()), random.randint(0, 3))
        
        return {
            "type": "prescription",
            "hospital": hospital,
            "doctor": doctor,
            "patient": {"name": patient, "age": age, "sex": sex},
            "date": date.strftime("%d/%m/%Y"),
            "symptoms": random.sample(symptoms, min(len(symptoms), random.randint(1, 3))),
            "diagnosis": diagnosis,
            "prescriptions": prescriptions,
            "investigations": investigations,
            "followup": (date + timedelta(days=random.choice([7, 14, 30]))).strftime("%d/%m/%Y")
        }
    
    @staticmethod
    def to_text(data: dict) -> str:
        lines = [
            "=" * 50,
            f"{data['hospital']['name']}".center(50),
            f"{data['hospital']['addr']}".center(50),
            f"Phone: {data['hospital']['phone']}".center(50),
            "=" * 50,
            f"{data['doctor']['name']}, {data['doctor']['qual']}",
            f"Reg. No: {data['doctor']['reg']} | {data['doctor']['specialty']}",
            "-" * 50,
            f"Date: {data['date']}",
            "",
            f"Patient Name: {data['patient']['name']}",
            f"Age/Sex: {data['patient']['age']} yrs / {data['patient']['sex']}",
            "",
            "Chief Complaints:",
        ]
        for s in data['symptoms']:
            lines.append(f"  • {s}")
        
        lines.extend([
            "",
            f"Diagnosis: {data['diagnosis']}",
            "",
            "Rx",
            "-" * 30,
        ])
        
        for i, p in enumerate(data['prescriptions'], 1):
            lines.append(f"{i}. {p['medicine']}")
            lines.append(f"   {p['dosage']} x {p['duration']} {p['instructions']}")
        
        if data['investigations']:
            lines.extend(["", "Investigations Advised:"])
            for inv in data['investigations']:
                lines.append(f"  • {inv}")
        
        lines.extend([
            "",
            f"Follow-up: {data['followup']}",
            "",
            f"{'_' * 20}".rjust(40),
            f"{data['doctor']['name']}".rjust(40),
            "=" * 50
        ])
        return "\n".join(lines)


class MedicalBillGenerator:
    @staticmethod
    def generate() -> dict:
        hospital = random.choice(HOSPITALS)
        doctor = random.choice(DOCTORS)
        patient = random.choice(PATIENT_NAMES)
        date = random_date()
        
        items = []
        # Consultation
        consult_fee = random.choice([300, 500, 700, 1000, 1500])
        items.append({"desc": "Consultation Fee", "amount": consult_fee})
        
        # Random tests
        if random.random() > 0.3:
            tests = random.sample(list(LAB_TESTS.keys()), random.randint(1, 3))
            for test in tests:
                items.append({"desc": f"Test - {test}", "amount": random.choice([200, 350, 500, 800, 1200])})
        
        # Procedures
        if random.random() > 0.6:
            procedures = ["Dressing", "Injection", "Nebulization", "ECG", "BP Check"]
            for proc in random.sample(procedures, random.randint(1, 2)):
                items.append({"desc": proc, "amount": random.choice([50, 100, 150, 200, 300])})
        
        subtotal = sum(item['amount'] for item in items)
        gst = round(subtotal * 0.05, 2) if random.random() > 0.5 else 0
        discount = round(subtotal * random.choice([0, 0, 0.05, 0.1]), 2)
        total = subtotal + gst - discount
        
        return {
            "type": "medical_bill",
            "bill_no": f"BILL{random.randint(10000, 99999)}",
            "hospital": hospital,
            "doctor": doctor,
            "patient": {"name": patient, "contact": f"+91 {random.randint(7000000000, 9999999999)}"},
            "date": date.strftime("%d/%m/%Y"),
            "items": items,
            "subtotal": subtotal,
            "gst": gst,
            "discount": discount,
            "total": total,
            "payment_mode": random.choice(["Cash", "Card", "UPI", "Insurance"]),
        }
    
    @staticmethod
    def to_text(data: dict) -> str:
        lines = [
            "=" * 55,
            f"{data['hospital']['name']}".center(55),
            f"{data['hospital']['addr']}".center(55),
            f"GST: {data['hospital']['gst']}".center(55),
            "=" * 55,
            f"Bill No: {data['bill_no']}".ljust(30) + f"Date: {data['date']}",
            "-" * 55,
            f"Patient: {data['patient']['name']}",
            f"Contact: {data['patient']['contact']}",
            f"Ref. By: {data['doctor']['name']}",
            "-" * 55,
            f"{'PARTICULARS':<35} {'AMOUNT':>15}",
            "-" * 55,
        ]
        
        for item in data['items']:
            lines.append(f"{item['desc']:<35} ₹{item['amount']:>12,.2f}")
        
        lines.extend([
            "-" * 55,
            f"{'Sub Total:':<35} ₹{data['subtotal']:>12,.2f}",
        ])
        
        if data['gst'] > 0:
            lines.append(f"{'GST (5%):':<35} ₹{data['gst']:>12,.2f}")
        if data['discount'] > 0:
            lines.append(f"{'Discount:':<35} -₹{data['discount']:>11,.2f}")
        
        lines.extend([
            "=" * 55,
            f"{'TOTAL:':<35} ₹{data['total']:>12,.2f}",
            "=" * 55,
            f"Payment Mode: {data['payment_mode']}",
            "",
            "Authorized Signatory".rjust(45),
            "=" * 55
        ])
        return "\n".join(lines)


class LabReportGenerator:
    @staticmethod
    def generate() -> dict:
        hospital = random.choice(HOSPITALS)
        doctor = random.choice(DOCTORS)
        patient = random.choice(PATIENT_NAMES)
        age = random.randint(20, 70)
        sex = random.choice(["M", "F"])
        date = random_date()
        
        # Select tests
        selected_tests = random.sample(list(LAB_TESTS.keys()), random.randint(1, 3))
        
        results = {}
        for test_name in selected_tests:
            test_results = []
            for param, unit, low, high in LAB_TESTS[test_name]:
                # Generate value (mostly normal, sometimes abnormal)
                if random.random() > 0.2:
                    value = round(random.uniform(low, high), 2)
                else:
                    value = round(random.uniform(low * 0.7, high * 1.3), 2)
                
                status = "Normal" if low <= value <= high else ("High" if value > high else "Low")
                test_results.append({
                    "parameter": param,
                    "value": value,
                    "unit": unit,
                    "range": f"{low}-{high}",
                    "status": status
                })
            results[test_name] = test_results
        
        return {
            "type": "lab_report",
            "report_id": f"LAB{random.randint(100000, 999999)}",
            "hospital": hospital,
            "doctor": doctor,
            "patient": {"name": patient, "age": age, "sex": sex},
            "date": date.strftime("%d/%m/%Y"),
            "collection_time": f"{random.randint(6,11)}:{random.choice(['00','15','30','45'])} AM",
            "results": results,
            "pathologist": f"Dr. {random.choice(['S. Mehta', 'R. Gupta', 'K. Rao', 'P. Das'])}"
        }
    
    @staticmethod
    def to_text(data: dict) -> str:
        lines = [
            "=" * 65,
            f"{data['hospital']['name']} - DIAGNOSTIC CENTER".center(65),
            f"{data['hospital']['addr']}".center(65),
            "NABL Accredited".center(65),
            "=" * 65,
            f"Report ID: {data['report_id']}".ljust(35) + f"Date: {data['date']}",
            f"Patient: {data['patient']['name']}".ljust(35) + f"Collection: {data['collection_time']}",
            f"Age/Sex: {data['patient']['age']} yrs / {data['patient']['sex']}".ljust(35) + f"Ref: {data['doctor']['name']}",
            "=" * 65,
        ]
        
        for test_name, params in data['results'].items():
            lines.extend([
                "",
                f">>> {test_name.upper()} <<<",
                "-" * 65,
                f"{'PARAMETER':<25} {'VALUE':>10} {'UNIT':<12} {'RANGE':<12} {'STATUS':<8}",
                "-" * 65,
            ])
            for p in params:
                flag = "*" if p['status'] != "Normal" else " "
                lines.append(f"{p['parameter']:<25} {p['value']:>10} {p['unit']:<12} {p['range']:<12} {p['status']:<8}{flag}")
        
        lines.extend([
            "",
            "=" * 65,
            "* Values outside normal range",
            "",
            f"Pathologist: {data['pathologist']}".rjust(55),
            "[Digital Signature]".rjust(55),
            "=" * 65
        ])
        return "\n".join(lines)


class PharmacyBillGenerator:
    @staticmethod
    def generate() -> dict:
        pharmacy = random.choice(PHARMACIES)
        patient = random.choice(PATIENT_NAMES)
        doctor = random.choice(DOCTORS)
        date = random_date()
        
        # Select medicines
        num_items = random.randint(2, 6)
        selected_meds = random.sample(MEDICINES, num_items)
        
        items = []
        for med in selected_meds:
            qty = random.choice([10, 14, 15, 20, 30])
            items.append({
                "medicine": f"{med['form']}. {med['name']} {med['strength']}",
                "batch": generate_batch_number(),
                "expiry": generate_expiry_date(),
                "qty": qty,
                "mrp": med['price'],
                "amount": round(med['price'] * qty, 2)
            })
        
        subtotal = sum(item['amount'] for item in items)
        gst = round(subtotal * 0.12, 2)
        discount = round(subtotal * random.choice([0, 0.05, 0.1, 0.15]), 2)
        total = round(subtotal + gst - discount, 2)
        
        return {
            "type": "pharmacy_bill",
            "bill_no": f"PH{random.randint(10000, 99999)}",
            "pharmacy": pharmacy,
            "patient": patient,
            "doctor": doctor['name'],
            "date": date.strftime("%d/%m/%Y"),
            "items": items,
            "subtotal": subtotal,
            "gst": gst,
            "discount": discount,
            "total": total,
            "payment_mode": random.choice(["Cash", "Card", "UPI"]),
        }
    
    @staticmethod
    def to_text(data: dict) -> str:
        lines = [
            "=" * 75,
            f"{data['pharmacy']['name']}".center(75),
            f"Drug License: {data['pharmacy']['license']} | GST: {data['pharmacy']['gst']}".center(75),
            "=" * 75,
            f"Bill No: {data['bill_no']}".ljust(40) + f"Date: {data['date']}",
            f"Patient: {data['patient']}".ljust(40) + f"Doctor: {data['doctor']}",
            "-" * 75,
            f"{'S.No':<5}{'Medicine':<30}{'Batch':<10}{'Exp':<8}{'Qty':<6}{'MRP':>8}{'Amount':>10}",
            "-" * 75,
        ]
        
        for i, item in enumerate(data['items'], 1):
            lines.append(
                f"{i:<5}{item['medicine']:<30}{item['batch']:<10}{item['expiry']:<8}"
                f"{item['qty']:<6}{item['mrp']:>8.2f}{item['amount']:>10.2f}"
            )
        
        lines.extend([
            "-" * 75,
            f"{'Sub Total:':>60} ₹{data['subtotal']:>10.2f}",
            f"{'GST (12%):':>60} ₹{data['gst']:>10.2f}",
        ])
        
        if data['discount'] > 0:
            lines.append(f"{'Discount:':>60} -₹{data['discount']:>9.2f}")
        
        lines.extend([
            "=" * 75,
            f"{'NET AMOUNT:':>60} ₹{data['total']:>10.2f}",
            "=" * 75,
            f"Payment: {data['payment_mode']}",
            "",
            "Thank you for your purchase!".center(75),
            "=" * 75
        ])
        return "\n".join(lines)


# Main Generator Class
class MedicalDocumentGenerator:
    """Main class to generate various medical documents"""
    
    generators = {
        "prescription": PrescriptionGenerator,
        "medical_bill": MedicalBillGenerator,
        "lab_report": LabReportGenerator,
        "pharmacy_bill": PharmacyBillGenerator,
    }
    
    @classmethod
    def generate(cls, doc_type: Optional[str] = None, output_format: str = "both") -> dict:
        """
        Generate a medical document
        
        Args:
            doc_type: Type of document (prescription, medical_bill, lab_report, pharmacy_bill)
                     If None, generates random type
            output_format: "data" for dict, "text" for formatted string, "both" for both
        
        Returns:
            Dictionary with generated document
        """
        if doc_type is None:
            doc_type = random.choice(list(cls.generators.keys()))
        
        if doc_type not in cls.generators:
            raise ValueError(f"Unknown document type: {doc_type}. Valid types: {list(cls.generators.keys())}")
        
        generator = cls.generators[doc_type]
        data = generator.generate()
        
        result = {"type": doc_type}
        if output_format in ("data", "both"):
            result["data"] = data
        if output_format in ("text", "both"):
            result["text"] = generator.to_text(data)
        
        return result
    
    @classmethod
    def generate_batch(cls, count: int = 10, doc_types: Optional[list] = None) -> list:
        """Generate multiple documents"""
        if doc_types is None:
            doc_types = list(cls.generators.keys())
        
        documents = []
        for _ in range(count):
            doc_type = random.choice(doc_types)
            documents.append(cls.generate(doc_type))
        return documents


# Demo usage
if __name__ == "__main__":
    print("=" * 80)
    print("MEDICAL DOCUMENT GENERATOR - DEMO")
    print("=" * 80)
    
    # Generate one of each type
    for doc_type in ["prescription", "medical_bill", "lab_report", "pharmacy_bill"]:
        print(f"\n{'#' * 80}")
        print(f"# {doc_type.upper().replace('_', ' ')}")
        print(f"{'#' * 80}\n")
        
        doc = MedicalDocumentGenerator.generate(doc_type, output_format="text")
        print(doc["text"])
    
    # Generate batch and save as JSON
    print("\n" + "=" * 80)
    print("Generating batch of 5 random documents...")
    batch = MedicalDocumentGenerator.generate_batch(5)
    print(f"Generated {len(batch)} documents: {[d['type'] for d in batch]}")
    
    # Save to JSON (data only)
    with open("sample_documents.json", "w") as f:
        json.dump([MedicalDocumentGenerator.generate(output_format="data") for _ in range(10)], f, indent=2)
    print("Saved 10 documents to sample_documents.json")