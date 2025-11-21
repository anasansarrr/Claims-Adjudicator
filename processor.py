"""
Medical Claim Adjudication Processor
Contains all the core business logic for claim processing
"""
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import re
from openai import AzureOpenAI
import base64
from PIL import Image
import pdfplumber
import pytesseract
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
        
        # 3. Load Azure OpenAI credentials from environment
        self.azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.azure_api_base = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        self.model_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT')
        
        # Validate OpenAI credentials
        if not all([self.azure_api_key, self.azure_api_base, self.model_deployment]):
            raise ValueError("Azure OpenAI credentials not configured. Check .env file.")
        
        # 4. Initialize fraud indicators list
        self.fraud_indicators = []
        
        # 5. Initialize Azure OpenAI client
        try:
            self.client = AzureOpenAI(
                api_key=self.azure_api_key,
                api_version=self.azure_api_version,
                azure_endpoint=self.azure_api_base
            )
            print("✓ Azure OpenAI client initialized")
        except Exception as e:
            print(f"✗ Azure OpenAI initialization failed: {e}")
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
    
    def extract_claim_data(self, document_text: str, claim_date: str = None) -> Dict[str, Any]:
        """Extract structured claim data from document text using AI model"""
        
        print(f"[EXTRACT_CLAIM_DATA] Starting extraction, text length: {len(document_text) if document_text else 0}")
        
        # Validate input
        if not isinstance(document_text, str):
            error_msg = f"Expected document_text to be a string, got {type(document_text).__name__}"
            print(f"[EXTRACT_CLAIM_DATA] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        if not document_text or len(document_text.strip()) < 10:
            error_msg = "Document text is empty or too short to process"
            print(f"[EXTRACT_CLAIM_DATA] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        # Build simple text-based message
        messages = [
            {
                "role": "user",
                "content": f"{self._get_extraction_prompt()}\n\nDocument content:\n{document_text}"
            }
        ]
        
        print("[EXTRACT_CLAIM_DATA] Calling Azure OpenAI API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_deployment,
                messages=messages,
                temperature=0.1,
                max_tokens=2000
            )
            
            extracted_text = response.choices[0].message.content
            print(f"[EXTRACT_CLAIM_DATA] Received response, length: {len(extracted_text)}")
            
            # Parse JSON response
            if '```json' in extracted_text:
                extracted_text = extracted_text.split('```json')[1].split('```')[0]
            elif '```' in extracted_text:
                extracted_text = extracted_text.split('```')[1].split('```')[0]
            
            claim_data = json.loads(extracted_text.strip())
            print("[EXTRACT_CLAIM_DATA] Successfully parsed JSON response")
            
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
    
    def _get_extraction_prompt(self) -> str:
        """Generate prompt for AI to extract claim data"""
        return """Extract medical claim information from this document and return ONLY a JSON object with the following structure:

{
  "claim_id": "string (if present, otherwise generate unique ID)",
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
- Extract ALL line items separately with detailed descriptions
- Categorize each item correctly based on the service type
- Capture all medical information including diagnosis, symptoms, and treatment details
- If a field is not present in the document, omit it or set to null
- Ensure all amounts are numeric values
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
        """Step 2: Validate document completeness, authenticity, and consistency"""
        issues = []
        is_valid = True
        
        # Get required fields from policy
        required_fields_config = self.policy.get('claim_requirements', {}).get('documents_required', [])
        
        # Default required fields if not in policy
        default_required = ['patient_name', 'treatment_date', 'total_amount', 'items']
        fields_to_check = required_fields_config if required_fields_config else default_required
        
        for field in fields_to_check:
            if not claim_data.get(field):
                issues.append({
                    'code': 'MISSING_DOCUMENTS',
                    'severity': 'critical',
                    'message': f"Required field missing: {field.replace('_', ' ').title()}"
                })
                is_valid = False
        
        # 2. Doctor Registration Validation
        doctor_reg = claim_data.get('doctor_registration')
        if doctor_reg:
            if not self._validate_doctor_registration(doctor_reg):
                issues.append({
                    'code': 'DOCTOR_REG_INVALID',
                    'severity': 'critical',
                    'message': f"Invalid doctor registration format: {doctor_reg}"
                })
                is_valid = False
        else:
            issues.append({
                'code': 'DOCTOR_REG_INVALID',
                'severity': 'warning',
                'message': "Doctor registration number not provided"
            })
        
        # 3. Date Consistency Check
        claim_date = claim_data.get('claim_date')
        treatment_date = claim_data.get('treatment_date')
        
        if claim_date and treatment_date:
            c_date = datetime.strptime(claim_date, '%Y-%m-%d')
            t_date = datetime.strptime(treatment_date, '%Y-%m-%d')
            
            if c_date < t_date:
                issues.append({
                    'code': 'DATE_MISMATCH',
                    'severity': 'critical',
                    'message': "Claim date cannot be before treatment date"
                })
                is_valid = False
        
        # 4. Patient Details Match
        patient_name = claim_data.get('patient_name', '')
        if len(patient_name.strip()) < 3:
            issues.append({
                'code': 'PATIENT_MISMATCH',
                'severity': 'warning',
                'message': "Patient name appears incomplete or invalid"
            })
        
        # 5. Completeness Check
        if not claim_data.get('doctor_name'):
            issues.append({
                'code': 'MISSING_DOCUMENTS',
                'severity': 'warning',
                'message': "Doctor name not provided"
            })
        
        if not claim_data.get('hospital_name'):
            issues.append({
                'code': 'MISSING_DOCUMENTS',
                'severity': 'warning',
                'message': "Hospital/clinic name not provided"
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
        """Use LLM to evaluate medical necessity"""
        prompt = self._get_medical_necessity_prompt(claim_data)
        
        messages = [{"role": "user", "content": prompt}]
        
        response = self.client.chat.completions.create(
            model=self.model_deployment,
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        
        assessment_text = response.choices[0].message.content
        
        try:
            if '```json' in assessment_text:
                assessment_text = assessment_text.split('```json')[1].split('```')[0]
            elif '```' in assessment_text:
                assessment_text = assessment_text.split('```')[1].split('```')[0]
            
            return json.loads(assessment_text.strip())
        except json.JSONDecodeError:
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
        """Analyze coverage for each line item with detailed breakdown"""
        item_analysis = []
        total_approved = 0
        total_rejected = 0
        total_copay = 0
        
        for item in items:
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
        covered = False
        for test in covered_tests:
            test_keywords = test.lower().split()
            if any(keyword in description for keyword in test_keywords):
                covered = True
                break
        
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
        """Make final adjudication decision based on all validation steps"""
        
        # Collect all critical issues
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
        
        # Determine if manual review is needed
        requires_manual_review = (
            fraud_detection.get('requires_manual_review', False) or
            confidence_score < confidence_threshold or
            claim_data.get('total_amount', 0) > high_value_threshold
        )
        
        # Priority Rule 1: Safety first - reject suspicious/fraudulent claims
        if fraud_detection.get('fraud_score', 0) > fraud_threshold:
            return self._create_decision_output(
                claim_data, 'MANUAL_REVIEW', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "High fraud risk detected - requires manual review",
                "Claim flagged for fraud investigation. Contact support."
            )
        
        # Priority Rule 2: Policy exclusions override everything
        exclusion_issues = [i for i in all_critical_issues if i['code'] == 'EXCLUDED_CONDITION']
        if exclusion_issues:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Service/condition excluded by policy",
                "This treatment is not covered under your policy. Review your policy document for details."
            )
        
        # Priority Rule 3: Critical eligibility and validation failures
        if not eligibility.get('is_eligible') or not doc_validation.get('is_valid'):
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Failed basic eligibility or document validation",
                "Please address the issues listed and resubmit your claim."
            )
        
        # Priority Rule 4: Hard limits cannot be exceeded
        hard_limit_codes = ['ANNUAL_LIMIT_EXCEEDED', 'PER_CLAIM_EXCEEDED', 'BELOW_MIN_AMOUNT', 'LATE_SUBMISSION']
        hard_limit_issues = [i for i in all_critical_issues if i['code'] in hard_limit_codes]
        if hard_limit_issues:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                hard_limit_issues[0]['message'],
                "This claim cannot be approved due to policy limit constraints."
            )
        
        # Priority Rule 5: Medical necessity is mandatory
        if not medical_necessity.get('is_necessary'):
            necessity_issues = [i for i in all_critical_issues 
                              if i['code'] in ['COSMETIC_PROCEDURE', 'EXPERIMENTAL_TREATMENT', 'NOT_MEDICALLY_NECESSARY']]
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                necessity_issues[0]['message'] if necessity_issues else "Medical necessity not established",
                "This treatment is not covered as it is not medically necessary."
            )
        
        # Priority Rule 6: Coverage issues
        if not coverage_verification.get('coverage_valid'):
            coverage_issues = [i for i in all_critical_issues 
                             if i['code'] in ['SERVICE_NOT_COVERED', 'PRE_AUTH_MISSING']]
            if coverage_issues:
                return self._create_decision_output(
                    claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                    confidence_score, coverage_analysis,
                    coverage_issues[0]['message'],
                    "Service not covered under your policy or pre-authorization missing."
                )
        
        # If we reach here, check coverage analysis for approval
        total_approved = coverage_analysis['total_approved']
        total_rejected = coverage_analysis['total_rejected']
        
        # Check for manual review trigger
        if requires_manual_review:
            return self._create_decision_output(
                claim_data, 'MANUAL_REVIEW', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                f"Claim requires manual review (confidence: {confidence_score:.0%})",
                "Your claim is under review by our team. You will be notified within 3-5 business days."
            )
        
        # Determine final decision
        if total_approved == 0:
            return self._create_decision_output(
                claim_data, 'REJECTED', 0, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "No covered items found in claim",
                "None of the services claimed are covered under your policy."
            )
        elif total_rejected > 0:
            return self._create_decision_output(
                claim_data, 'PARTIAL', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "Some items covered, some not covered or exceed limits",
                f"Approved: ₹{total_approved:.2f}. See breakdown for details on rejected items."
            )
        else:
            return self._create_decision_output(
                claim_data, 'APPROVED', total_approved, all_critical_issues, all_warnings,
                confidence_score, coverage_analysis,
                "All items covered as per policy",
                f"Claim approved. Amount ₹{total_approved:.2f} will be processed for payment."
            )
    
    def _create_decision_output(self, claim_data: Dict, decision: str, 
                               approved_amount: float, critical_issues: List,
                               warnings: List, confidence: float,
                               coverage_analysis: Dict, reason: str, 
                               next_steps: str) -> Dict[str, Any]:
        """Create standardized decision output"""
        
        rejection_reasons = [issue['code'] for issue in critical_issues]
        
        return {
            'claim_id': claim_data.get('claim_id', 'N/A'),
            'patient_name': claim_data.get('patient_name', 'N/A'),
            'employee_id': claim_data.get('employee_id', 'N/A'),
            'decision': decision,
            'reason': reason,
            'approved_amount': round(approved_amount, 2),
            'total_claimed': claim_data.get('total_amount', 0),
            'rejection_reasons': rejection_reasons,
            'confidence_score': round(confidence, 2),
            'deductions': {
                'copay': round(coverage_analysis.get('total_copay', 0), 2),
                'rejected_items': round(coverage_analysis.get('total_rejected', 0), 2)
            },
            'patient_payable': round(coverage_analysis.get('total_rejected', 0) + 
                                    coverage_analysis.get('total_copay', 0), 2),
            'insurance_payable': round(approved_amount, 2),
            'critical_issues': critical_issues,
            'warnings': warnings,
            'item_breakdown': coverage_analysis.get('item_analysis', []),
            'fraud_indicators': self.fraud_indicators,
            'next_steps': next_steps,
            'adjudication_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'policy_id': self.policy.get('policy_id', 'N/A')
        }
    
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
    
    def process_claim_complete(self, file_path: str, claim_date: str = None, 
                      policy_id: str = None, member_id: str = None) -> Dict[str, Any]:
        """
        Complete end-to-end claim processing with database storage.
        """
        try:
            # Step 0: Read and Extract Document
            print("Step 0: Reading document...")
            document_text = self.read_document(file_path)
            claim_data = self.extract_claim_data(document_text, claim_date)
            
            # Generate unique claim ID if not present
            if not claim_data.get('claim_id'):
                claim_data['claim_id'] = f"CLM_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"
            
            # Add file path to claim data
            claim_data['document_path'] = file_path
            
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
            
            # ✅ MAP FIELD NAMES FOR DATABASE
            claim_data_for_db = claim_data.copy()
            claim_data_for_db['total_claimed_amount'] = claim_data.get('total_amount', 0)
            
            # Create initial claim record in database
            print(f"Creating claim record: {claim_data['claim_id']}")
            db_claim_id = self.db.create_claim(claim_data_for_db)
            
            # Log audit entry
            self.db.log_audit(
                claim_id=claim_data['claim_id'],
                action='CREATED',
                details={'file_path': file_path, 'claim_date': claim_date}
            )
            
            # Store document upload record
            file_ext = file_path.split('.')[-1]
            self.db.create_document_upload(
                claim_id=claim_data['claim_id'],
                file_data={
                    'file_name': os.path.basename(file_path),
                    'file_type': file_ext,
                    'file_path': file_path
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
            return final_decision
            
        except Exception as e:
            print(f"✗ Error processing claim: {str(e)}")
            # Log error in audit
            if claim_data.get('claim_id'):
                self.db.log_audit(
                    claim_id=claim_data['claim_id'],
                    action='ERROR',
                    details={'error': str(e)}
                )
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