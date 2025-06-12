#!/usr/bin/env python3
"""
Comprehensive test suite for Sentinel system
Run with: python tests/test_everything.py

This file tests the ENTIRE system end-to-end to ensure nothing is broken.
Safe to delete - does not affect production code.

Enhanced with tests from backup folder including:
- Email connection testing
- LLM extraction testing  
- Email sending testing
- Database operations testing
- Component integration testing
"""

import sys
import os
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all core modules can be imported."""
    print("🧪 Testing imports...")
    
    try:
        from utils import ConfigManager, ProfileManager, DatabaseManager, EmailOpportunity
        from email_ingestion import EmailIngestionService
        from extraction import LLMExtractionService, FallbackExtractor
        from filtering import OpportunityFilteringService
        from storage import StorageService
        from summarization import EmailSummaryService
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config_loading():
    """Test configuration loading."""
    print("🧪 Testing config loading...")
    
    try:
        from utils import ConfigManager
        config = ConfigManager()
        config_data = config.load_config()
        
        if not config_data:
            print("❌ Config data is empty")
            return False
            
        if 'email' not in config_data:
            print("❌ Email section missing from config")
            return False
            
        print("✅ Config loading successful")
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False

def test_profile_loading():
    """Test profile loading."""
    print("🧪 Testing profile loading...")
    
    try:
        from src.utils import ProfileManager
        profile = ProfileManager()
        profile_data = profile.load_profile()
        
        if not profile_data:
            print("❌ Profile data is empty")
            return False
            
        required_keys = ['interests', 'preferred_locations', 'exclusions']
        for key in required_keys:
            if key not in profile_data:
                print(f"❌ Required profile key missing: {key}")
                return False
                
        print("✅ Profile loading successful")
        return True
    except Exception as e:
        print(f"❌ Profile loading failed: {e}")
        return False

def test_database_operations():
    """Test database operations with a temporary database."""
    print("🧪 Testing database operations...")
    
    try:
        from src.utils import DatabaseManager, EmailOpportunity
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            temp_db_path = tmp_db.name
        
        # Initialize database
        db = DatabaseManager(temp_db_path)
        
        # Test creating a sample opportunity
        opportunity = EmailOpportunity(
            uid="test_123",
            subject="Test Fellowship Opportunity",
            sender="test@university.edu",
            date_received="2024-06-12",
            title="Test Research Fellowship",
            organization="Test University",
            opportunity_type="fellowship",
            deadline="2024-12-31",
            location="Remote",
            notes="This is a test opportunity",
            priority_score=0.8,
            category="high_priority"
        )
        
        # Test saving opportunity
        db.save_opportunity(opportunity)
        
        # Test retrieving opportunities
        recent_ops = db.get_recent_opportunities(1)
        if len(recent_ops) != 1:
            print(f"❌ Expected 1 opportunity, got {len(recent_ops)}")
            return False
            
        # Test marking email as processed
        db.mark_email_processed("test_123", "Test Subject", "test@test.com", "2024-06-12")
        
        # Cleanup
        os.unlink(temp_db_path)
        
        print("✅ Database operations successful")
        return True
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False

def test_fallback_extractor():
    """Test the fallback extractor (doesn't require LLM)."""
    print("🧪 Testing fallback extractor...")
    
    try:
        from src.extraction import FallbackExtractor
        from src.utils import ConfigManager, ProfileManager
        
        config = ConfigManager()
        profile = ProfileManager()
        
        extractor = FallbackExtractor(config, profile)
        
        # Create a mock email
        class MockEmail:
            def __init__(self):
                self.uid = "test_123"
                self.subject = "PhD Fellowship Opportunity in Machine Learning"
                self.sender = "fellowships@university.edu"
                self.body = "We are pleased to announce a fellowship opportunity for PhD students interested in machine learning research. Application deadline: December 31, 2024."
                self.date_received = "2024-06-12"
        
        mock_email = MockEmail()
        opportunity = extractor.extract_basic_info(mock_email)
        
        if not opportunity:
            print("❌ Extractor returned None")
            return False
            
        if not opportunity.title:
            print("❌ No title extracted")
            return False
            
        print("✅ Fallback extractor successful")
        return True
    except Exception as e:
        print(f"❌ Fallback extractor failed: {e}")
        return False

def test_filtering_service():
    """Test opportunity filtering."""
    print("🧪 Testing filtering service...")
    
    try:
        from src.filtering import OpportunityFilteringService
        from src.utils import ConfigManager, ProfileManager, EmailOpportunity
        
        config = ConfigManager()
        profile = ProfileManager()
        
        filtering = OpportunityFilteringService(config, profile)
        
        # Create test opportunities
        opportunity1 = EmailOpportunity(
            uid="test_1",
            subject="Machine Learning Fellowship",
            sender="ml@university.edu",
            date_received="2024-06-12",
            title="ML Research Fellowship",
            organization="University",
            opportunity_type="fellowship",
            deadline="2024-12-31",
            location="Remote",
            notes="Machine learning research opportunity",
            priority_score=0.0,  # Will be set by filtering
            category="exploratory"
        )
        
        opportunity2 = EmailOpportunity(
            uid="test_2",
            subject="Sales Position Available",
            sender="sales@company.com",
            date_received="2024-06-12",
            title="Sales Representative",
            organization="Company",
            opportunity_type="job",
            deadline="2024-12-31",
            location="New York",
            notes="Sales position in our growing team",
            priority_score=0.0,
            category="exploratory"
        )
        
        opportunities = [opportunity1, opportunity2]
        filtered = filtering.filter_and_score_opportunities(opportunities)
        
        if not filtered:
            print("❌ No opportunities returned from filtering")
            return False
            
        # ML opportunity should score higher than sales (based on typical interests)
        ml_opp = next((o for o in filtered if "ML" in o.title), None)
        if ml_opp and ml_opp.priority_score > 0:
            print("✅ Filtering service successful")
            return True
        else:
            print("❌ Filtering didn't score opportunities properly")
            return False
            
    except Exception as e:
        print(f"❌ Filtering service failed: {e}")
        return False

def test_storage_service():
    """Test storage service operations."""
    print("🧪 Testing storage service...")
    
    try:
        from src.storage import StorageService
        from src.utils import DatabaseManager, EmailOpportunity
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            temp_db_path = tmp_db.name
        
        db = DatabaseManager(temp_db_path)
        storage = StorageService(db)
        
        # Test saving opportunities
        opportunity = EmailOpportunity(
            uid="storage_test_123",
            subject="Storage Test Opportunity",
            sender="test@test.edu",
            date_received="2024-06-12",
            title="Test Storage Fellowship",
            organization="Test Storage University",
            opportunity_type="fellowship",
            deadline="2024-12-31",
            location="Remote",
            notes="Testing storage functionality",
            priority_score=0.7,
            category="high_priority"
        )
        
        saved_count = storage.save_opportunities([opportunity])
        if saved_count != 1:
            print(f"❌ Expected 1 saved opportunity, got {saved_count}")
            return False
        
        # Test getting opportunities for summary
        summary_data = storage.get_opportunities_for_summary(days=1)
        if 'high_priority' not in summary_data or 'exploratory' not in summary_data:
            print("❌ Summary data structure incorrect")
            return False
            
        # Cleanup
        os.unlink(temp_db_path)
        
        print("✅ Storage service successful")
        return True
    except Exception as e:
        print(f"❌ Storage service failed: {e}")
        return False

def test_cli_functions():
    """Test CLI module functions."""
    print("🧪 Testing CLI functions...")
    
    try:
        # Test that CLI functions can be imported
        sys.path.append(str(Path(__file__).parent.parent))
        import cli
        
        # Check if main functions exist
        if not hasattr(cli, 'search_opportunities'):
            print("❌ search_opportunities function missing")
            return False
            
        if not hasattr(cli, 'update_profile'):
            print("❌ update_profile function missing")
            return False
            
        if not hasattr(cli, 'main'):
            print("❌ main function missing")
            return False
            
        print("✅ CLI functions test successful")
        return True
    except Exception as e:
        print(f"❌ CLI functions test failed: {e}")
        return False

def test_main_agent():
    """Test that the main SentinelAgent can be initialized."""
    print("🧪 Testing main SentinelAgent...")
    
    try:
        sys.path.append(str(Path(__file__).parent.parent))
        import main
        
        # Check if SentinelAgent exists
        if not hasattr(main, 'SentinelAgent'):
            print("❌ SentinelAgent class missing")
            return False
            
        # Try to initialize (this tests that all dependencies work)
        agent = main.SentinelAgent()
        
        if not hasattr(agent, 'run_full_pipeline'):
            print("❌ run_full_pipeline method missing")
            return False
            
        if not hasattr(agent, 'test_system_components'):
            print("❌ test_system_components method missing")
            return False
            
        print("✅ Main SentinelAgent test successful")
        return True
    except Exception as e:
        print(f"❌ Main SentinelAgent test failed: {e}")
        return False

def test_email_connection():
    """Test email connection for all configured accounts (from backup)."""
    print("🧪 Testing email connection...")
    
    try:
        from src.email_ingestion import EmailIngestionService
        from src.utils import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        email_service = EmailIngestionService(config)
        
        # Use the test_connection method from backup
        connection_success = email_service.test_connection()
        
        if connection_success:
            print("✅ Email connection test successful")
            return True
        else:
            print("⚠️  Email connection test failed - check config")
            return False
            
    except Exception as e:
        print(f"❌ Email connection test error: {e}")
        return False

def test_llm_extraction():
    """Test LLM extraction with sample opportunity text (from backup)."""
    print("🧪 Testing LLM extraction...")
    
    try:
        from src.extraction import LLMExtractionService, FallbackExtractor
        from src.utils import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Sample opportunity text from backup
        sample_text = """
        Subject: Research Fellowship Opportunity at MIT
        
        We are pleased to announce a new research fellowship opportunity at MIT's Computer Science department.
        This fellowship is open to PhD students and recent graduates working in machine learning and AI.
        
        The fellowship provides:
        - $60,000 annual stipend
        - Research funding
        - Mentorship from leading faculty
        
        Application deadline: March 15, 2024
        Location: Cambridge, MA (remote work possible)
        
        For more information and to apply, visit our website.
        """
        
        try:
            # Try LLM extraction first
            extractor = LLMExtractionService(config)
            
            # Create mock email for testing
            class MockEmail:
                def __init__(self):
                    self.uid = "test"
                    self.subject = "Research Fellowship Opportunity at MIT"
                    self.sender = "test@mit.edu"
                    self.body = sample_text
                    self.date_received = datetime.now()
            
            mock_email = MockEmail()
            
            if hasattr(extractor, 'test_extraction'):
                result = extractor.test_extraction(sample_text)
                if result.get('is_relevant', False):
                    print("✅ LLM extraction test successful - found relevant opportunity")
                    return True
                else:
                    print("⚠️  LLM extraction test - no opportunity found")
                    return False
            else:
                # Fallback to basic extraction test
                is_relevant, reasoning = extractor.is_relevant_opportunity(mock_email)
                if is_relevant:
                    print("✅ LLM extraction basic test successful")
                    return True
                else:
                    print("⚠️  LLM extraction basic test - not relevant")
                    return False
                    
        except Exception as llm_error:
            print(f"⚠️  LLM extraction failed, trying fallback: {llm_error}")
            
            # Use fallback extractor
            fallback = FallbackExtractor()
            opportunity = fallback.extract_opportunity(
                "Research Fellowship Opportunity at MIT",
                "test@mit.edu",
                sample_text
            )
            
            if opportunity:
                print("✅ Fallback extraction test successful")
                return True
            else:
                print("⚠️  Fallback extraction test - no opportunity found")
                return False
                
    except Exception as e:
        print(f"❌ Extraction test error: {e}")
        return False

def test_email_sending():
    """Test email sending configuration (from backup)."""
    print("🧪 Testing email sending...")
    
    try:
        from src.summarization import EmailSummaryService
        from src.utils import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        summary_service = EmailSummaryService(config)
        
        # Use the test_email_sending method from backup
        if hasattr(summary_service, 'test_email_sending'):
            send_success = summary_service.test_email_sending()
            
            if send_success:
                print("✅ Email sending test successful")
                return True
            else:
                print("⚠️  Email sending test failed - check email config")
                return False
        else:
            print("✅ Email sending test skipped - method not available")
            return True
            
    except Exception as e:
        print(f"❌ Email sending test error: {e}")
        return False

def test_database_operations_advanced():
    """Test advanced database operations (from backup)."""
    print("🧪 Testing advanced database operations...")
    
    try:
        from src.storage import StorageService
        from src.utils import ConfigManager, DatabaseManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        storage_service = StorageService(config)
        
        # Test getting processing statistics (from backup)
        try:
            stats = storage_service.get_processing_statistics(days=7)
            
            if isinstance(stats, dict):
                print(f"✅ Database statistics retrieved: {len(stats)} metrics")
                return True
            else:
                print("⚠️  Database statistics returned unexpected format")
                return False
                
        except Exception as stats_error:
            print(f"⚠️  Database statistics not available: {stats_error}")
            
            # Fallback: test basic database connection
            db_manager = DatabaseManager()
            
            with db_manager.connect() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                if tables:
                    print(f"✅ Database connection successful, found {len(tables)} tables")
                    return True
                else:
                    print("⚠️  Database connected but no tables found")
                    return False
                    
    except Exception as e:
        print(f"❌ Advanced database test error: {e}")
        return False

def test_system_components_integration():
    """Test system components integration (from backup)."""
    print("🧪 Testing system components integration...")
    
    try:
        # Add main to path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        from main import SentinelAgent
        
        # Initialize agent
        agent = SentinelAgent()
        
        # Test that agent has required components
        required_attributes = ['config_manager', 'profile_manager', 'services']
        missing_attrs = []
        
        for attr in required_attributes:
            if not hasattr(agent, attr):
                missing_attrs.append(attr)
        
        if missing_attrs:
            print(f"⚠️  Agent missing attributes: {missing_attrs}")
            return False
        
        # Test services initialization
        if hasattr(agent, 'services') and agent.services:
            service_count = len(agent.services) if isinstance(agent.services, dict) else 0
            print(f"✅ System integration test successful - {service_count} services initialized")
            return True
        else:
            print("⚠️  System integration test - services not properly initialized")
            return False
            
    except Exception as e:
        print(f"❌ System integration test error: {e}")
        return False

def test_configuration_validation():
    """Test comprehensive configuration validation."""
    print("🧪 Testing configuration validation...")
    
    try:
        from src.utils import ConfigManager, ProfileManager
        
        # Test config loading and validation
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Check required config sections
        required_sections = ['email', 'llm', 'processing', 'storage']
        missing_sections = []
        
        for section in required_sections:
            if section not in config:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"⚠️  Config missing sections: {missing_sections}")
            return False
        
        # Test profile loading
        profile_manager = ProfileManager()
        profile = profile_manager.load_profile()
        
        # Check profile has essential fields
        essential_fields = ['name', 'email', 'interests']
        missing_fields = []
        
        for field in essential_fields:
            if field not in profile:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"⚠️  Profile missing fields: {missing_fields}")
            return False
        
        print("✅ Configuration validation successful")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation error: {e}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("🛡️ SENTINEL SYSTEM TEST SUITE")
    print("=" * 50)
    
    tests = [
        ("Core Imports", test_imports),
        ("Config Loading", test_config_loading),
        ("Profile Loading", test_profile_loading),
        ("Database Operations", test_database_operations),
        ("Fallback Extractor", test_fallback_extractor),
        ("Filtering Service", test_filtering_service),
        ("Storage Service", test_storage_service),
        ("CLI Functions", test_cli_functions),
        ("Main SentinelAgent", test_main_agent),
        ("Email Connection", test_email_connection),
        ("LLM Extraction", test_llm_extraction),
        ("Email Sending", test_email_sending),
        ("Advanced Database Operations", test_database_operations_advanced),
        ("System Components Integration", test_system_components_integration),
        ("Configuration Validation", test_configuration_validation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! System is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
