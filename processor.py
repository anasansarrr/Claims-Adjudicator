"""
Medical Claim Adjudication Processor
Contains all the core business logic for claim processing
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import re
import google.generativeai as genai
from PIL import Image
import pytesseract
import traceback
from PIL import Image
import fitz
import uuid
from db_manager import DatabaseManager

# Initialize OCR once (English only)

class ClaimProcessor:
    """
    Comprehensive medical claim adjudication system implementing all adjudication rules.
    Processes documents, extracts data, and validates against policy rules in specified order.
    """
    
    def __init__(self, policy_path: str):
        """Initialize with policy configuration and database"""
        
        # 1. Initialize Database Manager FIRST
        try:
            self.db = DatabaseManager()
            print("✓ Database connection initialized")
        except Exception as e:
            print(f"✗ Database initialization failed: {e}")
            raise
        
        # 2. Load policy configuration (may use database)
        try:
            self.policy = self._load_policy(policy_path)
            print(f"✓ Policy loaded: {self.policy.get('policy_id', 'Unknown')}")
        except Exception as e:
            print(f"✗ Policy loading failed: {e}")
            raise
        
        # 3. Load Gemini API credentials from environment
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Validate Gemini credentials
        if not self.gemini_api_key:
            raise ValueError("Gemini API key not configured. Check .env file for GEMINI_API_KEY.")
        
        # 4. Initialize fraud indicators list
        self.fraud_indicators = []
        
        # 5. Initialize Gemini client
        try:
            genai.configure(api_key=self.gemini_api_key)
            # Use gpt-3.5-turbo-1106 equivalent model
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("✓ Gemini client initialized")
        except Exception as e:
            print(f"✗ Gemini initialization failed: {e}")
            raise
    
    def _load_policy(self, policy_path: str) -> Dict:
        """Load policy configuration from JSON file or database"""
        # First try to load from file
        with open(policy_path, 'r') as f:
            policy = json.load(f)
        
        # If policy_id exists, sync with database
        if policy.get('policy_id'):
            db_policy = self.db.get_policy(policy['policy_id'])
            if not db_policy:
                # Create policy in database if it doesn't exist
                self.db.create_policy(policy)
            else:
                # Use database version if it exists (database is source of truth)
                policy = db_policy.get('policy_config', policy)
        
        return policy
    
    # ==================== DOCUMENT PROCESSING ====================
    
    def read_document(self, file_path: str) -> str:
        """Read document from file path and extract text content"""
        print(f"[READ_DOCUMENT] Starting to read: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = file_path.lower().split('.')[-1]
        print(f"[READ_DOCUMENT] File extension: {file_ext}")
        
        try:
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                result = self._read_image(file_path)
            elif file_ext == 'pdf':
                result = self._read_pdf(file_path)
            elif file_ext == 'txt':
                result = self._read_text(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            print(f"[READ_DOCUMENT] Successfully extracted {len(result)} characters")
            return result
            
        except Exception as e:
            print(f"[READ_DOCUMENT] ERROR: {str(e)}")
            raise
   
    def _read_image(self, file_path: str) -> str:
        """Extract text from image using Tesseract OCR"""
        print(f"[READ_IMAGE] Processing image: {file_path}")
        try:
            image = Image.open(file_path)
            print(f"[READ_IMAGE] Image opened successfully, size: {image.size}")
            
            text_content = pytesseract.image_to_string(image)
            print(f"[READ_IMAGE] OCR extracted {len(text_content)} characters")
            
            if not text_content or len(text_content.strip()) < 10:
                raise ValueError("Could not extract sufficient text from image. Image may be unclear or empty.")
            
            return text_content.strip()
        except Exception as e:
            print(f"[READ_IMAGE] ERROR: {str(e)}")
            raise ValueError(f"Failed to read image with Tesseract: {str(e)}")

    def _read_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        print(f"[READ_PDF] Processing PDF: {file_path}")
        try:
            doc = fitz.open(file_path)
            print(f"[READ_PDF] PDF opened, {len(doc)} pages")
            pages_text = []
            
            for i, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    pages_text.append(page_text)
                    print(f"[READ_PDF] Page {i+1}: extracted {len(page_text)} characters")
            
            doc.close()
            
            text_content = "\n\n".join(pages_text).strip()
            print(f"[READ_PDF] Total extracted: {len(text_content)} characters")
            
            if not text_content or len(text_content) < 10:
                raise ValueError("Could not extract sufficient text from PDF. PDF may be image-based or empty.")
            
            return text_content
            
        except Exception as e:
            print(f"[READ_PDF] ERROR: {str(e)}")
            raise ValueError(f"Failed to read PDF: {str(e)}")
        
    def _read_text(self, file_path: str) -> str:
        """Read plain text file"""
        print(f"[READ_TEXT] Processing text file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            print(f"[READ_TEXT] Read {len(text_content)} characters")
            
            if not text_content or len(text_content.strip()) < 10:
                raise ValueError("Text file is empty or too short.")
            
            return text_content.strip()
        except Exception as e:
            print(f"[READ_TEXT] ERROR: {str(e)}")
            raise ValueError(f"Failed to read text file: {str(e)}")
        
    
    
    # ==================== LLM EXTRACTION ====================
    
    def extract_claim_data(self, document_text: str, claim_date: str = None, 
                      doc_type: str = None) -> Dict[str, Any]:
        """
        Extract structured claim data from document text using Gemini AI model.
        
        Args:
            document_text: Extracted text from document
            claim_date: Claim submission date
            doc_type: Type of document (prescription, medical_bill, etc.)
        """
        print(f"[EXTRACT_CLAIM_DATA] Starting extraction for {doc_type}, text length: {len(document_text) if document_text else 0}")
        
        # Validate input
        if not isinstance(document_text, str):
            error_msg = f"Expected document_text to be a string, got {type(document_text).__name__}"
            print(f"[EXTRACT_CLAIM_DATA] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        if not document_text or len(document_text.strip()) < 10:
            error_msg = "Document text is empty or too short to process"
            print(f"[EXTRACT_CLAIM_DATA] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        # Build prompt
        prompt = self._get_extraction_prompt(doc_type)
        full_prompt = f"{prompt}\n\nDocument Type: {doc_type or 'unknown'}\n\nDocument content:\n{document_text}"
        
        print("[EXTRACT_CLAIM_DATA] Calling Gemini API...")
        
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2000,
                )
            )
            
            extracted_text = response.text
            
            # Parse JSON response
            if '```json' in extracted_text:
                extracted_text = extracted_text.split('```json')[1].split('```')[0]
            elif '```' in extracted_text:
                extracted_text = extracted_text.split('```')[1].split('```')[0]
            
            claim_data = json.loads(extracted_text.strip())
            
            # ✅ FIX: Ensure items have valid amounts
            if 'items' in claim_data:
                for item in claim_data['items']:
                    if item.get('amount') is None:
                        item['amount'] = 0
                    else:
                        item['amount'] = float(item['amount'])
            
            # ✅ FIX: Ensure total_amount is set
            if 'total_amount' not in claim_data or claim_data['total_amount'] is None:
                if 'items' in claim_data and claim_data['items']:
                    claim_data['total_amount'] = sum(item.get('amount', 0) for item in claim_data['items'])
                else:
                    claim_data['total_amount'] = 0
            
            # Add claim_date from parameter or use current date
            claim_data['claim_date'] = claim_date if claim_date else datetime.now().strftime('%Y-%m-%d')
            
            return claim_data
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse extracted data: {e}\nRaw response: {extracted_text}"
            print(f"[EXTRACT_CLAIM_DATA] JSON PARSE ERROR: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"API call failed: {str(e)}"
            print(f"[EXTRACT_CLAIM_DATA] API ERROR: {error_msg}")
            raise
        
    def _get_extraction_prompt(self, doc_type: str = None) -> str:
        """Generate prompt for AI to extract claim data based on document type"""
        
        base_prompt = """Extract medical claim information from this document and return ONLY a JSON object."""
        
        if doc_type == 'prescription':
            specific_fields = """
    Focus on extracting:
    - Doctor details (name, registration, specialization)
    - Diagnosis and symptoms
    - Prescribed medicines with dosage
    - Follow-up requirements
    """
        elif doc_type == 'medical_bill':
            specific_fields = """
    Focus on extracting:
    - Hospital/clinic details
    - Consultation fees
    - Itemized charges
    - Total amount
    - Tax and billing details
    """
        elif doc_type == 'pharmacy_bill':
            specific_fields = """
    Focus on extracting:
    - Pharmacy details
    - Individual medicine items with batch numbers
    - Quantities and prices
    - Total amount
    """
        elif doc_type == 'lab_results':
            specific_fields = """
    Focus on extracting:
    - Diagnostic center details
    - Test names and results
    - Reference ranges
    - Pathologist details
    """
        else:
            specific_fields = ""
        
        return base_prompt + specific_fields + """

    {
    "patient_name": "string",
    "patient_age": "number (if present)",
    "patient_gender": "string (Male/Female/Other if present)",
    "patient_dob": "YYYY-MM-DD (if present)",
    "employee_id": "string (if present)",
    "policy_number": "string (if present)",
    "treatment_date": "YYYY-MM-DD",
    "document_type": "medical_bill|prescription|diagnostic_report|consultation_note",
    "items": [
        {
        "description": "string (detailed description of service/medicine)",
        "category": "consultation|diagnostic|pharmacy|dental|vision|alternative_medicine",
        "amount": number,
        "quantity": number (if applicable),
        "unit_price": number (if applicable)
        }
    ],
    "total_amount": number,
    "hospital_name": "string (if present)",
    "hospital_registration": "string (if present)",
    "hospital_address": "string (if present)",
    "doctor_name": "string (if present)",
    "doctor_registration": "string (format: XX/123456/2020, if present)",
    "doctor_specialization": "string (if present)",
    "diagnosis": "string (primary diagnosis/reason for visit)",
    "diagnosis_code": "string (ICD code if present)",
    "symptoms": "string (patient symptoms if mentioned)",
    "prescription_details": "string (medicines prescribed with dosage)",
    "test_results": "string (diagnostic test results if present)",
    "treatment_summary": "string (summary of treatment provided)",
    "pre_authorization_number": "string (if present)",
    "emergency_treatment": "boolean (true if emergency case)",
    "follow_up_required": "boolean (if mentioned)",
    "billing_details": {
        "subtotal": number (if itemized),
        "tax": number (if present),
        "discount": number (if present)
    }
    }

    IMPORTANT INSTRUCTIONS:
    - DO NOT include a "claim_id" field - the system will generate this
    - Extract ALL line items separately with detailed descriptions
    - Categorize each item correctly based on the service type
    - Capture all medical information including diagnosis, symptoms, and treatment details
    - If a field is not present in the document, omit it or set to null
    - Ensure all amounts are numeric values (not strings)
    - Return ONLY the JSON, no additional text or explanations"""
    
    # ==================== STEP 1: BASIC ELIGIBILITY CHECK ====================
    
    def check_basic_eligibility(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 1: Verify policy status, waiting period, and member verification"""
        issues = []
        is_eligible = True
        
        # Get dates from policy config
        policy_start = datetime.strptime(
            self.policy.get('effective_date'),
            "%Y-%m-%d"
        )
        policy_end_str = self.policy.get('policy_end_date')
        if policy_end_str:
            policy_end = datetime.strptime(policy_end_str, '%Y-%m-%d')
        
        treatment_date = datetime.strptime(
            claim_data.get('treatment_date', claim_data.get('claim_date')), 
            '%Y-%m-%d'
        )
        
        # 1. Policy Status Check
        if not (policy_start <= treatment_date):
            issues.append({
                'code': 'POLICY_INACTIVE',
                'severity': 'critical',
                'message': f"Policy not active on treatment date {treatment_date.strftime('%Y-%m-%d')}"
            })
            is_eligible = False
        
        if policy_end_str and treatment_date > policy_end:
            issues.append({
                'code': 'POLICY_EXPIRED',
                'severity': 'critical',
                'message': f"Policy expired before treatment date"
            })
            is_eligible = False
        
        # 2. Waiting Period Check
        waiting_period_days = self.policy.get("waiting_periods", {}).get("initial_waiting", 0)
        days_since_policy_start = (treatment_date - policy_start).days
        
        if days_since_policy_start < waiting_period_days:
            issues.append({
                'code': 'WAITING_PERIOD',
                'severity': 'critical',
                'message': f"Treatment during waiting period. {waiting_period_days - days_since_policy_start} days remaining"
            })
            is_eligible = False
        
        # 3. Member Verification
        member_id = claim_data.get("member_id")
        if member_id:
            member = self.db.get_member(member_id)
            if not member:
                issues.append({
                    "code": "MEMBER_NOT_COVERED",
                    "severity": "critical",
                    "message": f"Member {member_id} not found in database"
                })
                is_eligible = False
        
        return {
            'step': 'basic_eligibility',
            'is_eligible': is_eligible,
            'issues': issues
        }
    
    # ==================== STEP 2: DOCUMENT VALIDATION ====================
    
    def validate_documents(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: Validate document completeness, authenticity, and consistency
        
        FIXED: Check for actual uploaded document types instead of policy checklist items
        """
        issues = []
        is_valid = True
        
        # Check required document types from policy
        required_doc_types = self.policy.get('claim_requirements', {}).get(
            'required_document_types', 
            ['prescription', 'medical_bill']  # Default minimum
        )
        
        submitted_doc_types = claim_data.get('document_types_submitted', [])
        
        # Only check if required document TYPES were submitted (not checklist items)
        for req_type in required_doc_types:
            # Normalize the type name for comparison
            req_type_normalized = req_type.lower().replace('_', ' ').replace('-', ' ')
            submitted_normalized = [t.lower().replace('_', ' ').replace('-', ' ') for t in submitted_doc_types]
            
            if req_type_normalized not in submitted_normalized:
                issues.append({
                    'code': 'MISSING_DOCUMENT_TYPE',
                    'severity': 'critical',
                    'message': f"Required document type not uploaded: {req_type.replace('_', ' ').title()}"
                })
                is_valid = False
        
        # Check essential data fields (not policy checklist items)
        essential_fields = {
            'patient_name': 'Patient Name',
            'treatment_date': 'Treatment Date',
            'total_amount': 'Total Amount',
            'items': 'Line Items'
        }
        
        for field, display_name in essential_fields.items():
            value = claim_data.get(field)
            if not value or (isinstance(value, list) and len(value) == 0):
                issues.append({
                    'code': 'MISSING_REQUIRED_FIELD',
                    'severity': 'critical',
                    'message': f"Required field missing: {display_name}"
                })
                is_valid = False
        
        # 2. Doctor Registration Validation (warning only if not critical)
        doctor_reg = claim_data.get('doctor_registration')
        if doctor_reg:
            if not self._validate_doctor_registration(doctor_reg):
                issues.append({
                    'code': 'DOCTOR_REG_INVALID',
                    'severity': 'warning',
                    'message': f"Invalid doctor registration format: {doctor_reg}"
                })
        else:
            # Only warning, not critical - doctor reg might be on prescription
            issues.append({
                'code': 'DOCTOR_REG_MISSING',
                'severity': 'warning',
                'message': "Doctor registration number not found in documents"
            })
        
        # 3. Date Consistency Check
        claim_date = claim_data.get('claim_date')
        treatment_date = claim_data.get('treatment_date')
        
        if claim_date and treatment_date:
            try:
                c_date = datetime.strptime(claim_date, '%Y-%m-%d')
                t_date = datetime.strptime(treatment_date, '%Y-%m-%d')
                
                if c_date < t_date:
                    issues.append({
                        'code': 'DATE_MISMATCH',
                        'severity': 'warning',  # Changed to warning - might be data extraction issue
                        'message': f"Claim date ({claim_date}) is before treatment date ({treatment_date})"
                    })
            except ValueError:
                issues.append({
                    'code': 'DATE_FORMAT_ERROR',
                    'severity': 'warning',
                    'message': "Could not validate date consistency"
                })
        
        # 4. Patient Details Check
        patient_name = claim_data.get('patient_name', '')
        if len(patient_name.strip()) < 3:
            issues.append({
                'code': 'PATIENT_NAME_INCOMPLETE',
                'severity': 'warning',
                'message': "Patient name appears incomplete or invalid"
            })
        
        # 5. Completeness Check (warnings only)
        if not claim_data.get('doctor_name'):
            issues.append({
                'code': 'DOCTOR_NAME_MISSING',
                'severity': 'warning',
                'message': "Doctor name not found in documents"
            })
        
        if not claim_data.get('hospital_name'):
            issues.append({
                'code': 'HOSPITAL_NAME_MISSING',
                'severity': 'warning',
                'message': "Hospital/clinic name not found in documents"
            })
        
        return {
            'step': 'document_validation',
            'is_valid': is_valid,
            'issues': issues
        }

    
    def _validate_doctor_registration(self, reg_number: str) -> bool:
        """Validate doctor registration number format from policy config"""
        # Get format from policy, with fallback default
        reg_format = self.policy.get('claim_requirements', {}).get(
            'doctor_registration_format',
            r'^[A-Z]{2}/\d+/\d{4}$'  # Default: "XX/123456/2020"
        )
        return bool(re.match(reg_format, reg_number))
    
    # ==================== STEP 3: COVERAGE VERIFICATION ====================
    
    def verify_coverage(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3: Check if treatment/service is covered and not excluded"""
        issues = []
        coverage_valid = True
        
        items = claim_data.get('items', [])
        exclusions = self.policy.get('exclusions', [])
        
        for item in items:
            # Check exclusions
            description = item.get('description', '').lower()
            diagnosis = claim_data.get('diagnosis', '').lower()
            
            for exclusion in exclusions:
                if exclusion.lower() in description or exclusion.lower() in diagnosis:
                    issues.append({
                        'code': 'EXCLUDED_CONDITION',
                        'severity': 'critical',
                        'message': f"Service excluded: {exclusion}",
                        'item': item['description']
                    })
                    coverage_valid = False
            
            # Check if category is covered
            category = item.get('category')
            if not self._is_category_covered(category):
                issues.append({
                    'code': 'SERVICE_NOT_COVERED',
                    'severity': 'critical',
                    'message': f"Service category not covered: {category}",
                    'item': item['description']
                })
                coverage_valid = False
        
        # Check for pre-authorization requirements
        pre_auth_issues = self._check_pre_authorization(claim_data)
        if pre_auth_issues:
            issues.extend(pre_auth_issues)
            coverage_valid = False
        
        return {
            'step': 'coverage_verification',
            'coverage_valid': coverage_valid,
            'issues': issues
        }
    
    def _is_category_covered(self, category: str) -> bool:
        """Check if a category is covered under policy"""
        coverage = self.policy.get('coverage_details', {})
        category_map = {
            'consultation': 'consultation_fees',
            'diagnostic': 'diagnostic_tests',
            'pharmacy': 'pharmacy',
            'dental': 'dental',
            'vision': 'vision',
            'alternative_medicine': 'alternative_medicine'
        }
        
        policy_key = category_map.get(category)
        if not policy_key:
            return False
        
        return coverage.get(policy_key, {}).get('covered', False)
    
    
    def _check_pre_authorization(self, claim_data):
        issues = []
        diagnostic_policy = self.policy.get('coverage_details', {}).get('diagnostic_tests', {})

        requires_pre_auth_flag = diagnostic_policy.get('pre_authorization_required', False)

        pre_auth_keywords = ["mri", "ct", "ct scan", "mri scan"]

        for item in claim_data.get('items', []):
            desc = item.get("description", "").lower()
            if any(k in desc for k in pre_auth_keywords):
                if requires_pre_auth_flag and not claim_data.get("pre_authorization_number"):
                    issues.append({
                        "code": "PRE_AUTH_MISSING",
                        "severity": "critical",
                        "message": f"Pre-authorization required for: {item['description']}"
                    })

        return issues

    # ==================== STEP 4: LIMIT VALIDATION ====================
    
    def validate_limits(self, claim_data: Dict[str, Any], coverage_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Step 4: Verify claim amounts against policy limits"""
        issues = []
        limits_valid = True
        
        total_claimed = claim_data.get('total_amount', 0)
        claim_requirements = self.policy.get('claim_requirements', {})
        coverage_details = self.policy.get('coverage_details', {})
        
        # 1. Minimum Claim Amount
        min_amount = claim_requirements.get('minimum_claim_amount', 0)
        if min_amount and total_claimed < min_amount:
            issues.append({
                'code': 'BELOW_MIN_AMOUNT',
                'severity': 'critical',
                'message': f"Claim amount ₹{total_claimed} below minimum ₹{min_amount}"
            })
            limits_valid = False
        
        # 2. Per-Claim Limit
        per_claim_limit = coverage_details.get('per_claim_limit')
        if per_claim_limit and total_claimed > per_claim_limit:
            issues.append({
                'code': 'PER_CLAIM_EXCEEDED',
                'severity': 'critical',
                'message': f"Claim amount ₹{total_claimed} exceeds per-claim limit ₹{per_claim_limit}"
            })
            limits_valid = False
        
        # 3. Annual Limit Check - GET FROM DATABASE ✅
        policy_id = claim_data.get('policy_id')
        if policy_id:
            policy_util = self.db.get_policy_utilization(policy_id)
            claims_ytd = policy_util['total_approved_ytd'] if policy_util else 0
        else:
            claims_ytd = 0
        
        annual_limit = coverage_details.get('annual_limit')
        
        if annual_limit and (claims_ytd + total_claimed) > annual_limit:
            issues.append({
                'code': 'ANNUAL_LIMIT_EXCEEDED',
                'severity': 'critical',
                'message': f"Total claims (₹{claims_ytd + total_claimed}) would exceed annual limit ₹{annual_limit}"
            })
            limits_valid = False
        
        # 4. Sub-Limit Validation - NOW WITH DATABASE QUERY
        sub_limit_issues = self._check_sub_limits(claim_data, coverage_analysis)
        if sub_limit_issues:
            issues.extend(sub_limit_issues)
        
        # 5. Late Submission Check
        timeline_days = claim_requirements.get('submission_timeline_days')
        if timeline_days:
            treatment_date = datetime.strptime(
                claim_data.get('treatment_date', claim_data.get('claim_date')), 
                '%Y-%m-%d'
            )
            claim_date = datetime.strptime(claim_data.get('claim_date'), '%Y-%m-%d')
            days_diff = (claim_date - treatment_date).days
            
            if days_diff > timeline_days:
                issues.append({
                    'code': 'LATE_SUBMISSION',
                    'severity': 'critical',
                    'message': f"Claim submitted {days_diff} days after treatment, exceeds {timeline_days} day limit"
                })
                limits_valid = False
        
        return {
            'step': 'limit_validation',
            'limits_valid': limits_valid,
            'issues': issues
        }
    
    def _check_sub_limits(self, claim_data: Dict[str, Any], coverage_analysis: Dict[str, Any]) -> List[Dict]:
        """Check category-specific sub-limits with YTD utilization from database"""
        issues = []
        policy_id = claim_data.get('policy_id')
        
        # Get YTD utilization from database for this policy
        if policy_id:
            policy_util = self.db.get_policy_utilization(policy_id)
            category_usage = policy_util.get('category_usage', {}) if policy_util else {}
        else:
            category_usage = {}
        
        for item_analysis in coverage_analysis.get('item_analysis', []):
            category = item_analysis.get('category')
            claimed_amount = item_analysis.get('claimed_amount', 0)
            
            # Get category sub-limit from policy
            category_config = self._get_category_config(category)
            sub_limit = category_config.get('sub_limit', 0) if category_config else 0
            
            if sub_limit:
                # Check YTD usage for this category
                ytd_used = category_usage.get(category, 0)
                remaining = sub_limit - ytd_used
                
                if claimed_amount > remaining:
                    issues.append({
                        'code': 'SUB_LIMIT_EXCEEDED',
                        'severity': 'warning',
                        'message': f"{category.title()} sub-limit exceeded. YTD used: ₹{ytd_used}, Limit: ₹{sub_limit}, Requested: ₹{claimed_amount}",
                        'item': item_analysis['description']
                    })
        
        return issues

    def _get_category_config(self, category: str) -> Dict:
        """Helper to get category configuration from policy"""
        category_map = {
            'consultation': 'consultation_fees',
            'diagnostic': 'diagnostic_tests',
            'pharmacy': 'pharmacy',
            'dental': 'dental',
            'vision': 'vision',
            'alternative_medicine': 'alternative_medicine'
        }
        policy_key = category_map.get(category)
        return self.policy.get('coverage_details', {}).get(policy_key, {})
    
    # ==================== STEP 5: MEDICAL NECESSITY REVIEW ====================
    
    def review_medical_necessity(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 5: Evaluate if treatment was medically necessary using LLM"""
        issues = []
        is_necessary = True
        
        diagnosis = claim_data.get('diagnosis', '')
        items = claim_data.get('items', [])
        
        if not diagnosis:
            issues.append({
                'code': 'NOT_MEDICALLY_NECESSARY',
                'severity': 'warning',
                'message': "No diagnosis provided to justify treatment"
            })
        
        # Get exclusion keywords from policy
        cosmetic_keywords = self.policy.get('medical_necessity_rules', {}).get(
            'cosmetic_keywords', 
            ['whitening', 'bleaching', 'cosmetic', 'aesthetic', 'beauty']
        )
        experimental_keywords = self.policy.get('medical_necessity_rules', {}).get(
            'experimental_keywords',
            ['experimental', 'investigational', 'trial', 'unproven']
        )
        
        # Check for cosmetic procedures
        for item in items:
            description = item.get('description', '').lower()
            if any(keyword in description for keyword in cosmetic_keywords):
                issues.append({
                    'code': 'COSMETIC_PROCEDURE',
                    'severity': 'critical',
                    'message': f"Cosmetic procedure not covered: {item['description']}"
                })
                is_necessary = False
        
        # Check for experimental treatments
        for item in items:
            description = item.get('description', '').lower()
            if any(keyword in description for keyword in experimental_keywords):
                issues.append({
                    'code': 'EXPERIMENTAL_TREATMENT',
                    'severity': 'critical',
                    'message': f"Experimental treatment not covered: {item['description']}"
                })
                is_necessary = False
        
        # Use LLM for detailed medical necessity assessment
        if diagnosis and items:
            llm_assessment = self._llm_medical_necessity_check(claim_data)
            
            if not llm_assessment['is_necessary']:
                issues.append({
                    'code': 'NOT_MEDICALLY_NECESSARY',
                    'severity': 'critical',
                    'message': llm_assessment['reason']
                })
                is_necessary = False
            
            # Add LLM warnings if any
            if llm_assessment.get('warnings'):
                for warning in llm_assessment['warnings']:
                    issues.append({
                        'code': 'MEDICAL_REVIEW_WARNING',
                        'severity': 'warning',
                        'message': warning
                    })
        
        return {
            'step': 'medical_necessity',
            'is_necessary': is_necessary,
            'issues': issues
        }
    
    def _llm_medical_necessity_check(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use Gemini LLM to evaluate medical necessity"""
        prompt = self._get_medical_necessity_prompt(claim_data)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1000,
                )
            )
            
            assessment_text = response.text
            
            if '```json' in assessment_text:
                assessment_text = assessment_text.split('```json')[1].split('```')[0]
            elif '```' in assessment_text:
                assessment_text = assessment_text.split('```')[1].split('```')[0]
            
            return json.loads(assessment_text.strip())
        except (json.JSONDecodeError, Exception):
            return {
                'is_necessary': True,
                'reason': 'Could not parse LLM response, defaulting to approval',
                'warnings': []
            }
    
    def _get_medical_necessity_prompt(self, claim_data: Dict[str, Any]) -> str:
        """Generate prompt for LLM medical necessity evaluation"""
        return f"""You are a medical claim reviewer. Evaluate if the treatment was medically necessary based on the following claim information:

CLAIM DETAILS:
- Diagnosis: {claim_data.get('diagnosis', 'Not provided')}
- Symptoms: {claim_data.get('symptoms', 'Not provided')}
- Treatment Summary: {claim_data.get('treatment_summary', 'Not provided')}
- Patient Age: {claim_data.get('patient_age', 'Not provided')}
- Patient Gender: {claim_data.get('patient_gender', 'Not provided')}
- Emergency Treatment: {claim_data.get('emergency_treatment', False)}

TREATMENTS/SERVICES PROVIDED:
{json.dumps(claim_data.get('items', []), indent=2)}

PRESCRIPTION DETAILS:
{claim_data.get('prescription_details', 'Not provided')}

TEST RESULTS:
{claim_data.get('test_results', 'Not provided')}

Evaluate the following:
1. Does the diagnosis justify the treatments provided?
2. Are the prescribed medications appropriate for the diagnosis?
3. Are diagnostic tests relevant to the diagnosis?
4. Is the treatment following standard medical protocols?
5. Are there any red flags indicating unnecessary procedures?

Return ONLY a JSON object with this structure:
{{
  "is_necessary": true/false,
  "reason": "Brief explanation of your assessment",
  "warnings": ["List of any concerns or warnings"],
  "confidence": 0.0-1.0
}}"""
    
    # ==================== FRAUD DETECTION ====================
    
    def detect_fraud_indicators(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect potential fraud indicators"""
        indicators = []
        fraud_score = 0.0
        
        fraud_config = self.policy.get('fraud_detection', {})
        high_value_threshold = fraud_config.get('high_value_threshold', 25000)
        
        # 1. Unusually high amounts
        total_amount = claim_data.get('total_amount', 0)
        if total_amount > high_value_threshold:
            score = min(0.3, (total_amount / high_value_threshold) * 0.2)
            indicators.append({
                'type': 'HIGH_VALUE',
                'severity': 'medium',
                'message': f"High-value claim: ₹{total_amount}",
                'score': score
            })
            fraud_score += score
        
        # 2. Missing critical information
        critical_fields = fraud_config.get('critical_fields', ['doctor_registration', 'hospital_name'])
        for field in critical_fields:
            if not claim_data.get(field):
                indicators.append({
                    'type': 'MISSING_INFO',
                    'severity': 'medium',
                    'message': f"Missing critical field: {field}",
                    'score': 0.2
                })
                fraud_score += 0.2
        
        # 3. Suspicious patterns in amounts
        items = claim_data.get('items', [])
        if len(items) > 2:
            round_numbers = sum(1 for item in items if item['amount'] % 1000 == 0)
            if round_numbers == len(items):
                indicators.append({
                    'type': 'SUSPICIOUS_AMOUNTS',
                    'severity': 'low',
                    'message': "All amounts are round numbers",
                    'score': 0.1
                })
                fraud_score += 0.1
        
        self.fraud_indicators = indicators
        fraud_threshold = fraud_config.get('manual_review_threshold', 0.5)
        
        return {
            'fraud_score': min(fraud_score, 1.0),
            'indicators': indicators,
            'requires_manual_review': fraud_score > fraud_threshold
        }
    
    # ==================== COVERAGE ANALYSIS ====================
    
    def analyze_coverage(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze coverage for each line item with detailed breakdown
        
        FIXED: Only include items with actual amounts (>0) from bills, 
        exclude prescription/lab result items that have no cost
        """
        item_analysis = []
        total_approved = 0
        total_rejected = 0
        total_copay = 0
        
        for item in items:
            # Skip items with no amount (typically from prescriptions/lab results)
            claimed_amount = item.get('amount', 0)
            if claimed_amount is None or claimed_amount <= 0:
                continue
            
            # Skip items that are clearly from prescriptions (dosage instructions)
            description = item.get('description', '').lower()
            prescription_indicators = [
                'after food', 'before food', 'at bedtime', 'twice daily', 
                'thrice daily', '1-0-1', '0-0-1', '1-0-0', 'for 5 days', 
                'for 3 days', 'for 7 days', 'tsp', 'teaspoon'
            ]
            if any(indicator in description for indicator in prescription_indicators) and claimed_amount == 0:
                continue
            
            # Skip lab result individual parameters (they're part of the main test)
            lab_indicators = ['hemoglobin', 'wbc count', 'rbc count', 'platelet', 
                            'neutrophils', 'lymphocytes', 'monocytes', 'eosinophils',
                            'basophils', 'hematocrit', 'pcv', 'mcv', 'mch', 'mchc']
            if any(indicator in description for indicator in lab_indicators) and claimed_amount == 0:
                continue
            
            analysis = self._analyze_item_detailed(item)
            item_analysis.append(analysis)
            
            total_approved += analysis['approved_amount']
            total_rejected += analysis['rejected_amount']
            total_copay += analysis['copay_amount']
        
        return {
            'item_analysis': item_analysis,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_copay': total_copay
        }

    
    def _analyze_item_detailed(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Detailed analysis of single item for coverage"""
        category = item['category']
        amount = item['amount']
        description = item['description'].lower()
        
        result = {
            'description': item['description'],
            'category': category,
            'claimed_amount': amount,
            'approved_amount': 0,
            'rejected_amount': 0,
            'copay_amount': 0,
            'status': 'rejected',
            'reason': '',
            'sub_limit_exceeded': False
        }
        
        # Check exclusions first
        exclusions = self.policy.get('exclusions', [])
        for exclusion in exclusions:
            if exclusion.lower() in description:
                result['rejected_amount'] = amount
                result['reason'] = f"Excluded: {exclusion}"
                return result
        
        # Route to category-specific coverage check
        if category == 'consultation':
            return self._check_consultation_coverage(item, result)
        elif category == 'diagnostic':
            return self._check_diagnostic_coverage(item, result)
        elif category == 'pharmacy':
            return self._check_pharmacy_coverage(item, result)
        elif category == 'dental':
            return self._check_dental_coverage(item, result)
        elif category == 'vision':
            return self._check_vision_coverage(item, result)
        elif category == 'alternative_medicine':
            return self._check_alternative_coverage(item, result)
        else:
            result['rejected_amount'] = amount
            result['reason'] = "Unknown category"
            return result
    
    def _check_consultation_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check consultation fee coverage"""
        policy = self.policy.get('coverage_details', {}).get('consultation_fees', {})
        amount = item['amount']
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Consultation not covered"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        copay_pct = policy.get('copay_percentage', 0)
        
        # Handle sub-limit exceeded - partial approval up to limit
        if sub_limit and amount > sub_limit:
            copay = (sub_limit * copay_pct) / 100
            result['approved_amount'] = sub_limit - copay
            result['copay_amount'] = copay
            result['rejected_amount'] = amount - sub_limit
            result['status'] = 'partial'
            result['sub_limit_exceeded'] = True
            result['reason'] = f"Partial approval: ₹{sub_limit} covered (limit), ₹{amount - sub_limit} exceeds limit, {copay_pct}% copay applied"
            return result
        
        # Full approval with copay
        copay = (amount * copay_pct) / 100
        result['approved_amount'] = amount - copay
        result['copay_amount'] = copay
        result['status'] = 'approved'
        result['reason'] = f"Approved with {copay_pct}% copay"
        return result
    
    def _is_test_covered_llm(self, description: str, covered_tests: List[str]) -> bool:
        desc = description.lower()

        for test in covered_tests:
            if test.lower() in desc:
                return True

        for test in covered_tests:
            tokens = test.lower().replace('-', ' ').split()
            if all(tok in desc for tok in tokens):
                return True

        try:
            prompt = f"""
    Determine if the medical test description refers to one of the covered diagnostic tests.
    Return only 'true' or 'false'.

    Item: "{description}"
    Covered: {covered_tests}
    """
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0)
            )
            return "true" in response.text.lower()
        except:
            return False


    
    def _check_diagnostic_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check diagnostic test coverage"""
        policy = self.policy.get('coverage_details', {}).get('diagnostic_tests', {})
        amount = item['amount']
        description = item['description'].lower()
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Diagnostics not covered"
            return result
        
        # Check if test is in covered list
        covered_tests = policy.get('covered_tests', [])
        covered = self._is_test_covered_llm(description, covered_tests)
        
        if not covered:
            result['rejected_amount'] = amount
            result['reason'] = "Test not in covered list"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        if sub_limit and amount > sub_limit:
            result['rejected_amount'] = amount
            result['reason'] = f"Exceeds diagnostic limit ₹{sub_limit}"
            result['sub_limit_exceeded'] = True
            return result
        
        result['approved_amount'] = amount
        result['status'] = 'approved'
        result['reason'] = "Covered diagnostic test"
        return result
    
    def _check_pharmacy_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check pharmacy/medicine coverage"""
        policy = self.policy.get('coverage_details', {}).get('pharmacy', {})
        amount = item['amount']
        description = item['description'].lower()
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Pharmacy not covered"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        if sub_limit and amount > sub_limit:
            result['rejected_amount'] = amount
            result['reason'] = f"Exceeds pharmacy limit ₹{sub_limit}"
            result['sub_limit_exceeded'] = True
            return result
        
        is_generic = 'generic' in description
        
        if is_generic:
            result['approved_amount'] = amount
            result['status'] = 'approved'
            result['reason'] = "Generic drug - 100% covered"
        else:
            copay_pct = policy.get('branded_drugs_copay', 0)
            copay = (amount * copay_pct) / 100
            result['approved_amount'] = amount - copay
            result['copay_amount'] = copay
            result['status'] = 'approved'
            result['reason'] = f"Branded drug - {copay_pct}% copay"
        
        return result
    
    def _check_dental_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check dental coverage"""
        policy = self.policy.get('coverage_details', {}).get('dental', {})
        amount = item['amount']
        description = item['description'].lower()
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Dental not covered"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        if sub_limit and amount > sub_limit:
            result['rejected_amount'] = amount
            result['reason'] = f"Exceeds dental limit ₹{sub_limit}"
            result['sub_limit_exceeded'] = True
            return result
        
        procedures_covered = policy.get('procedures_covered', [])
        covered = any(proc.lower() in description for proc in procedures_covered)
        
        if not covered:
            result['rejected_amount'] = amount
            result['reason'] = "Dental procedure not covered"
            return result
        
        result['approved_amount'] = amount
        result['status'] = 'approved'
        result['reason'] = "Covered dental procedure"
        return result
    
    def _check_vision_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check vision coverage"""
        policy = self.policy.get('coverage_details', {}).get('vision', {})
        amount = item['amount']
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Vision not covered"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        if sub_limit and amount > sub_limit:
            result['rejected_amount'] = amount
            result['reason'] = f"Exceeds vision limit ₹{sub_limit}"
            result['sub_limit_exceeded'] = True
            return result
        
        result['approved_amount'] = amount
        result['status'] = 'approved'
        result['reason'] = "Covered vision service"
        return result
    
    def _check_alternative_coverage(self, item: Dict, result: Dict) -> Dict:
        """Check alternative medicine coverage"""
        policy = self.policy.get('coverage_details', {}).get('alternative_medicine', {})
        amount = item['amount']
        description = item['description'].lower()
        
        if not policy.get('covered', False):
            result['rejected_amount'] = amount
            result['reason'] = "Alternative medicine not covered"
            return result
        
        covered_treatments = policy.get('covered_treatments', [])
        covered = any(treatment.lower() in description for treatment in covered_treatments)
        
        if not covered:
            result['rejected_amount'] = amount
            result['reason'] = "Treatment type not covered"
            return result
        
        sub_limit = policy.get('sub_limit', 0)
        if sub_limit and amount > sub_limit:
            result['rejected_amount'] = amount
            result['reason'] = f"Exceeds alternative medicine limit ₹{sub_limit}"
            result['sub_limit_exceeded'] = True
            return result
        
        result['approved_amount'] = amount
        result['status'] = 'approved'
        result['reason'] = "Covered alternative medicine"
        return result
    
    # ==================== FINAL ADJUDICATION ====================
    
    def make_adjudication_decision(self, claim_data: Dict[str, Any], 
                               eligibility: Dict[str, Any],
                               doc_validation: Dict[str, Any],
                               coverage_verification: Dict[str, Any],
                               limit_validation: Dict[str, Any],
                               medical_necessity: Dict[str, Any],
                               coverage_analysis: Dict[str, Any],
                               fraud_detection: Dict[str, Any]) -> Dict[str, Any]:
        """Make final adjudication decision based on all validation steps
        
        FIXED: Proper handling of partial approvals and manual review triggers
        """
        
        # Collect all issues by severity
        all_critical_issues = []
        all_warnings = []
        
        for step_result in [eligibility, doc_validation, coverage_verification, 
                        limit_validation, medical_necessity]:
            issues = step_result.get('issues', [])
            for issue in issues:
                if issue.get('severity') == 'critical':
                    all_critical_issues.append(issue)
                elif issue.get('severity') == 'warning':
                    all_warnings.append(issue)
        
        # Calculate confidence score
        confidence_score = self._calculate_comprehensive_confidence(
            claim_data, doc_validation, all_warnings, fraud_detection
        )
        
        # Get thresholds from policy
        fraud_config = self.policy.get('fraud_detection', {})
        high_value_threshold = fraud_config.get('high_value_threshold', 25000)
        fraud_threshold = fraud_config.get('fraud_threshold', 0.7)
        confidence_threshold = self.policy.get('adjudication_rules', {}).get('confidence_threshold', 0.7)
        
        total_claimed = claim_data.get('total_amount', 0)
        total_approved = coverage_analysis.get('total_approved', 0)
        total_rejected = coverage_analysis.get('total_rejected', 0)
        total_copay = coverage_analysis.get('total_copay', 0)
        
        # ========== MANUAL REVIEW TRIGGERS ==========
        manual_review_reasons = []
        
        # 1. High fraud score
        if fraud_detection.get('fraud_score', 0) > fraud_threshold:
            manual_review_reasons.append("High fraud risk detected")
        
        # 2. High-value claim
        if total_claimed > high_value_threshold:
            manual_review_reasons.append(f"High-value claim (₹{total_claimed:,.2f} > ₹{high_value_threshold:,.2f})")
        
        # 3. Low confidence
        if confidence_score < confidence_threshold:
            manual_review_reasons.append(f"Low confidence score ({confidence_score:.0%})")
        
        # 4. Fraud indicators present
        if fraud_detection.get('indicators'):
            indicator_types = [i['type'] for i in fraud_detection['indicators']]
            if 'DOCUMENT_MODIFIED' in indicator_types or 'UNUSUAL_PATTERN' in indicator_types:
                manual_review_reasons.append("Suspicious patterns detected")
        
        # ========== REJECTION CONDITIONS (Hard Stops) ==========
        
        # Check for absolute rejection conditions
        rejection_codes = {
            'POLICY_INACTIVE': "Policy not active on treatment date",
            'POLICY_EXPIRED': "Policy expired before treatment date",
            'WAITING_PERIOD': "Treatment during waiting period",
            'MEMBER_NOT_COVERED': "Member not found in policy",
            'EXCLUDED_CONDITION': "Service/condition excluded by policy",
            'COSMETIC_PROCEDURE': "Cosmetic procedure not covered",
            'EXPERIMENTAL_TREATMENT': "Experimental treatment not covered",
            'LATE_SUBMISSION': "Claim submitted after deadline"
        }
        
        hard_rejection_issues = [i for i in all_critical_issues if i['code'] in rejection_codes]
        
        if hard_rejection_issues:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                hard_rejection_issues[0]['message'],
                self._get_rejection_next_steps(hard_rejection_issues[0]['code'])
            )
        
        # ========== MANUAL REVIEW DECISION ==========
        if manual_review_reasons:
            return self._create_decision_output(
                claim_data, 'MANUAL_REVIEW', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                f"Requires manual review: {'; '.join(manual_review_reasons)}",
                "Your claim has been escalated for manual review. Our team will contact you within 3-5 business days."
            )
        
        # ========== CHECK IF BASIC VALIDATION PASSED ==========
        # Only reject for missing essential documents/fields, not checklist items
        essential_missing = [i for i in all_critical_issues 
                            if i['code'] in ['MISSING_DOCUMENT_TYPE', 'MISSING_REQUIRED_FIELD']]
        
        if essential_missing:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Essential documents or information missing",
                "Please upload all required documents and ensure patient details are complete."
            )
        
        # ========== COVERAGE-BASED DECISIONS ==========
        
        # No covered items at all
        if total_approved == 0 and total_claimed > 0:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "No items covered under policy",
                "The services claimed are not covered under your policy. Please review your coverage details."
            )
        
        # Calculate approval percentage
        if total_claimed > 0:
            approval_percentage = (total_approved / total_claimed) * 100
        else:
            approval_percentage = 0
        
        # ========== PARTIAL APPROVAL CONDITIONS ==========
        is_partial = False
        partial_reasons = []
        
        if total_rejected > 0:
            is_partial = True
            partial_reasons.append(f"₹{total_rejected:,.2f} not covered")
        
        if total_copay > 0:
            is_partial = True
            partial_reasons.append(f"₹{total_copay:,.2f} co-payment applies")
        
        # Check for sub-limit exceeded items
        sub_limit_items = [item for item in coverage_analysis.get('item_analysis', []) 
                        if item.get('sub_limit_exceeded')]
        if sub_limit_items:
            is_partial = True
            partial_reasons.append("Some items exceed sub-limits")
        
        # Check for annual/per-claim limit issues (partial, not full rejection)
        limit_exceeded_issues = [i for i in all_critical_issues 
                                if i['code'] in ['ANNUAL_LIMIT_EXCEEDED', 'PER_CLAIM_EXCEEDED']]
        if limit_exceeded_issues:
            # Approve up to limit instead of rejecting
            annual_limit = self.policy.get('coverage_details', {}).get('annual_limit')
            per_claim_limit = self.policy.get('coverage_details', {}).get('per_claim_limit')
            
            if per_claim_limit and total_approved > per_claim_limit:
                total_approved = per_claim_limit
                is_partial = True
                partial_reasons.append(f"Approved up to per-claim limit (₹{per_claim_limit:,.2f})")
        
        # ========== FINAL DECISION ==========
        
        if is_partial and total_approved > 0:
            return self._create_decision_output(
                claim_data, 'PARTIAL', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                f"Partially approved: {'; '.join(partial_reasons)}",
                f"Approved amount: ₹{total_approved:,.2f}. Patient responsibility: ₹{(total_copay + total_rejected):,.2f}. Payment will be processed within 7-10 business days."
            )
        elif total_approved > 0:
            return self._create_decision_output(
                claim_data, 'APPROVED', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Claim fully approved as per policy coverage",
                f"Your claim of ₹{total_approved:,.2f} has been approved. Payment will be processed within 7-10 business days."
            )
        else:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Unable to process claim",
                "Please contact customer support for assistance with your claim."
            )
    
    def _get_rejection_next_steps(self, rejection_code: str) -> str:
        """Get appropriate next steps based on rejection reason"""
        next_steps_map = {
            'POLICY_INACTIVE': "Please verify your policy status and effective dates.",
            'POLICY_EXPIRED': "Your policy has expired. Please renew your policy to submit new claims.",
            'WAITING_PERIOD': "This claim is within the waiting period. You can resubmit after the waiting period ends.",
            'MEMBER_NOT_COVERED': "Please verify member details match your policy records.",
            'EXCLUDED_CONDITION': "This service is explicitly excluded from your policy. Review your policy document for coverage details.",
            'COSMETIC_PROCEDURE': "Cosmetic procedures are not covered. Only medically necessary treatments are eligible.",
            'EXPERIMENTAL_TREATMENT': "Experimental treatments require special approval. Contact us for pre-authorization.",
            'LATE_SUBMISSION': "Claims must be submitted within the specified timeline. Contact support if you have extenuating circumstances."
        }
        return next_steps_map.get(rejection_code, "Please contact customer support for assistance.")

    def _create_decision_output(self, claim_data: Dict, decision: str, 
                           approved_amount: float, critical_issues: List,
                           warnings: List, confidence: float,
                           coverage_analysis: Dict, reason: str, 
                           next_steps: str) -> Dict[str, Any]:
        """Create standardized decision output
        
        FIXED: 
        1. Item status reflects final decision (not coverage eligibility)
        2. Added detailed reasoning/judgment explanation
        """
        
        # Get rejection reason codes
        rejection_reasons = []
        if decision == 'REJECTED':
            rejection_reasons = list(set([issue['code'] for issue in critical_issues]))
        
        total_claimed = claim_data.get('total_amount', 0)
        total_copay = coverage_analysis.get('total_copay', 0)
        total_rejected_items = coverage_analysis.get('total_rejected', 0)
        
        # FIXED: Update item breakdown to reflect FINAL decision
        item_breakdown = self._finalize_item_breakdown(
            coverage_analysis.get('item_analysis', []),
            decision,
            reason
        )
        
        # Build notes from warnings and observations
        notes = []
        if warnings:
            notes.extend([w['message'] for w in warnings[:3]])
        if self.fraud_indicators:
            notes.append(f"Fraud score: {len(self.fraud_indicators)} indicators detected")
        
        # BUILD DETAILED REASONING
        reasoning = self._build_judgment_reasoning(
            claim_data, decision, critical_issues, warnings,
            coverage_analysis, confidence, approved_amount
        )
        
        return {
            # Core decision fields
            'claim_id': claim_data.get('claim_id', 'N/A'),
            'decision': decision,
            'approved_amount': round(approved_amount, 2),
            'rejection_reasons': rejection_reasons,
            'confidence_score': round(confidence, 2),
            'notes': '; '.join(notes) if notes else "No additional observations",
            'next_steps': next_steps,
            
            # NEW: Detailed reasoning for the judgment
            'reasoning': reasoning,
            
            # Extended information
            'patient_name': claim_data.get('patient_name', 'N/A'),
            'employee_id': claim_data.get('employee_id', 'N/A'),
            'reason': reason,
            'total_claimed': round(total_claimed, 2),
            
            # Financial breakdown
            'deductions': {
                'copay': round(total_copay, 2),
                'rejected_items': round(total_rejected_items, 2)
            },
            'patient_payable': round(total_rejected_items + total_copay, 2),
            'insurance_payable': round(approved_amount, 2),
            
            # Detailed breakdowns
            'critical_issues': critical_issues,
            'warnings': warnings,
            'item_breakdown': item_breakdown,
            'fraud_indicators': self.fraud_indicators,
            
            # Metadata
            'adjudication_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'policy_id': self.policy.get('policy_id', 'N/A')
        }
    
    def _build_judgment_reasoning(self, claim_data: Dict, decision: str,
                              critical_issues: List, warnings: List,
                              coverage_analysis: Dict, confidence: float,
                              approved_amount: float) -> Dict[str, Any]:
        """Build detailed reasoning explaining WHY the decision was made"""
        
        reasoning = {
            'summary': '',
            'decision_factors': [],
            'validation_steps': {},
            'coverage_summary': {},
            'recommendation': ''
        }
        
        total_claimed = claim_data.get('total_amount', 0)
        
        # Decision factors based on what triggered the decision
        factors = []
        
        if decision == 'REJECTED':
            reasoning['summary'] = f"Claim REJECTED due to {len(critical_issues)} critical issue(s) that prevent approval."
            
            # Group issues by type for clearer explanation
            issue_groups = {}
            for issue in critical_issues:
                code = issue['code']
                if code not in issue_groups:
                    issue_groups[code] = []
                issue_groups[code].append(issue['message'])
            
            for code, messages in issue_groups.items():
                factor = {
                    'type': code,
                    'impact': 'blocking',
                    'description': self._get_issue_explanation(code),
                    'details': messages
                }
                factors.append(factor)
            
            reasoning['recommendation'] = "Address all critical issues listed above and resubmit the claim."
            
        elif decision == 'MANUAL_REVIEW':
            reasoning['summary'] = "Claim requires human review due to complexity or risk factors."
            
            if confidence < 0.7:
                factors.append({
                    'type': 'LOW_CONFIDENCE',
                    'impact': 'review_required',
                    'description': f"System confidence ({confidence:.0%}) is below threshold (70%)",
                    'details': ["Incomplete information or data quality issues detected"]
                })
            
            if total_claimed > 25000:
                factors.append({
                    'type': 'HIGH_VALUE',
                    'impact': 'review_required',
                    'description': f"High-value claim (₹{total_claimed:,.2f}) requires manual verification",
                    'details': ["Claims above ₹25,000 are automatically escalated"]
                })
            
            if self.fraud_indicators:
                factors.append({
                    'type': 'FRAUD_INDICATORS',
                    'impact': 'review_required',
                    'description': "Potential fraud indicators detected",
                    'details': [ind['message'] for ind in self.fraud_indicators]
                })
            
            reasoning['recommendation'] = "Claim will be reviewed by our team within 3-5 business days."
            
        elif decision == 'PARTIAL':
            total_copay = coverage_analysis.get('total_copay', 0)
            total_rejected = coverage_analysis.get('total_rejected', 0)
            
            reasoning['summary'] = f"Claim PARTIALLY APPROVED. ₹{approved_amount:,.2f} of ₹{total_claimed:,.2f} will be reimbursed."
            
            if total_copay > 0:
                factors.append({
                    'type': 'COPAY_APPLIED',
                    'impact': 'partial_deduction',
                    'description': f"Co-payment of ₹{total_copay:,.2f} applies per policy terms",
                    'details': ["Co-pay percentages vary by service category"]
                })
            
            if total_rejected > 0:
                factors.append({
                    'type': 'ITEMS_NOT_COVERED',
                    'impact': 'partial_deduction',
                    'description': f"₹{total_rejected:,.2f} not covered under policy",
                    'details': ["Some services/items are excluded or exceed limits"]
                })
            
            reasoning['recommendation'] = f"Patient is responsible for ₹{(total_copay + total_rejected):,.2f}. Approved amount will be processed for payment."
            
        elif decision == 'APPROVED':
            reasoning['summary'] = f"Claim FULLY APPROVED. ₹{approved_amount:,.2f} will be reimbursed."
            
            factors.append({
                'type': 'ALL_VALIDATIONS_PASSED',
                'impact': 'approved',
                'description': "All eligibility, coverage, and validation checks passed",
                'details': ["Policy active", "Services covered", "Within limits", "Medically necessary"]
            })
            
            reasoning['recommendation'] = "Payment will be processed within 7-10 business days."
        
        reasoning['decision_factors'] = factors
        
        # Validation steps summary
        reasoning['validation_steps'] = {
            'eligibility': 'passed' if not any(i['code'] in ['POLICY_INACTIVE', 'POLICY_EXPIRED', 'WAITING_PERIOD'] for i in critical_issues) else 'failed',
            'documents': 'passed' if not any(i['code'].startswith('MISSING_') for i in critical_issues) else 'failed',
            'coverage': 'passed' if not any(i['code'] in ['EXCLUDED_CONDITION', 'SERVICE_NOT_COVERED'] for i in critical_issues) else 'failed',
            'limits': 'passed' if not any(i['code'] in ['ANNUAL_LIMIT_EXCEEDED', 'PER_CLAIM_EXCEEDED'] for i in critical_issues) else 'failed',
            'medical_necessity': 'passed' if not any(i['code'] in ['COSMETIC_PROCEDURE', 'EXPERIMENTAL_TREATMENT', 'NOT_MEDICALLY_NECESSARY'] for i in critical_issues) else 'failed'
        }
        
        # Coverage summary
        reasoning['coverage_summary'] = {
            'total_claimed': total_claimed,
            'eligible_amount': coverage_analysis.get('total_approved', 0) + coverage_analysis.get('total_copay', 0),
            'copay_deduction': coverage_analysis.get('total_copay', 0),
            'not_covered': coverage_analysis.get('total_rejected', 0),
            'final_approved': approved_amount if decision in ['APPROVED', 'PARTIAL'] else 0
        }
        
        return reasoning
    
    def _get_issue_explanation(self, issue_code: str) -> str:
        """Get human-readable explanation for issue codes"""
        explanations = {
            'POLICY_INACTIVE': "The insurance policy was not active on the date of treatment",
            'POLICY_EXPIRED': "The insurance policy had expired before the treatment date",
            'WAITING_PERIOD': "The treatment occurred during the policy waiting period",
            'MEMBER_NOT_COVERED': "The patient is not listed as a covered member on this policy",
            'MISSING_DOCUMENT_TYPE': "Required supporting documents were not uploaded",
            'MISSING_REQUIRED_FIELD': "Essential claim information is missing from the documents",
            'DATE_MISMATCH': "Inconsistency detected between claim date and treatment date",
            'DOCTOR_REG_INVALID': "Doctor's registration number could not be verified",
            'EXCLUDED_CONDITION': "The treatment or condition is specifically excluded from coverage",
            'SERVICE_NOT_COVERED': "This type of service is not included in the policy coverage",
            'PRE_AUTH_MISSING': "Pre-authorization was required but not obtained",
            'ANNUAL_LIMIT_EXCEEDED': "The claim would exceed the annual coverage limit",
            'PER_CLAIM_EXCEEDED': "The claim amount exceeds the per-claim limit",
            'BELOW_MIN_AMOUNT': "The claim amount is below the minimum threshold",
            'LATE_SUBMISSION': "The claim was submitted after the allowed submission window",
            'COSMETIC_PROCEDURE': "Cosmetic or elective procedures are not covered",
            'EXPERIMENTAL_TREATMENT': "Experimental or investigational treatments are not covered",
            'NOT_MEDICALLY_NECESSARY': "The treatment was deemed not medically necessary"
        }
        return explanations.get(issue_code, f"Validation failed: {issue_code}")
    
    def _finalize_item_breakdown(self, item_analysis: List[Dict], 
                            final_decision: str, 
                            rejection_reason: str) -> List[Dict]:
        """Update item statuses to reflect the FINAL claim decision"""
        finalized_items = []
        
        for item in item_analysis:
            item_copy = item.copy()
            
            if final_decision == 'REJECTED':
                claimed = item_copy.get('claimed_amount', 0) or 0
                item_copy['status'] = 'rejected'
                item_copy['approved_amount'] = 0
                item_copy['copay_amount'] = 0
                item_copy['rejected_amount'] = claimed
                item_copy['final_status'] = 'rejected'
                item_copy['final_approved_amount'] = 0
                item_copy['final_reason'] = f"Claim rejected: {rejection_reason}"
                item_copy['coverage_eligible'] = False
                item_copy['coverage_analysis'] = "Not payable due to claim-level rejection"
            
            elif final_decision == 'MANUAL_REVIEW':
                item_copy['final_status'] = 'pending_review'
                item_copy['final_approved_amount'] = 0
                item_copy['final_reason'] = "Awaiting manual review"
                item_copy['coverage_eligible'] = item.get('status') == 'approved'
                item_copy['coverage_analysis'] = item.get('reason', '')
                
            elif final_decision == 'PARTIAL':
                item_copy['final_status'] = item.get('status', 'unknown')
                item_copy['final_approved_amount'] = item.get('approved_amount', 0)
                item_copy['final_reason'] = item.get('reason', '')
                
            elif final_decision == 'APPROVED':
                item_copy['final_status'] = item.get('status', 'approved')
                item_copy['final_approved_amount'] = item.get('approved_amount', 0)
                item_copy['final_reason'] = item.get('reason', '')
            
            finalized_items.append(item_copy)
        
        return finalized_items

    
    def _calculate_comprehensive_confidence(self, claim_data: Dict, 
                                           doc_validation: Dict,
                                           warnings: List,
                                           fraud_detection: Dict) -> float:
        """Calculate overall confidence score for adjudication"""
        score = 1.0
        
        # Get confidence calculation weights from policy
        confidence_config = self.policy.get('adjudication_rules', {}).get('confidence_weights', {})
        
        # Reduce for missing critical information
        missing_field_penalty = confidence_config.get('missing_field_penalty', 0.1)
        if not claim_data.get('doctor_registration'):
            score -= missing_field_penalty
        if not claim_data.get('hospital_name'):
            score -= missing_field_penalty / 2
        if not claim_data.get('doctor_name'):
            score -= missing_field_penalty / 2
        if not claim_data.get('diagnosis'):
            score -= missing_field_penalty
        
        # Reduce for warnings
        warning_penalty = confidence_config.get('warning_penalty', 0.05)
        score -= len(warnings) * warning_penalty
        
        # Reduce for fraud indicators
        fraud_impact = confidence_config.get('fraud_impact', 0.3)
        fraud_score = fraud_detection.get('fraud_score', 0)
        score -= fraud_score * fraud_impact
        
        return max(0.0, min(1.0, score))
    
    # ==================== COMPLETE PROCESSING PIPELINE ====================
    def _merge_claim_data(self, existing_data: Dict, new_data: Dict, doc_type: str) -> Dict[str, Any]:
        """
        Intelligently merge data from multiple documents.
        
        FIXED: Don't add prescription/lab items to main items list if they have no cost
        """
        if not existing_data:
            return new_data
        
        # Priority rules for different fields based on document type
        priority_map = {
            'prescription': ['doctor_name', 'doctor_registration', 'doctor_specialization', 
                            'diagnosis', 'symptoms', 'prescription_details'],
            'medical_bill': ['hospital_name', 'hospital_registration', 'hospital_address',
                            'consultation_fee', 'billing_details'],
            'pharmacy_bill': ['pharmacy_items', 'medicines_total'],
            'lab_results': ['test_results', 'diagnostic_details']
        }
        
        merged = existing_data.copy()
        
        # Merge basic patient info (prefer most complete data)
        for field in ['patient_name', 'patient_age', 'patient_gender', 'patient_dob', 
                    'employee_id', 'policy_number', 'treatment_date']:
            if new_data.get(field) and not existing_data.get(field):
                merged[field] = new_data[field]
        
        # Merge items from different documents - ONLY if they have amounts
        if 'items' in new_data and new_data['items']:
            if 'items' not in merged:
                merged['items'] = []
            
            for item in new_data['items']:
                # Add document type to each item for tracking
                item['source_document'] = doc_type
                
                # Ensure amount is not None
                if item.get('amount') is None:
                    item['amount'] = 0
                
                # Only add items with actual amounts to the main items list
                # Prescriptions and lab results typically don't have costs
                if doc_type in ['prescription', 'lab_results']:
                    # Store separately for reference but don't add to billable items
                    if f'{doc_type}_items' not in merged:
                        merged[f'{doc_type}_items'] = []
                    merged[f'{doc_type}_items'].append(item)
                else:
                    # Medical bills and pharmacy bills have actual costs
                    if item['amount'] > 0:
                        merged['items'].append(item)
        
        # Merge document-specific fields based on priority
        priority_fields = priority_map.get(doc_type, [])
        for field in priority_fields:
            if new_data.get(field):
                merged[field] = new_data[field]
        
        # Merge medical details
        if doc_type == 'prescription':
            merged['prescription_details'] = new_data.get('prescription_details', '')
            merged['diagnosis'] = new_data.get('diagnosis', merged.get('diagnosis', ''))
            merged['symptoms'] = new_data.get('symptoms', merged.get('symptoms', ''))
            # Store prescribed medicines separately for cross-reference
            merged['prescribed_medicines'] = new_data.get('items', [])
        
        if doc_type == 'lab_results':
            merged['test_results'] = new_data.get('test_results', '')
            # Store lab tests separately for reference
            merged['lab_tests'] = new_data.get('items', [])
        
        # Calculate total_amount from bills only
        if doc_type in ['medical_bill', 'pharmacy_bill'] and new_data.get('total_amount'):
            if 'bill_totals' not in merged:
                merged['bill_totals'] = {}
            merged['bill_totals'][doc_type] = new_data['total_amount']
        
        # Sum all bill totals
        if 'bill_totals' in merged:
            merged['total_amount'] = sum(merged['bill_totals'].values())
        elif 'items' in merged and merged['items']:
            merged['total_amount'] = sum(
                float(item.get('amount') or 0) for item in merged['items']
            )
        else:
            merged['total_amount'] = merged.get('total_amount', 0)
        
        # Store document-specific extracted data
        if 'documents_data' not in merged:
            merged['documents_data'] = {}
        merged['documents_data'][doc_type] = new_data
        
        return merged

    def process_claim_complete(self, file_paths: Dict[str, str], claim_date: str = None, 
                  policy_id: str = None, member_id: str = None) -> Dict[str, Any]:
        """
        Complete end-to-end claim processing with multiple documents.
        """
        claim_data = {}
        
        try:
            # Step 0: Read and Extract from ALL Documents
            print("Step 0: Reading multiple documents...")
            all_documents_text = {}
            
            # Process each document type
            for doc_type, file_path in file_paths.items():
                print(f"Processing {doc_type}: {file_path}")
                document_text = self.read_document(file_path)
                all_documents_text[doc_type] = document_text
                
                # Extract data from each document
                extracted_data = self.extract_claim_data(document_text, claim_date, doc_type)
                
                # Merge extracted data intelligently
                claim_data = self._merge_claim_data(claim_data, extracted_data, doc_type)
            
            # ✅ FIX: ALWAYS generate a NEW unique claim ID, ignore extracted ones
            # Extracted claim_ids might be duplicates or placeholder values
            original_claim_id = claim_data.get('claim_id')
            claim_data['claim_id'] = f"CLM_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8].upper()}"
            
            if original_claim_id:
                print(f"Replaced extracted claim_id '{original_claim_id}' with unique '{claim_data['claim_id']}'")
            
            # Store all document paths
            claim_data['document_paths'] = file_paths
            claim_data['document_types_submitted'] = list(file_paths.keys())
            
            # Link to policy and member
            if policy_id:
                claim_data['policy_id'] = policy_id
            if member_id:
                claim_data['member_id'] = member_id
            
            # Try to find policy and member if not provided
            if not policy_id and claim_data.get('policy_number'):
                policy = self.db.get_policy_by_number(claim_data['policy_number'])
                if policy:
                    claim_data['policy_id'] = policy['policy_id']
                    self.policy = policy.get('policy_config', self.policy)
            
            if not member_id and claim_data.get('employee_id'):
                member = self.db.get_member_by_employee_id(claim_data['employee_id'])
                if member:
                    claim_data['member_id'] = member['member_id']
            
            # MAP FIELD NAMES FOR DATABASE
            claim_data_for_db = claim_data.copy()
            claim_data_for_db['total_claimed_amount'] = claim_data.get('total_amount', 0)
            
            # Create claim record FIRST before any audit logs
            print(f"Creating claim record: {claim_data['claim_id']}")
            
            # ✅ FIX: Check if claim_id already exists (extra safety)
            existing_claim = None
            try:
                existing_claim = self.db.get_claim(claim_data['claim_id'])
            except:
                pass
            
            if existing_claim:
                # Generate a new ID if somehow it still conflicts
                claim_data['claim_id'] = f"CLM_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:12].upper()}"
                claim_data_for_db['claim_id'] = claim_data['claim_id']
                print(f"Conflict detected, using new claim_id: {claim_data['claim_id']}")
            
            db_claim_id = self.db.create_claim(claim_data_for_db)
            
            if not db_claim_id:
                raise Exception("Failed to create claim record in database")
            
            print(f"✓ Claim created successfully with ID: {claim_data['claim_id']}")
            
            # NOW we can log audit entry (after claim exists)
            self.db.log_audit(
                claim_id=claim_data['claim_id'],
                action='CREATED',
                details={
                    'file_paths': {k: os.path.basename(v) for k, v in file_paths.items()},
                    'claim_date': claim_date,
                    'document_types': list(file_paths.keys())
                }
            )
            
            # Store ALL document uploads
            for doc_type, file_path in file_paths.items():
                file_ext = file_path.split('.')[-1]
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
                
                self.db.create_document_upload(
                    claim_id=claim_data['claim_id'],
                    file_data={
                        'file_name': os.path.basename(file_path),
                        'file_type': file_ext,
                        'file_path': file_path,
                        'file_size': file_size,
                        'document_type': doc_type
                    }
                )
                
            # Step 1: Basic Eligibility Check
            print("Step 1: Checking basic eligibility...")
            eligibility = self.check_basic_eligibility(claim_data)
            if eligibility['issues']:
                self.db.create_adjudication_issues(
                    claim_data['claim_id'], 
                    eligibility['issues']
                )
            
            # Step 2: Document Validation
            print("Step 2: Validating documents...")
            doc_validation = self.validate_documents(claim_data)
            if doc_validation['issues']:
                self.db.create_adjudication_issues(
                    claim_data['claim_id'],
                    doc_validation['issues']
                )
            
            # Step 3: Coverage Verification
            print("Step 3: Verifying coverage...")
            coverage_verification = self.verify_coverage(claim_data)
            if coverage_verification['issues']:
                self.db.create_adjudication_issues(
                    claim_data['claim_id'],
                    coverage_verification['issues']
                )
            
            # Step 3.5: Coverage Analysis
            print("Step 3.5: Analyzing coverage for each item...")
            coverage_analysis = self.analyze_coverage(claim_data['items'])
            
            # Store claim items in database
            items_for_db = []
            for item_analysis in coverage_analysis['item_analysis']:
                items_for_db.append({
                    'description': item_analysis['description'],
                    'category': item_analysis['category'],
                    'claimed_amount': item_analysis['claimed_amount'],
                    'approved_amount': item_analysis['approved_amount'],
                    'rejected_amount': item_analysis['rejected_amount'],
                    'copay_amount': item_analysis['copay_amount'],
                    'status': item_analysis['status'],
                    'reason': item_analysis['reason'],
                    'sub_limit_exceeded': item_analysis.get('sub_limit_exceeded', False)
                })
            
            if items_for_db:
                self.db.create_claim_items(claim_data['claim_id'], items_for_db)
            
            # Step 4: Limit Validation
            print("Step 4: Validating limits...")
            limit_validation = self.validate_limits(claim_data, coverage_analysis)
            if limit_validation['issues']:
                self.db.create_adjudication_issues(
                    claim_data['claim_id'],
                    limit_validation['issues']
                )
            
            # Step 5: Medical Necessity Review
            print("Step 5: Reviewing medical necessity...")
            medical_necessity = self.review_medical_necessity(claim_data)
            if medical_necessity['issues']:
                self.db.create_adjudication_issues(
                    claim_data['claim_id'],
                    medical_necessity['issues']
                )
            
            # Step 6: Fraud Detection
            print("Step 6: Detecting fraud indicators...")
            fraud_detection = self.detect_fraud_indicators(claim_data)
            if fraud_detection['indicators']:
                self.db.create_fraud_indicators(
                    claim_data['claim_id'],
                    fraud_detection['indicators']
                )
            
            # Add fraud score to decision data
            fraud_detection['fraud_score'] = fraud_detection.get('fraud_score', 0)
            
            # Step 7: Final Adjudication Decision
            print("Step 7: Making final adjudication decision...")
            final_decision = self.make_adjudication_decision(
                claim_data, eligibility, doc_validation, coverage_verification,
                limit_validation, medical_necessity, coverage_analysis, fraud_detection
            )
            
            # Update claim with decision in database
            self.db.update_claim_decision(claim_data['claim_id'], final_decision)
            
            # Log audit entry for decision
            self.db.log_audit(
                claim_id=claim_data['claim_id'],
                action=final_decision['decision'],
                details={
                    'approved_amount': final_decision['approved_amount'],
                    'confidence_score': final_decision['confidence_score']
                }
            )
            
            # If approved, update policy claims_ytd
            if final_decision['decision'] == 'APPROVED' and claim_data.get('policy_id'):
                self.db.update_policy_claims_ytd(
                    claim_data['policy_id'],
                    final_decision['approved_amount']
                )
            
            print(f"✓ Claim processing complete: {final_decision['decision']}")
            print("\n================ FINAL JUDGMENT ================")
            print(json.dumps(final_decision, indent=2))
            print("================================================\n")

            return final_decision
            
        except Exception as e:
            print(f"✗ Error processing claim: {str(e)}")
            print(traceback.format_exc())
            
            # Only log error audit if claim was created
            if claim_data.get('claim_id'):
                try:
                    # Check if claim exists before logging
                    existing_claim = self.db.get_claim(claim_data['claim_id'])
                    if existing_claim:
                        self.db.log_audit(
                            claim_id=claim_data['claim_id'],
                            action='ERROR',
                            details={'error': str(e), 'traceback': traceback.format_exc()}
                        )
                except Exception as audit_error:
                    print(f"Could not log audit error: {audit_error}")
            
            raise e
        
        
    def get_claim_from_db(self, claim_id: str) -> Optional[Dict]:
        """Retrieve complete claim data from database"""
        return self.db.get_claim(claim_id)

    
    def get_policy_utilization(self, policy_id: str) -> Optional[Dict]:
        """Get policy utilization statistics from database"""
        return self.db.get_policy_utilization(policy_id)

    def get_claims_statistics(self, policy_id: str = None, 
                            start_date: str = None, 
                            end_date: str = None) -> Dict:
        """Get claims statistics from database"""
        return self.db.get_claims_statistics(policy_id, start_date, end_date)

    def get_recent_claims(self, days: int = 30, limit: int = 100) -> List[Dict]:
        """Get recent claims from database"""
        return self.db.get_recent_claims(days, limit)