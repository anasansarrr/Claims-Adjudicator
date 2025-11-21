"""
Test script to verify database setup and operations
Run this to test your database connection and operations
"""
import os
from dotenv import load_dotenv
from db_manager import DatabaseManager
from datetime import datetime, timedelta
import json

load_dotenv()

def test_database_connection():
    """Test basic database connection"""
    print("Testing database connection...")
    try:
        db = DatabaseManager()
        print("✓ Database connection successful!")
        return db
    except Exception as e:
        print(f"✗ Database connection failed: {str(e)}")
        return None

def test_policy_operations(db):
    print("\n=== Testing Policy Operations ===")
    
    policy_data = {
        'policy_id': 'TEST_POL_001',
        'policy_name': 'Test Policy',
        'effective_date': '2024-01-01',
        'policy_config': {
            'coverage_details': {
                'consultation_fees': {'covered': True, 'sub_limit': 1000 }
            }
        }
    }
    
    try:
        # Cleanup
        db.execute_query("DELETE FROM policies WHERE policy_id = %s", ('TEST_POL_001',), fetch=False)

        policy_id = db.create_policy(policy_data)
        print(f"✓ Created policy: {policy_id}")

        policy = db.get_policy(policy_id)
        print(f"✓ Retrieved policy: {policy['policy_name']}")

        return True
    except Exception as e:
        print(f"✗ Policy operations failed: {str(e)}")
        return False
    

def test_member_operations(db):
    """Test member CRUD operations"""
    print("\n=== Testing Member Operations ===")
    
    member_data = {
        'member_id': 'TEST_MEM_001',
        'policy_id': 'TEST_POL_001',
        'employee_id': 'TEST_EMP123',
        'member_name': 'Test Member',
        'date_of_birth': '1990-01-01',
        'gender': 'Male',
        'relationship': 'self',
        'status': 'active'
    }
    
    try:
        # Delete if exists
        db.execute_query("DELETE FROM covered_members WHERE member_id = %s", ('TEST_MEM_001',), fetch=False)
        
        member_id = db.create_member(member_data)
        print(f"✓ Created member: {member_id}")
        
        # Retrieve member
        member = db.get_member(member_id)
        print(f"✓ Retrieved member: {member['member_name']}")
        
        # Get by employee ID
        member = db.get_member_by_employee_id('TEST_EMP123')
        print(f"✓ Found member by employee ID: {member['member_id']}")
        
        return True
    except Exception as e:
        print(f"✗ Member operations failed: {str(e)}")
        return False

