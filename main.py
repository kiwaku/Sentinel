#!/usr/bin/env python3
"""
Sentinel - Modular Email Opportunity Extraction and Summarization System

A Python agent that:
1. Regularly scans email inbox via IMAP
2. Extracts and filters relevant opportunities based on personal profile
3. Generates and sends daily email summary reports

Usage:
    python main.py [command] [options]

Commands:
    run         - Run the full extraction and summarization pipeline (default)
    test        - Test system components (email, LLM, etc.)
    summary     - Generate and send summary from existing data
    cleanup     - Clean up old data and logs
    config      - Verify configuration files
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils import ConfigManager, ProfileManager, DatabaseManager, setup_logging
from src.email_ingestion import EmailIngestionService
from src.extraction import LLMExtractionService, FallbackExtractor
from src.filtering import OpportunityFilteringService
from src.storage import StorageService
from src.summarization import EmailSummaryService


class SentinelAgent:
    """Main Sentinel application class."""
    
    def __init__(self):
        """Initialize the Sentinel agent."""
        self.logger = None
        self.config = None
        self.profile = None
        self.db = None
        self.services = {}
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all system components."""
        try:
            # Set up logging first
            self.logger = setup_logging()
            self.logger.info("Starting Sentinel Email Opportunity Extraction System")
            
            # Load configuration and profile
            self.config = ConfigManager()
            self.profile = ProfileManager('config/profile.json')
            
            # Initialize database
            db_path = self.config.get('storage.database_path', 'data/sentinel.db')
            self.db = DatabaseManager(db_path)
            
            # Initialize services
            self.services = {
                'email_ingestion': EmailIngestionService(self.config, self.db),
                'extraction': self._initialize_extraction_service(),
                'filtering': OpportunityFilteringService(self.profile),
                'storage': StorageService(self.db),
                'summarization': EmailSummaryService(self.config)
            }
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize components: {e}")
            else:
                print(f"Failed to initialize components: {e}")
            raise
    
    def _initialize_extraction_service(self):
        """Initialize extraction service with fallback."""
        try:
            # Try to initialize LLM service with semantic filtering
            extraction_service = LLMExtractionService(self.config, self.profile)
            self.logger.info("LLM extraction service initialized with semantic filtering")
            return extraction_service
        except Exception as e:
            self.logger.warning(f"LLM extraction service failed to initialize: {e}")
            self.logger.info("Falling back to rule-based extraction")
            return FallbackExtractor()
    
    def run_full_pipeline(self, days_back: int = None) -> dict:
        """Run the complete email processing pipeline."""
        self.logger.info("Starting full pipeline execution")
        
        results = {
            'emails_fetched': 0,
            'opportunities_extracted': 0,
            'high_priority_count': 0,
            'exploratory_count': 0,
            'summary_sent': False,
            'errors': []
        }
        
        try:
            # Step 1: Fetch new emails
            self.logger.info("Step 1: Fetching new emails")
            emails = self.services['email_ingestion'].fetch_new_emails(days_back)
            results['emails_fetched'] = len(emails)
            
            if not emails:
                self.logger.info("No new emails found")
                return results
            
            # Step 2: Extract opportunities
            self.logger.info(f"Step 2: Extracting opportunities from {len(emails)} emails")
            
            if hasattr(self.services['extraction'], 'extract_opportunities_batch'):
                # LLM-based extraction
                opportunities = self.services['extraction'].extract_opportunities_batch(emails)
            else:
                # Fallback extraction
                opportunities = []
                for email in emails:
                    opp = self.services['extraction'].extract_basic_info(email)
                    if opp:
                        opportunities.append(opp)
            
            results['opportunities_extracted'] = len(opportunities)
            
            if not opportunities:
                self.logger.info("No opportunities extracted from emails")
                # Still mark emails as processed to avoid reprocessing emails with no opportunities
                self.logger.info(f"Marking {len(emails)} emails as processed (no opportunities found)")
                for email in emails:
                    composite_uid = email.composite_uid if hasattr(email, 'composite_uid') else email.uid
                    account_name = email.account_name if hasattr(email, 'account_name') else "Primary Account"
                    self.db.mark_email_processed(
                        composite_uid, 
                        email.subject, 
                        email.sender, 
                        email.date_received,
                        account_name
                    )
                return results
            
            # Step 3: Filter and score opportunities
            self.logger.info(f"Step 3: Filtering and scoring {len(opportunities)} opportunities")
            
            # Apply profile-based filtering
            high_priority, exploratory = self.services['filtering'].filter_and_score_opportunities(opportunities)
            
            # Apply advanced filters
            high_priority = self.services['filtering'].apply_advanced_filters(high_priority)
            exploratory = self.services['filtering'].apply_advanced_filters(exploratory)
            
            # Calculate similarity scores
            all_opportunities = high_priority + exploratory
            all_opportunities = self.services['filtering'].calculate_similarity_scores(all_opportunities)
            
            # Deduplicate
            all_opportunities = self.services['filtering'].deduplicate_opportunities(all_opportunities)
            
            # Re-categorize after deduplication
            high_priority = [opp for opp in all_opportunities if opp.category == 'high_priority']
            exploratory = [opp for opp in all_opportunities if opp.category == 'exploratory']
            
            results['high_priority_count'] = len(high_priority)
            results['exploratory_count'] = len(exploratory)
            
            # Step 4: Store opportunities
            self.logger.info("Step 4: Storing opportunities in database")
            try:
                saved_count = self.services['storage'].save_opportunities(all_opportunities)
                
                # Step 4.5: Mark emails as processed after successful opportunity storage
                # Only mark emails that actually had opportunities successfully saved
                if saved_count > 0:
                    processed_email_uids = set()
                    for opportunity in all_opportunities:
                        processed_email_uids.add(opportunity.uid)
                    
                    self.logger.info(f"Marking {len(processed_email_uids)} emails as successfully processed")
                    for email in emails:
                        composite_uid = email.composite_uid if hasattr(email, 'composite_uid') else email.uid
                        if composite_uid in processed_email_uids:
                            account_name = email.account_name if hasattr(email, 'account_name') else "Primary Account"
                            self.db.mark_email_processed(
                                composite_uid, 
                                email.subject, 
                                email.sender, 
                                email.date_received,
                                account_name
                            )
                else:
                    self.logger.warning("No opportunities were successfully saved to database")
                    
            except Exception as e:
                self.logger.error(f"Failed to save opportunities: {e}")
                results['errors'].append(f"Storage failed: {e}")
                # Don't mark emails as processed if storage failed
                return results
            
            # Step 5: Generate and send summary
            if self.config.get('summary.send_daily_summary', True):
                self.logger.info("Step 5: Generating and sending daily summary")
                
                categorized_opportunities = {
                    'high_priority': high_priority,
                    'exploratory': exploratory
                }
                
                summary_content = self.services['summarization'].generate_daily_summary(categorized_opportunities)
                
                summary_sent = self.services['summarization'].send_summary_email(summary_content)
                results['summary_sent'] = summary_sent
            
            self.logger.info(f"Pipeline completed successfully: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Pipeline execution failed: {e}"
            self.logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def test_system_components(self) -> dict:
        """Test all system components."""
        test_results = {}
        
        self.logger.info("Running system component tests")
        
        # Test email connection
        try:
            email_test = self.services['email_ingestion'].test_connection()
            test_results['email_connection'] = email_test
        except Exception as e:
            test_results['email_connection'] = False
            test_results['email_error'] = str(e)
        
        # Test LLM extraction
        try:
            if hasattr(self.services['extraction'], 'test_extraction'):
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
                
                extraction_test = self.services['extraction'].test_extraction(sample_text)
                test_results['extraction'] = extraction_test.get('is_relevant', False)
                test_results['extraction_details'] = extraction_test
            else:
                test_results['extraction'] = True
                test_results['extraction_details'] = {"note": "Using fallback extractor"}
        except Exception as e:
            test_results['extraction'] = False
            test_results['extraction_error'] = str(e)
        
        # Test email sending
        try:
            email_send_test = self.services['summarization'].test_email_sending()
            test_results['email_sending'] = email_send_test
        except Exception as e:
            test_results['email_sending'] = False
            test_results['email_send_error'] = str(e)
        
        # Test database
        try:
            stats = self.services['storage'].get_processing_statistics(days=7)
            test_results['database'] = True
            test_results['database_stats'] = stats
        except Exception as e:
            test_results['database'] = False
            test_results['database_error'] = str(e)
        
        self.logger.info(f"System test results: {test_results}")
        return test_results
    
    def generate_summary_only(self, days: int = 1) -> bool:
        """Generate and send summary from existing data."""
        try:
            self.logger.info(f"Generating summary from last {days} days of data")
            
            opportunities = self.services['storage'].get_opportunities_for_summary(days)
            
            if not opportunities['high_priority'] and not opportunities['exploratory']:
                self.logger.info("No opportunities found for summary")
                return False
            
            summary_content = self.services['summarization'].generate_daily_summary(opportunities)
            
            return self.services['summarization'].send_summary_email(summary_content)
            
        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            return False
    
    def cleanup_old_data(self) -> bool:
        """Clean up old data."""
        try:
            self.logger.info("Running cleanup...")
            self.services['storage'].cleanup_old_data()
            return True
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return False


def main():
    """Main entry point for the Sentinel application."""
    parser = argparse.ArgumentParser(description="Sentinel - Email Opportunity Extraction")
    
    parser.add_argument(
        'command',
        nargs='?',
        default='run',
        choices=['run', 'test', 'summary', 'cleanup'],
        help='Command to execute (default: run)'
    )
    
    parser.add_argument('--days-back', type=int, help='Days back to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    try:
        agent = SentinelAgent()
        
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Execute requested command
        if args.command == 'run':
            results = agent.run_full_pipeline(days_back=args.days_back)
            print(f"Pipeline Results: {results}")
            
            # Exit with error code if there were issues
            if results['errors']:
                sys.exit(1)
                
        elif args.command == 'test':
            test_results = agent.test_system_components()
            print("System Test Results:")
            for component, result in test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"  {component}: {status}")
            
            # Show details if verbose
            if args.verbose:
                import json
                print(f"\nDetailed Results:\n{json.dumps(test_results, indent=2)}")
            
        elif args.command == 'summary':
            days = args.days_back or 1
            success = agent.generate_summary_only(days)
            print(f"Summary: {'✅ SUCCESS' if success else '❌ FAILED'}")
            
        elif args.command == 'cleanup':
            success = agent.cleanup_old_data()
            print(f"Cleanup: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()