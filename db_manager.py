"""
Database Manager for Medical Claim Adjudication System
Uses Supabase REST API - works anywhere, no network issues
"""
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests
import json


class DatabaseManager:
    """Manages all database operations using Supabase REST API"""
    
    def __init__(self):
        """Initialize Supabase REST API client"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set.\n"
                "Get these from your Supabase project settings > API"
            )
        
        # Clean up URL if needed
        self.supabase_url = self.supabase_url.rstrip('/')
        self.api_url = f"{self.supabase_url}/rest/v1"
        
        # Common headers for all requests
        self.headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
        
        # Test connection
        try:
            response = requests.get(
                f"{self.api_url}/policies",
                headers=self.headers,
                params={'limit': 1},
                timeout=10
            )
            response.raise_for_status()
            print("✓ Supabase REST API connection initialized successfully")
        except requests.exceptions.RequestException as e:
            raise ValueError(
                f"Cannot connect to Supabase API. Please check:\n"
                f"1. SUPABASE_URL is correct (should be https://xxx.supabase.co)\n"
                f"2. SUPABASE_KEY is the 'anon' or 'service_role' key\n"
                f"3. Your Supabase project is active\n"
                f"Original error: {e}"
            )
    
    def _get(self, table: str, params: Dict = None) -> List[Dict]:
        """Generic GET request"""
        url = f"{self.api_url}/{table}"
        response = requests.get(url, headers=self.headers, params=params or {})
        response.raise_for_status()
        return response.json()
    
    def _post(self, table: str, data: Dict) -> Dict:
        """Generic POST request"""
        url = f"{self.api_url}/{table}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result
    
    def _patch(self, table: str, data: Dict, filter_params: Dict) -> Dict:
        """Generic PATCH request"""
        url = f"{self.api_url}/{table}"
        params = {f"{k}": f"eq.{v}" for k, v in filter_params.items()}
        response = requests.patch(url, headers=self.headers, json=data, params=params)
        response.raise_for_status()
        result = response.json()
        return result[0] if isinstance(result, list) and result else result
    
    def _delete(self, table: str, filter_params: Dict) -> bool:
        """Generic DELETE request"""
        url = f"{self.api_url}/{table}"
        params = {f"{k}": f"eq.{v}" for k, v in filter_params.items()}
        response = requests.delete(url, headers=self.headers, params=params)
        response.raise_for_status()
        return True
    
    # ==================== POLICY OPERATIONS ====================
    
    def get_policy(self, policy_id: str) -> Optional[Dict]:
        """Get policy by ID"""
        try:
            result = self._get('policies', {'policy_id': f'eq.{policy_id}'})
            return result[0] if result else None
        except:
            return None
    
    def create_policy(self, policy_data: Dict) -> str:
        """Create new policy"""
        data = {
            'policy_id': policy_data['policy_id'],
            'policy_name': policy_data['policy_name'],
            'effective_date': policy_data['effective_date'],
            'policy_config': policy_data
        }
        result = self._post('policies', data)
        return result['policy_id']
    
    # ==================== MEMBER OPERATIONS ====================
    
    def get_member(self, member_id: str) -> Optional[Dict]:
        """Get member by ID"""
        try:
            result = self._get('covered_members', {'member_id': f'eq.{member_id}'})
            return result[0] if result else None
        except:
            return None
    
    def get_member_by_employee_id(self, employee_id: str) -> Optional[Dict]:
        """Get member by employee ID"""
        try:
            result = self._get('covered_members', {'employee_id': f'eq.{employee_id}'})
            return result[0] if result else None
        except:
            return None
    
    def create_member(self, member_data: Dict) -> str:
        """Create new covered member"""
        data = {
            'member_id': member_data['member_id'],
            'policy_id': member_data['policy_id'],
            'employee_id': member_data.get('employee_id'),
            'member_name': member_data['member_name'],
            'date_of_birth': member_data.get('date_of_birth'),
            'gender': member_data.get('gender'),
            'relationship': member_data.get('relationship'),
            'status': member_data.get('status', 'active')
        }
        result = self._post('covered_members', data)
        return result['member_id']
    
    # ==================== CLAIM OPERATIONS ====================
    
    def create_claim(self, claim_data: Dict) -> str:
        """Create new claim record"""
        total_claimed = claim_data.get('total_claimed_amount') or claim_data.get('total_amount', 0)
        
        data = {
            'claim_id': claim_data['claim_id'],
            'policy_id': claim_data.get('policy_id'),
            'member_id': claim_data.get('member_id'),
            'patient_name': claim_data['patient_name'],
            'patient_age': claim_data.get('patient_age'),
            'patient_gender': claim_data.get('patient_gender'),
            'patient_dob': claim_data.get('patient_dob'),
            'employee_id': claim_data.get('employee_id'),
            'treatment_date': claim_data['treatment_date'],
            'claim_date': claim_data['claim_date'],
            'document_type': claim_data.get('document_type'),
            'total_claimed_amount': total_claimed,
            'diagnosis': claim_data.get('diagnosis'),
            'diagnosis_code': claim_data.get('diagnosis_code'),
            'symptoms': claim_data.get('symptoms'),
            'treatment_summary': claim_data.get('treatment_summary'),
            'emergency_treatment': claim_data.get('emergency_treatment', False),
            'follow_up_required': claim_data.get('follow_up_required', False),
            'hospital_name': claim_data.get('hospital_name'),
            'hospital_registration': claim_data.get('hospital_registration'),
            'hospital_address': claim_data.get('hospital_address'),
            'doctor_name': claim_data.get('doctor_name'),
            'doctor_registration': claim_data.get('doctor_registration'),
            'doctor_specialization': claim_data.get('doctor_specialization'),
            'pre_authorization_number': claim_data.get('pre_authorization_number'),
            'extracted_data': claim_data,
            'document_path': claim_data.get('document_path'),
            'decision': 'PENDING'
        }
        
        result = self._post('claims', data)
        return result['claim_id']
    
    def update_claim_decision(self, claim_id: str, decision_data: Dict):
        """Update claim with adjudication decision"""
        data = {
            'decision': decision_data['decision'],
            'decision_reason': decision_data['reason'],
            'approved_amount': decision_data['approved_amount'],
            'rejected_amount': decision_data['deductions']['rejected_items'],
            'copay_amount': decision_data['deductions']['copay'],
            'patient_payable': decision_data['patient_payable'],
            'insurance_payable': decision_data['insurance_payable'],
            'confidence_score': decision_data['confidence_score'],
            'fraud_score': decision_data.get('fraud_score', 0),
            'adjudication_date': datetime.now().isoformat()
        }
        
        self._patch('claims', data, {'claim_id': claim_id})
    
    def get_claim(self, claim_id: str) -> Optional[Dict]:
        """Get claim by ID with related data"""
        try:
            # Get main claim data
            claims = self._get('claims', {'claim_id': f'eq.{claim_id}'})
            if not claims:
                return None
            
            claim = claims[0]
            
            # Get related items
            items = self._get('claim_items', {'claim_id': f'eq.{claim_id}'})
            claim['items'] = items
            
            # Get policy name
            if claim.get('policy_id'):
                policy = self.get_policy(claim['policy_id'])
                if policy:
                    claim['policy_name'] = policy.get('policy_name')
            
            # Get member name
            if claim.get('member_id'):
                member = self.get_member(claim['member_id'])
                if member:
                    claim['member_name'] = member.get('member_name')
            
            return claim
        except:
            return None
    
    def get_claims_by_policy(self, policy_id: str, limit: int = 100) -> List[Dict]:
        """Get claims for a policy"""
        params = {
            'policy_id': f'eq.{policy_id}',
            'order': 'treatment_date.desc',
            'limit': limit
        }
        return self._get('claims', params)
    
    def get_recent_claims(self, days: int = 30, limit: int = 100) -> List[Dict]:
        """Get recent claims"""
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        params = {
            'treatment_date': f'gte.{cutoff_date}',
            'order': 'treatment_date.desc',
            'limit': limit
        }
        return self._get('claims', params)
    
    # ==================== CLAIM ITEMS OPERATIONS ====================
    
    def create_claim_items(self, claim_id: str, items: List[Dict]):
        """Create claim items in bulk"""
        for item in items:
            data = {
                'claim_id': claim_id,
                'description': item['description'],
                'category': item['category'],
                'quantity': item.get('quantity', 1),
                'unit_price': item.get('unit_price'),
                'claimed_amount': item['claimed_amount'],
                'approved_amount': item['approved_amount'],
                'rejected_amount': item['rejected_amount'],
                'copay_amount': item['copay_amount'],
                'status': item['status'],
                'coverage_reason': item['reason'],
                'sub_limit_exceeded': item.get('sub_limit_exceeded', False)
            }
            self._post('claim_items', data)
    
    # ==================== ISSUES OPERATIONS ====================
    
    def create_adjudication_issues(self, claim_id: str, issues: List[Dict]):
        """Create adjudication issues"""
        if not issues:
            return
        
        for issue in issues:
            data = {
                'claim_id': claim_id,
                'issue_code': issue['code'],
                'severity': issue['severity'],
                'message': issue['message'],
                'step': issue.get('step'),
                'item_description': issue.get('item')
            }
            self._post('adjudication_issues', data)
    
    def get_claim_issues(self, claim_id: str) -> List[Dict]:
        """Get all issues for a claim"""
        params = {
            'claim_id': f'eq.{claim_id}',
            'order': 'created_at.asc'
        }
        return self._get('adjudication_issues', params)
    
    # ==================== FRAUD INDICATORS OPERATIONS ====================
    
    def create_fraud_indicators(self, claim_id: str, indicators: List[Dict]):
        """Create fraud indicators"""
        if not indicators:
            return
        
        for indicator in indicators:
            data = {
                'claim_id': claim_id,
                'indicator_type': indicator['type'],
                'severity': indicator['severity'],
                'message': indicator['message'],
                'score': indicator['score']
            }
            self._post('fraud_indicators', data)
    
    # ==================== AUDIT LOG OPERATIONS ====================
    
    def log_audit(self, claim_id: str, action: str, performed_by: str = 'system', details: Dict = None):
        """Create audit log entry"""
        data = {
            'claim_id': claim_id,
            'action': action,
            'performed_by': performed_by,
            'details': details or {}
        }
        self._post('audit_log', data)
    
    def get_claim_audit_log(self, claim_id: str) -> List[Dict]:
        """Get audit log for a claim"""
        params = {
            'claim_id': f'eq.{claim_id}',
            'order': 'created_at.desc'
        }
        return self._get('audit_log', params)
    
    # ==================== DOCUMENT UPLOADS OPERATIONS ====================
    
    def create_document_upload(self, claim_id: str, file_data: Dict) -> str:
        """Record document upload"""
        data = {
            'claim_id': claim_id,
            'file_name': file_data['file_name'],
            'file_type': file_data['file_type'],
            'file_size': file_data.get('file_size'),
            'file_path': file_data['file_path'],
            'storage_url': file_data.get('storage_url'),
            'document_type': file_data.get('document_type', 'general')
        }
        result = self._post('document_uploads', data)
        return str(result['id'])
    
    def get_claim_documents_by_type(self, claim_id: str, doc_type: str = None) -> List[Dict]:
        """Get documents for a claim, optionally filtered by type"""
        params = {'claim_id': f'eq.{claim_id}'}
        
        if doc_type:
            params['document_type'] = f'eq.{doc_type}'
        
        params['order'] = 'uploaded_at.desc'
        return self._get('document_uploads', params)
    
    # ==================== ANALYTICS & REPORTS ====================
    
    def get_claims_statistics(self, policy_id: str = None, start_date: str = None, end_date: str = None) -> Dict:
        """Get claims statistics"""
        # For complex aggregations, use RPC functions or manual calculation
        params = {}
        
        if policy_id:
            params['policy_id'] = f'eq.{policy_id}'
        if start_date:
            params['treatment_date'] = f'gte.{start_date}'
        if end_date:
            if 'treatment_date' in params:
                # Supabase doesn't support multiple filters on same column easily
                # You may need to fetch and filter in Python
                pass
            else:
                params['treatment_date'] = f'lte.{end_date}'
        
        claims = self._get('claims', params)
        
        # Calculate statistics
        stats = {
            'total_claims': len(claims),
            'approved_count': sum(1 for c in claims if c.get('decision') == 'APPROVED'),
            'rejected_count': sum(1 for c in claims if c.get('decision') == 'REJECTED'),
            'partial_count': sum(1 for c in claims if c.get('decision') == 'PARTIAL'),
            'manual_review_count': sum(1 for c in claims if c.get('decision') == 'MANUAL_REVIEW'),
            'total_claimed': sum(c.get('total_claimed_amount', 0) or 0 for c in claims),
            'total_approved': sum(c.get('approved_amount', 0) or 0 for c in claims),
            'avg_confidence': sum(c.get('confidence_score', 0) or 0 for c in claims) / len(claims) if claims else 0,
            'avg_fraud_score': sum(c.get('fraud_score', 0) or 0 for c in claims) / len(claims) if claims else 0
        }
        
        return stats
    
    def update_policy_claims_ytd(self, policy_id: str, amount: float):
        """Update policy year-to-date claims amount"""
        # Get current policy
        policy = self.get_policy(policy_id)
        if not policy:
            return
        
        current_ytd = policy.get('claims_ytd', 0) or 0
        new_ytd = current_ytd + amount
        
        self._patch('policies', {'claims_ytd': new_ytd}, {'policy_id': policy_id})
    
    def get_policy_by_number(self, policy_number: str) -> Optional[Dict]:
        """Get policy by policy number"""
        try:
            # Try direct match
            result = self._get('policies', {'policy_id': f'eq.{policy_number}'})
            if result:
                return result[0]
            
            # Try searching in policy_config JSON
            # This requires using Supabase's JSON operators
            # For now, fetch all and filter
            policies = self._get('policies', {})
            for policy in policies:
                config = policy.get('policy_config', {})
                if isinstance(config, dict) and config.get('policy_number') == policy_number:
                    return policy
            
            return None
        except:
            return None
    
    def get_policy_utilization(self, policy_id: str) -> Optional[Dict]:
        """Get policy utilization with category breakdown"""
        try:
            # Get all claims for this policy in current year
            current_year = datetime.now().year
            params = {
                'policy_id': f'eq.{policy_id}',
                'treatment_date': f'gte.{current_year}-01-01'
            }
            claims = self._get('claims', params)
            
            if not claims:
                return None
            
            # Calculate totals
            total_approved = sum(c.get('approved_amount', 0) or 0 for c in claims)
            total_claims = len(claims)
            
            # Get category usage
            category_usage = {}
            for claim in claims:
                claim_id = claim['claim_id']
                items = self._get('claim_items', {'claim_id': f'eq.{claim_id}'})
                
                for item in items:
                    category = item.get('category', 'unknown')
                    approved = item.get('approved_amount', 0) or 0
                    
                    if category not in category_usage:
                        category_usage[category] = 0
                    category_usage[category] += approved
            
            return {
                'policy_id': policy_id,
                'total_approved_ytd': total_approved,
                'total_claims': total_claims,
                'category_usage': category_usage
            }
        except:
            return None
    
    def close(self):
        """Close connections (no-op for REST API)"""
        pass