def test_claim_operations(db):
    """Test claim CRUD operations"""
    print("\n=== Testing Claim Operations ===")
    
    claim_data = {
    'claim_id': 'TEST_CLM_001',
    'policy_id': 'TEST_POL_001',
    'member_id': 'TEST_MEM_001',
    'patient_name': 'Test Member',
    'patient_age': 34,
    'patient_gender': 'Male',
    'employee_id': 'TEST_EMP123',
    'treatment_date': '2024-06-15',
    'claim_date': '2024-06-16',
    'document_type': 'medical_bill',
    'total_claimed_amount': 5000.00,   # FIX
    'diagnosis': 'Common Cold',
    'hospital_name': 'Test Hospital',
    'doctor_name': 'Dr. Test',
    'doctor_registration': 'MH/12345/2020'
}

    
    try:
        # Delete if exists
        db.execute_query("DELETE FROM claims WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        
        claim_id = db.create_claim(claim_data)
        print(f"✓ Created claim: {claim_id}")
        
        # Create claim items
        items = [
            {
                'description': 'Consultation Fee',
                'category': 'consultation',
                'quantity': 1,
                'unit_price': 500,
                'claimed_amount': 500,
                'approved_amount': 450,
                'rejected_amount': 0,
                'copay_amount': 50,
                'status': 'approved',
                'reason': 'Approved with 10% copay'
            }
        ]
        db.create_claim_items(claim_id, items)
        print("✓ Created claim items")
        
        # Update with decision
        decision_data = {
            'decision': 'APPROVED',
            'reason': 'All validations passed',
            'approved_amount': 450.00,
            'deductions': {
                'rejected_items': 0,
                'copay': 50.00
            },
            'patient_payable': 50.00,
            'insurance_payable': 450.00,
            'confidence_score': 0.95,
            'fraud_score': 0.1
        }
        db.update_claim_decision(claim_id, decision_data)
        print("✓ Updated claim decision")
        
        # Retrieve claim
        claim = db.get_claim(claim_id)
        print(f"✓ Retrieved claim: {claim['decision']}")
        
        # Test audit log
        db.log_audit(claim_id, 'TEST_ACTION', 'test_script', {'test': True})
        print("✓ Created audit log entry")
        
        audit_logs = db.get_claim_audit_log(claim_id)
        print(f"✓ Retrieved {len(audit_logs)} audit log entries")
        
        return True
    except Exception as e:
        print(f"✗ Claim operations failed: {str(e)}")
        return False

def test_issues_and_fraud(db):
    """Test issues and fraud indicators"""
    print("\n=== Testing Issues and Fraud Indicators ===")
    
    try:
        # Create test issues
        issues = [
            {
                'code': 'TEST_ISSUE',
                'severity': 'warning',
                'message': 'This is a test issue',
                'step': 'test_step'
            }
        ]
        db.create_adjudication_issues('TEST_CLM_001', issues)
        print("✓ Created adjudication issues")
        
        # Retrieve issues
        claim_issues = db.get_claim_issues('TEST_CLM_001')
        print(f"✓ Retrieved {len(claim_issues)} issues")
        
        # Create fraud indicators
        fraud_indicators = [
            {
                'type': 'TEST_FRAUD',
                'severity': 'medium',
                'message': 'Test fraud indicator',
                'score': 0.3
            }
        ]
        db.create_fraud_indicators('TEST_CLM_001', fraud_indicators)
        print("✓ Created fraud indicators")
        
        return True
    except Exception as e:
        print(f"✗ Issues/Fraud operations failed: {str(e)}")
        return False

def test_analytics(db):
    """Test analytics and reporting functions"""
    print("\n=== Testing Analytics ===")
    
    try:
        
        
        # Get claims statistics
        stats = db.get_claims_statistics(policy_id='TEST_POL_001')
        print(f"✓ Claims statistics: {stats.get('total_claims', 0)} total claims")
        
        # Get recent claims
        recent = db.get_recent_claims(days=30, limit=10)
        print(f"✓ Retrieved {len(recent)} recent claims")
        
        return True
    except Exception as e:
        print(f"✗ Analytics failed: {str(e)}")
        return False

def cleanup_test_data(db):
    """Clean up test data"""
    print("\n=== Cleaning Up Test Data ===")
    
    try:
        # Delete in correct order (respecting foreign keys)
        db.execute_query("DELETE FROM audit_log WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        db.execute_query("DELETE FROM fraud_indicators WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        db.execute_query("DELETE FROM adjudication_issues WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        db.execute_query("DELETE FROM claim_items WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        db.execute_query("DELETE FROM claims WHERE claim_id = %s", ('TEST_CLM_001',), fetch=False)
        db.execute_query("DELETE FROM covered_members WHERE member_id = %s", ('TEST_MEM_001',), fetch=False)
        db.execute_query("DELETE FROM policies WHERE policy_id = %s", ('TEST_POL_001',), fetch=False)
        
        print("✓ Test data cleaned up successfully")
        return True
    except Exception as e:
        print(f"✗ Cleanup failed: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("MEDICAL CLAIM ADJUDICATION - DATABASE TESTING")
    print("="*60)
    
    # Test connection
    db = test_database_connection()
    if not db:
        print("\n✗ Cannot proceed without database connection")
        return
    
    # Run all tests
    tests = [
        ("Policy Operations", lambda: test_policy_operations(db)),
        ("Member Operations", lambda: test_member_operations(db)),
        ("Claim Operations", lambda: test_claim_operations(db)),
        ("Issues & Fraud", lambda: test_issues_and_fraud(db)),
        ("Analytics", lambda: test_analytics(db)),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Cleanup
    cleanup_test_data(db)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)
    
    # Close connection
    db.close()

if __name__ == "__main__":
    main()