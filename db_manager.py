"""
Database Manager for Medical Claim Adjudication System
Handles all database operations using Supabase PostgreSQL
"""
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
import json


class DatabaseManager:
    """Manages all database operations for claim adjudication system"""
    
    def __init__(self):
        """Initialize database connection pool"""
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        # Parse connection string and ensure SSL is enabled
        # Add sslmode if not present
        if 'sslmode=' not in self.db_url:
            separator = '&' if '?' in self.db_url else '?'
            self.db_url = f"{self.db_url}{separator}sslmode=require"
        
        try:
            # Create connection pool with SSL
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.db_url,
                connect_timeout=10  # Add timeout
            )
            
            # Test the connection
            conn = self.pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            self.pool.putconn(conn)
            print("✓ Database connection pool initialized successfully")
            
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "Connection refused" in error_msg:
                raise ValueError(
                    "Cannot connect to database. Please check:\n"
                    "1. Your DATABASE_URL format (should not have [] around password)\n"
                    "2. Try using port 6543 (connection pooler) instead of 5432\n"
                    "3. Add ?sslmode=require to the connection string\n"
                    "4. Verify your Supabase project is active\n"
                    f"Original error: {error_msg}"
                )
            raise
    
    def get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()
    
    def release_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True):
        """Execute a query and return results"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)

                # Always commit after any successful execute
                conn.commit()

                if fetch:
                    result = cur.fetchall()
                    return [dict(row) for row in result]

                return None

        except Exception as e:
            conn.rollback()
            raise e

        finally:
            self.release_connection(conn)

    
    # ==================== POLICY OPERATIONS ====================
    
    def get_policy(self, policy_id: str) -> Optional[Dict]:
        """Get policy by ID"""
        query = "SELECT * FROM policies WHERE policy_id = %s"
        result = self.execute_query(query, (policy_id,))
        return result[0] if result else None
    
    
    def create_policy(self, policy_data: Dict) -> str:
        query = """
            INSERT INTO policies (
                policy_id, policy_name, effective_date, policy_config
            ) VALUES (%s, %s, %s, %s)
            RETURNING policy_id
        """
        params = (
            policy_data["policy_id"],
            policy_data["policy_name"],
            policy_data["effective_date"],
            Json(policy_data)
        )
        result = self.execute_query(query, params)
        return result[0]["policy_id"]


    
    # ==================== MEMBER OPERATIONS ====================
    
    def get_member(self, member_id: str) -> Optional[Dict]:
        """Get member by ID"""
        query = "SELECT * FROM covered_members WHERE member_id = %s"
        result = self.execute_query(query, (member_id,))
        return result[0] if result else None
    
    def get_member_by_employee_id(self, employee_id: str) -> Optional[Dict]:
        """Get member by employee ID"""
        query = "SELECT * FROM covered_members WHERE employee_id = %s"
        result = self.execute_query(query, (employee_id,))
        return result[0] if result else None
    
    def create_member(self, member_data: Dict) -> str:
        """Create new covered member"""
        query = """
            INSERT INTO covered_members (
                member_id, policy_id, employee_id, member_name,
                date_of_birth, gender, relationship, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING member_id
        """
        params = (
            member_data['member_id'],
            member_data['policy_id'],
            member_data.get('employee_id'),
            member_data['member_name'],
            member_data.get('date_of_birth'),
            member_data.get('gender'),
            member_data.get('relationship'),
            member_data.get('status', 'active')
        )
        result = self.execute_query(query, params)
        return result[0]['member_id'] if result else None
    
    # ==================== CLAIM OPERATIONS ====================
    
    def create_claim(self, claim_data: Dict) -> str:
        """Create new claim record"""
        
        # ✅ Handle both field name variations
        total_claimed = claim_data.get('total_claimed_amount') or claim_data.get('total_amount', 0)
        
        query = """
            INSERT INTO claims (
                claim_id, policy_id, member_id, patient_name, patient_age,
                patient_gender, patient_dob, employee_id, treatment_date,
                claim_date, document_type, total_claimed_amount, diagnosis,
                diagnosis_code, symptoms, treatment_summary, emergency_treatment,
                follow_up_required, hospital_name, hospital_registration,
                hospital_address, doctor_name, doctor_registration,
                doctor_specialization, pre_authorization_number,
                extracted_data, document_path, decision
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING claim_id
        """
        params = (
            claim_data['claim_id'],
            claim_data.get('policy_id'),
            claim_data.get('member_id'),
            claim_data['patient_name'],
            claim_data.get('patient_age'),
            claim_data.get('patient_gender'),
            claim_data.get('patient_dob'),
            claim_data.get('employee_id'),
            claim_data['treatment_date'],
            claim_data['claim_date'],
            claim_data.get('document_type'),
            total_claimed,  # ✅ Use the mapped value
            claim_data.get('diagnosis'),
            claim_data.get('diagnosis_code'),
            claim_data.get('symptoms'),
            claim_data.get('treatment_summary'),
            claim_data.get('emergency_treatment', False),
            claim_data.get('follow_up_required', False),
            claim_data.get('hospital_name'),
            claim_data.get('hospital_registration'),
            claim_data.get('hospital_address'),
            claim_data.get('doctor_name'),
            claim_data.get('doctor_registration'),
            claim_data.get('doctor_specialization'),
            claim_data.get('pre_authorization_number'),
            Json(claim_data),
            claim_data.get('document_path'),
            'PENDING'
        )
        result = self.execute_query(query, params)
        return result[0]['claim_id'] if result else None
    
    def update_claim_decision(self, claim_id: str, decision_data: Dict):
        """Update claim with adjudication decision"""
        query = """
            UPDATE claims SET
                decision = %s,
                decision_reason = %s,
                approved_amount = %s,
                rejected_amount = %s,
                copay_amount = %s,
                patient_payable = %s,
                insurance_payable = %s,
                confidence_score = %s,
                fraud_score = %s,
                adjudication_date = %s
            WHERE claim_id = %s
        """
        params = (
            decision_data['decision'],
            decision_data['reason'],
            decision_data['approved_amount'],
            decision_data['deductions']['rejected_items'],
            decision_data['deductions']['copay'],
            decision_data['patient_payable'],
            decision_data['insurance_payable'],
            decision_data['confidence_score'],
            decision_data.get('fraud_score', 0),
            datetime.now(),
            claim_id
        )
        self.execute_query(query, params, fetch=False)
    
    def get_claim(self, claim_id: str) -> Optional[Dict]:
        """Get claim by ID with all related data"""
        query = """
            SELECT 
                c.*,
                p.policy_name,
                m.member_name,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id', ci.id,
                            'description', ci.description,
                            'category', ci.category,
                            'claimed_amount', ci.claimed_amount,
                            'approved_amount', ci.approved_amount,
                            'status', ci.status
                        )
                    ),
                    '[]'::json
                ) AS items
            FROM claims c
            LEFT JOIN policies p ON c.policy_id = p.policy_id
            LEFT JOIN covered_members m ON c.member_id = m.member_id
            LEFT JOIN claim_items ci ON c.claim_id = ci.claim_id
            WHERE c.claim_id = %s
            GROUP BY c.id, p.policy_name, m.member_name

        """
        result = self.execute_query(query, (claim_id,))
        return result[0] if result else None
    
    def get_claims_by_policy(self, policy_id: str, limit: int = 100) -> List[Dict]:
        query = """
            SELECT * FROM claim_summary
            WHERE policy_id = %s
            ORDER BY treatment_date DESC
            LIMIT %s
        """
        return self.execute_query(query, (policy_id, limit))
    
    def get_recent_claims(self, days: int = 30, limit: int = 100) -> List[Dict]:
        """Get recent claims"""
        query = """
            SELECT * FROM claim_summary
            WHERE treatment_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            ORDER BY treatment_date DESC
            LIMIT %s
        """
        return self.execute_query(query, (days, limit))

    
    # ==================== CLAIM ITEMS OPERATIONS ====================
    
    def create_claim_items(self, claim_id: str, items: List[Dict]):
        """Create claim items in bulk"""
        query = """
            INSERT INTO claim_items (
                claim_id, description, category, quantity, unit_price,
                claimed_amount, approved_amount, rejected_amount,
                copay_amount, status, coverage_reason, sub_limit_exceeded
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for item in items:
                    params = (
                        claim_id,
                        item['description'],
                        item['category'],
                        item.get('quantity', 1),
                        item.get('unit_price'),
                        item['claimed_amount'],
                        item['approved_amount'],
                        item['rejected_amount'],
                        item['copay_amount'],
                        item['status'],
                        item['reason'],
                        item.get('sub_limit_exceeded', False)
                    )
                    cur.execute(query, params)
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.release_connection(conn)
    
    # ==================== ISSUES OPERATIONS ====================
    
    def create_adjudication_issues(self, claim_id: str, issues: List[Dict]):
        """Create adjudication issues"""
        if not issues:
            return
        
        query = """
            INSERT INTO adjudication_issues (
                claim_id, issue_code, severity, message, step, item_description
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for issue in issues:
                    params = (
                        claim_id,
                        issue['code'],
                        issue['severity'],
                        issue['message'],
                        issue.get('step'),
                        issue.get('item')
                    )
                    cur.execute(query, params)
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.release_connection(conn)
    
    def get_claim_issues(self, claim_id: str) -> List[Dict]:
        """Get all issues for a claim"""
        query = """
            SELECT * FROM adjudication_issues
            WHERE claim_id = %s
            ORDER BY created_at
        """
        return self.execute_query(query, (claim_id,))
    
    # ==================== FRAUD INDICATORS OPERATIONS ====================
    
    def create_fraud_indicators(self, claim_id: str, indicators: List[Dict]):
        """Create fraud indicators"""
        if not indicators:
            return
        
        query = """
            INSERT INTO fraud_indicators (
                claim_id, indicator_type, severity, message, score
            ) VALUES (%s, %s, %s, %s, %s)
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for indicator in indicators:
                    params = (
                        claim_id,
                        indicator['type'],
                        indicator['severity'],
                        indicator['message'],
                        indicator['score']
                    )
                    cur.execute(query, params)
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.release_connection(conn)
    
    # ==================== AUDIT LOG OPERATIONS ====================
    
    def log_audit(self, claim_id: str, action: str, performed_by: str = 'system', details: Dict = None):
        """Create audit log entry"""
        query = """
            INSERT INTO audit_log (claim_id, action, performed_by, details)
            VALUES (%s, %s, %s, %s)
        """
        params = (claim_id, action, performed_by, Json(details or {}))
        self.execute_query(query, params, fetch=False)
    
    def get_claim_audit_log(self, claim_id: str) -> List[Dict]:
        """Get audit log for a claim"""
        query = """
            SELECT * FROM audit_log
            WHERE claim_id = %s
            ORDER BY created_at DESC
        """
        return self.execute_query(query, (claim_id,))
    
    # ==================== DOCUMENT UPLOADS OPERATIONS ====================
    
    def create_document_upload(self, claim_id: str, file_data: Dict) -> str:
        """Record document upload"""
        query = """
            INSERT INTO document_uploads (
                claim_id, file_name, file_type, file_size, file_path, storage_url
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            claim_id,
            file_data['file_name'],
            file_data['file_type'],
            file_data.get('file_size'),
            file_data['file_path'],
            file_data.get('storage_url')
        )
        result = self.execute_query(query, params)
        return str(result[0]['id']) if result else None
    
    # ==================== ANALYTICS & REPORTS ====================
    
    def get_claims_statistics(self, policy_id: str = None, start_date: str = None, end_date: str = None) -> Dict:
        """Get claims statistics"""
        conditions = []
        params = []
        
        if policy_id:
            conditions.append("policy_id = %s")
            params.append(policy_id)
        if start_date:
            conditions.append("treatment_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("treatment_date <= %s")
            params.append(end_date)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT 
                COUNT(*) as total_claims,
                SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) as approved_count,
                SUM(CASE WHEN decision = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count,
                SUM(CASE WHEN decision = 'PARTIAL' THEN 1 ELSE 0 END) as partial_count,
                SUM(CASE WHEN decision = 'MANUAL_REVIEW' THEN 1 ELSE 0 END) as manual_review_count,
                SUM(total_claimed_amount) as total_claimed,
                SUM(approved_amount) as total_approved,
                AVG(confidence_score) as avg_confidence,
                AVG(fraud_score) as avg_fraud_score
            FROM claims
            {where_clause}
        """
        result = self.execute_query(query, tuple(params))
        return result[0] if result else {}
    
    def update_policy_claims_ytd(self, policy_id: str, amount: float):
        """Update policy year-to-date claims amount"""
        query = """
            UPDATE policies 
            SET claims_ytd = COALESCE(claims_ytd, 0) + %s
            WHERE policy_id = %s
        """
        self.execute_query(query, (amount, policy_id), fetch=False)

    def get_policy_by_number(self, policy_number: str) -> Optional[Dict]:
        """Get policy by policy number (for backward compatibility)"""
        # Assuming policy_number might be stored in policy_config JSON
        query = """
            SELECT * FROM policies 
            WHERE policy_id = %s 
            OR policy_config->>'policy_number' = %s
        """
        result = self.execute_query(query, (policy_number, policy_number))
        return result[0] if result else None

    def get_policy_utilization(self, policy_id: str) -> Optional[Dict]:
        """Get policy utilization with category breakdown"""
        query = """
            SELECT 
                policy_id,
                SUM(approved_amount) as total_approved_ytd,
                COUNT(*) as total_claims,
                json_object_agg(
                    category, 
                    category_total
                ) as category_usage
            FROM (
                SELECT 
                    c.policy_id,
                    c.approved_amount,
                    ci.category,
                    SUM(ci.approved_amount) as category_total
                FROM claims c
                LEFT JOIN claim_items ci ON c.claim_id = ci.claim_id
                WHERE c.policy_id = %s
                AND EXTRACT(YEAR FROM c.treatment_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY c.policy_id, c.approved_amount, ci.category
            ) subquery
            GROUP BY policy_id
        """
        result = self.execute_query(query, (policy_id,))
        return result[0] if result else None
    
    def close(self):
        """Close all database connections"""
        self.pool.closeall()