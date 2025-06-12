"""
Sentinel Email Opportunity Extraction System - Core Package

This package contains all the core modules for the Sentinel system:
- email_ingestion: IMAP email fetching and processing
- extraction: LLM-based opportunity extraction using DSPy
- filtering: Profile-based filtering and scoring
- storage: Database and file storage management
- summarization: Email report generation and sending
- utils: Shared utilities and configuration management
"""

__version__ = "1.0.0"
__author__ = "Sentinel Team"
__description__ = "Modular Email Opportunity Extraction and Summarization System"

# Make key classes available at package level
from .utils import EmailOpportunity, ConfigManager, ProfileManager, DatabaseManager
from .email_ingestion import EmailIngestionService, EmailMessage
from .extraction import LLMExtractionService, FallbackExtractor
from .filtering import OpportunityFilteringService
from .storage import StorageService
from .summarization import EmailSummaryService

__all__ = [
    'EmailOpportunity',
    'ConfigManager', 
    'ProfileManager',
    'DatabaseManager',
    'EmailIngestionService',
    'EmailMessage',
    'LLMExtractionService',
    'FallbackExtractor',
    'OpportunityFilteringService',
    'StorageService',
    'EmailSummaryService'
]
