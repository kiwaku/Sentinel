"""
Utility functions for the Sentinel email opportunity extraction system.
"""

import json
import logging
import os
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class EmailOpportunity(BaseModel):
    """Structured representation of an extracted email opportunity."""
    
    uid: str = Field(description="Email UID")
    title: str = Field(description="Opportunity title")
    organization: str = Field(description="Organization name")
    opportunity_type: str = Field(description="Type of opportunity")
    eligibility: str = Field(description="Eligibility requirements")
    location: str = Field(description="Location or remote")
    deadlines: str = Field(description="Application deadlines")
    notes: str = Field(description="Additional notes")
    email_date: datetime = Field(description="Email received date")
    processed_date: datetime = Field(default_factory=datetime.now)
    priority_score: float = Field(default=0.0, description="Calculated priority score")
    category: str = Field(default="exploratory", description="high_priority or exploratory")
    
    # New URL and metadata fields
    original_urls: List[str] = Field(default=[], description="URLs found in original email")
    primary_url: Optional[str] = Field(default=None, description="Most relevant opportunity URL")
    urls_with_context: List[dict] = Field(default=[], description="URLs with anchor text and context")
    mailto_addresses: List[dict] = Field(default=[], description="Contact emails with context")
    calendar_links: List[dict] = Field(default=[], description="Calendar/event links")
    attachment_info: List[dict] = Field(default=[], description="Attachment metadata")
    email_headers: dict = Field(default={}, description="Original email headers")
    deadlines_from_links: List[str] = Field(default=[], description="Deadlines extracted from link context")
    account_name: str = Field(default="Primary Account", description="Email account source")


class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._config = None
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file and override with environment variables."""
        if self._config is None:
            try:
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
                
                # Override with environment variables
                self._apply_env_overrides()
                
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}. "
                    "Please copy config.example.json to config.json and customize it."
                )
        return self._config
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        # Process multi-account email configuration from env variables
        email_accounts = self._get_email_accounts_from_env()
        if email_accounts:
            self._config['email_accounts'] = email_accounts
        
        # Single email configuration (legacy support)
        if os.getenv('EMAIL_USERNAME'):
            if 'email' not in self._config:
                self._config['email'] = {}
            self._config['email']['username'] = os.getenv('EMAIL_USERNAME')
        
        if os.getenv('EMAIL_PASSWORD'):
            if 'email' not in self._config:
                self._config['email'] = {}
            self._config['email']['password'] = os.getenv('EMAIL_PASSWORD')
        
        if os.getenv('EMAIL_IMAP_SERVER'):
            if 'email' not in self._config:
                self._config['email'] = {}
            self._config['email']['imap_server'] = os.getenv('EMAIL_IMAP_SERVER')
        
        if os.getenv('EMAIL_SMTP_SERVER'):
            if 'email' not in self._config:
                self._config['email'] = {}
            self._config['email']['smtp_server'] = os.getenv('EMAIL_SMTP_SERVER')
        
        # LLM Configuration
        if os.getenv('LLM_API_KEY'):
            if 'llm' not in self._config:
                self._config['llm'] = {}
            self._config['llm']['api_key'] = os.getenv('LLM_API_KEY')
        
        # Support both new and old env var names for backwards compatibility
        if os.getenv('TOGETHER_AI_API_KEY'):
            if 'llm' not in self._config:
                self._config['llm'] = {}
            self._config['llm']['api_key'] = os.getenv('TOGETHER_AI_API_KEY')
        
        if os.getenv('LLM_MODEL'):
            if 'llm' not in self._config:
                self._config['llm'] = {}
            self._config['llm']['model'] = os.getenv('LLM_MODEL')
        
        if os.getenv('LLM_TEMPERATURE'):
            if 'llm' not in self._config:
                self._config['llm'] = {}
            self._config['llm']['temperature'] = float(os.getenv('LLM_TEMPERATURE'))
        
        # Summary Configuration
        if os.getenv('SUMMARY_RECIPIENT_EMAIL'):
            if 'summary' not in self._config:
                self._config['summary'] = {}
            self._config['summary']['recipient_email'] = os.getenv('SUMMARY_RECIPIENT_EMAIL')
        
        # Storage Configuration
        if os.getenv('DATABASE_PATH'):
            if 'storage' not in self._config:
                self._config['storage'] = {}
            self._config['storage']['database_path'] = os.getenv('DATABASE_PATH')
        
        if os.getenv('LOGS_DIRECTORY'):
            if 'storage' not in self._config:
                self._config['storage'] = {}
            self._config['storage']['logs_directory'] = os.getenv('LOGS_DIRECTORY')
        
        # Legacy support for old env var names
        if os.getenv('SENDER_EMAIL'):
            if 'email' not in self._config:
                self._config['email'] = {}
            self._config['email']['username'] = os.getenv('SENDER_EMAIL')
    
    def _get_email_accounts_from_env(self) -> List[Dict[str, Any]]:
        """Extract multiple email account configurations from environment variables."""
        accounts = []
        pattern = r'^SOURCE_EMAIL_(\d+)_(\w+)$'
        logger = logging.getLogger(__name__)
        
        # Collect environment variables related to email accounts
        email_env_vars = {}
        for key in os.environ:
            match = re.match(pattern, key)
            if match:
                account_num = int(match.group(1))
                param_name = match.group(2).lower()
                
                if account_num not in email_env_vars:
                    email_env_vars[account_num] = {}
                
                email_env_vars[account_num][param_name] = os.environ[key]
        
        # Process each account
        for account_num, params in email_env_vars.items():
            try:
                # Required parameters
                if not params.get("username"):
                    logger.warning(f"Skipping email account {account_num}: Missing USERNAME parameter")
                    continue
                
                if not params.get("password"):
                    logger.warning(f"Skipping email account {account_num}: Missing PASSWORD parameter")
                    continue
                
                # Build the account configuration
                account_config = {
                    "account_name": params.get("name", f"Account {account_num}"),
                    "username": params.get("username"),
                    "password": params.get("password"),
                    "imap_server": params.get("imap_server", os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")),
                    "smtp_server": params.get("smtp_server", os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")),
                    "use_oauth": params.get("use_oauth", "false").lower() == "true"
                }
                
                # Handle numeric parameters with proper error checking
                try:
                    account_config["imap_port"] = int(params.get("imap_port", os.getenv("EMAIL_IMAP_PORT", "993")))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid IMAP_PORT for account {account_num}, using default 993")
                    account_config["imap_port"] = 993
                
                try:
                    account_config["smtp_port"] = int(params.get("smtp_port", os.getenv("EMAIL_SMTP_PORT", "587")))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid SMTP_PORT for account {account_num}, using default 587")
                    account_config["smtp_port"] = 587
                
                # Add the account to our list
                logger.debug(f"Added email account from environment: {account_config['account_name']} ({account_config['username']})")
                accounts.append(account_config)
                
            except Exception as e:
                logger.error(f"Error processing email account {account_num} from environment: {e}")
        
        if accounts:
            logger.info(f"Loaded {len(accounts)} email accounts from environment variables")
        
        return accounts
    
    def get(self, key_path: str, default=None) -> Any:
        """Get nested configuration value using dot notation."""
        config = self.load_config()
        keys = key_path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class ProfileManager:
    """Manages user profile loading and filtering logic."""
    
    def __init__(self, profile_path: str = "config/profile.json"):
        self.profile_path = profile_path
        self.logger = logging.getLogger(__name__)
        self._profile = None
    
    def load_profile(self) -> Dict[str, Any]:
        """Load user profile from JSON file."""
        if self._profile is None:
            try:
                with open(self.profile_path, 'r') as f:
                    self._profile = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Profile file not found: {self.profile_path}. "
                    "Please copy profile.example.json to profile.json and customize it."
                )
        return self._profile
    
    def calculate_priority_score(self, opportunity: EmailOpportunity) -> float:
        """Calculate priority score based on profile preferences with enhanced discovery scoring."""
        profile = self.load_profile()
        weights = profile.get('scoring_weights', {})
        
        score = 0.0
        
        # Use LLM-based vibe scoring for interest matching (fallback to keywords if needed)
        vibe_interest_score = self.calculate_interest_vibes_score(opportunity)
        
        # Traditional keyword-based scoring as backup
        interests = [i.lower() for i in profile.get('interests', [])]
        opportunity_text = f"{opportunity.title} {opportunity.notes}".lower()
        
        # Direct matches (full weight)
        direct_matches = sum(1 for interest in interests if interest in opportunity_text)
        
        # Enhanced partial matches with broader technical/AI recognition
        partial_matches = 0
        
        # AI/ML domain terms (broader recognition)
        ai_terms = [
            'ai', 'artificial', 'intelligence', 'ml', 'deep learning', 'neural', 'algorithm',
            'llm', 'gpt', 'chatgpt', 'openai', 'claude', 'anthropic', 'transformer', 'bert',
            'diffusion', 'generative', 'nlp', 'computer vision', 'reinforcement learning',
            'foundation model', 'large language model', 'prompt engineering', 'fine-tuning'
        ]
        
        # Technical/Engineering terms (broader recognition)
        tech_terms = [
            'tech', 'engineering', 'development', 'programming', 'coding', 'software',
            'frontend', 'backend', 'fullstack', 'web dev', 'mobile dev', 'devops',
            'cloud', 'aws', 'azure', 'kubernetes', 'docker', 'api', 'database',
            'python', 'javascript', 'react', 'nodejs', 'typescript', 'css', 'html',
            'framework', 'library', 'open source', 'github', 'architecture'
        ]
        
        # Research/Academic terms
        research_terms = [
            'study', 'academic', 'university', 'phd', 'graduate', 'scholar', 'paper',
            'publication', 'journal', 'conference', 'workshop', 'symposium', 'research',
            'experiment', 'analysis', 'methodology', 'findings', 'peer review'
        ]
        
        # Industry/Business terms for market intelligence
        industry_terms = [
            'startup', 'funding', 'venture', 'series a', 'ipo', 'acquisition', 'merger',
            'product launch', 'announcement', 'release', 'update', 'platform', 'service',
            'industry', 'market', 'trend', 'innovation', 'breakthrough', 'investment'
        ]
        
        # Design/Creative tech terms
        design_terms = [
            'design', 'ui', 'ux', 'interface', 'user experience', 'creative', 'visual',
            'graphic', 'web design', 'product design', 'prototyping', 'figma', 'sketch'
        ]
        
        # Apply enhanced semantic matching
        if any(term in interests for term in ['artificial intelligence', 'machine learning']):
            partial_matches += sum(1 for term in ai_terms if term in opportunity_text)
        
        if 'research' in interests:
            partial_matches += sum(1 for term in research_terms if term in opportunity_text)
            
        if any(term in interests for term in ['software engineering', 'data science']):
            partial_matches += sum(1 for term in tech_terms if term in opportunity_text)
            partial_matches += sum(1 for term in design_terms if term in opportunity_text)
        
        # Add industry intelligence bonus for market awareness
        if any(term in interests for term in ['conferences', 'workshops']):
            partial_matches += sum(1 for term in industry_terms if term in opportunity_text) * 0.5
        
        # Special boost for content types that are inherently valuable
        content_type_boost = 0
        if opportunity.opportunity_type in ['interesting_content', 'industry_update', 'news_with_opportunities']:
            # Check if it's technically relevant even without keyword matches
            tech_relevance = sum(1 for term in ai_terms + tech_terms + design_terms if term in opportunity_text)
            if tech_relevance > 0:
                content_type_boost = min(tech_relevance * 0.3, 1.0)  # Up to 1.0 boost for highly technical content
        
        # Combine vibe-based and keyword-based interest scoring
        base_interest_score = (direct_matches + partial_matches * 0.5) / len(interests) if interests else 0
        
        # Weight the vibe score more heavily as it's more sophisticated
        combined_interest_score = (vibe_interest_score * 0.7) + (base_interest_score * 0.3)
        interest_score = min(combined_interest_score + content_type_boost, 1.0)
        
        score += interest_score * weights.get('interest_match', 0.4)
        
        # Opportunity type score (enhanced with fuzzy matching and content type recognition)
        preferred_types = [t.lower() for t in profile.get('preferred_opportunities', [])]
        type_score = 0.0
        
        # Direct type matches
        if any(ptype in opportunity.opportunity_type.lower() for ptype in preferred_types):
            type_score = 1.0
        else:
            # Enhanced fuzzy type matching
            opp_type_lower = opportunity.opportunity_type.lower()
            
            # Traditional opportunity type matching
            if 'fellowship' in preferred_types and any(term in opp_type_lower for term in ['program', 'scholarship', 'award']):
                type_score = 0.7
            elif 'research position' in preferred_types and any(term in opp_type_lower for term in ['academic', 'university', 'lab']):
                type_score = 0.7
            elif 'conference' in preferred_types and any(term in opp_type_lower for term in ['workshop', 'seminar', 'symposium', 'event', 'webinar']):
                type_score = 0.8
            elif 'job opening' in preferred_types and any(term in opp_type_lower for term in ['position', 'role', 'career', 'job']):
                type_score = 0.6
            
            # Enhanced content type recognition for modern discovery
            elif any(ptype in preferred_types for ptype in ['conference', 'workshop']) and \
                 opp_type_lower in ['interesting_content', 'industry_update', 'news_with_opportunities']:
                # Check if it's about conferences, workshops, or technical content
                content_text = f"{opportunity.title} {opportunity.notes}".lower()
                if any(term in content_text for term in [
                    'conference', 'workshop', 'event', 'summit', 'symposium', 'meetup',
                    'wwdc', 'google i/o', 'tech talk', 'keynote', 'presentation'
                ]):
                    type_score = 0.7
                # Technical/AI content that's inherently valuable for staying current
                elif any(term in content_text for term in [
                    'release', 'launch', 'update', 'announcement', 'breakthrough',
                    'openai', 'google', 'microsoft', 'apple', 'meta', 'anthropic',
                    'css', 'javascript', 'react', 'python', 'ai model', 'llm'
                ]):
                    type_score = 0.6
            
            # Course and learning content matching
            elif 'workshop' in preferred_types and opp_type_lower in ['course', 'professional certificate', 'specialization']:
                type_score = 0.6
            
            # Competition and challenge matching
            elif any(ptype in preferred_types for ptype in ['internship', 'job opening']) and \
                 opp_type_lower in ['competition', 'challenge']:
                type_score = 0.5
        
        score += type_score * weights.get('opportunity_type', 0.3)
        
        # Location score (more generous for online/remote opportunities)
        preferred_locations = [l.lower() for l in profile.get('preferred_locations', [])]
        location_score = 0.5  # Base score
        
        if any(loc in opportunity.location.lower() for loc in preferred_locations):
            location_score = 1.0
        elif any(term in opportunity.location.lower() for term in ['online', 'virtual', 'remote']) and \
             any(term in preferred_locations for term in ['remote', 'online', 'virtual']):
            location_score = 1.0
        elif 'united states' in preferred_locations and any(term in opportunity.location.lower() for term in ['usa', 'us', 'america']):
            location_score = 0.9
        
        score += location_score * weights.get('location_match', 0.2)
        
        # Urgency score (based on deadline proximity)
        urgency_score = self._calculate_urgency_score(opportunity.deadlines, profile.get('time_sensitivity', {}))
        score += urgency_score * weights.get('urgency', 0.1)
        
        # Bonus scoring for high-value signals (enhanced for content discovery)
        bonus_score = 0.0
        opportunity_full_text = f"{opportunity.title} {opportunity.organization} {opportunity.notes}".lower()
        
        # High-value organization bonus (expanded list)
        prestigious_orgs = [
            'nsf', 'nih', 'darpa', 'google', 'microsoft', 'openai', 'anthropic', 'stanford', 'mit', 'berkeley',
            'apple', 'meta', 'amazon', 'nvidia', 'adobe', 'databricks', 'hugging face', 'cohere',
            'deepmind', 'tesla', 'spacex', 'stripe', 'airbnb', 'uber', 'netflix', 'spotify'
        ]
        if any(org in opportunity_full_text for org in prestigious_orgs):
            bonus_score += 0.15  # Increased from 0.1
        
        # Fellowship/grant bonus
        if any(term in opportunity_full_text for term in ['fellowship', 'grant', 'scholarship', 'funding']):
            bonus_score += 0.1
        
        # Technical content relevance bonus
        if any(term in opportunity_full_text for term in [
            'developer', 'programming', 'coding', 'software', 'ai', 'machine learning', 
            'deep learning', 'neural network', 'algorithm', 'data science', 'python',
            'javascript', 'react', 'css', 'html', 'api', 'framework', 'library'
        ]):
            bonus_score += 0.1
        
        # Industry intelligence bonus (for staying current)
        if any(term in opportunity_full_text for term in [
            'announcement', 'release', 'launch', 'update', 'breakthrough', 'innovation',
            'trending', 'viral', 'popular', 'featured', 'spotlight'
        ]):
            bonus_score += 0.08
        
        # Research opportunity bonus
        if any(term in opportunity_full_text for term in ['research', 'phd', 'graduate', 'academic']):
            bonus_score += 0.05
        
        # Creative/Design technical content bonus
        if any(term in opportunity_full_text for term in [
            'design', 'ui', 'ux', 'creative', 'visual', 'css', 'animation', 'graphics'
        ]):
            bonus_score += 0.06
        
        final_score = min(score + bonus_score, 1.0)
        return final_score
    
    def calculate_interest_vibes_score(self, opportunity: EmailOpportunity) -> float:
        """Calculate interest score based on 'vibes' and contextual understanding using LLM."""
        try:
            # Import here to avoid circular imports
            import dspy
            
            profile = self.load_profile()
            interests = profile.get('interests', [])
            
            # Create a vibe-based evaluator
            vibe_evaluator = dspy.ChainOfThought(
                "title, content, user_interests -> relevance_score: float, reasoning: str"
            )
            
            interest_analysis_prompt = f"""
            Analyze how interesting this content would be to someone with these interests and preferences:
            
            Title: {opportunity.title}
            Organization: {opportunity.organization}
            Content: {opportunity.notes[:800]}...
            
            User's stated interests: {', '.join(interests)}
            
            Beyond keywords, consider:
            - Is this content technically sophisticated and intellectually stimulating?
            - Would this help the user stay current with tech/AI trends?
            - Does this represent cutting-edge developments or insights?
            - Is this the kind of content a technical professional would find valuable?
            - Would this content spark curiosity or provide useful knowledge?
            
            Rate relevance 0.0-1.0 where:
            - 0.0-0.2: Completely uninteresting/irrelevant
            - 0.3-0.5: Somewhat interesting but not compelling  
            - 0.6-0.8: Quite interesting and relevant
            - 0.9-1.0: Extremely compelling and valuable
            
            Consider the 'vibe' - even if keywords don't match exactly, technical depth and innovation matter.
            """
            
            result = vibe_evaluator(
                title=opportunity.title,
                content=opportunity.notes[:800],
                user_interests=str(interests)
            )
            
            try:
                score = float(result.relevance_score)
                return max(0.0, min(1.0, score))  # Clamp to 0-1 range
            except:
                return 0.5  # Default to neutral if parsing fails
                
        except Exception as e:
            self.logger.warning(f"LLM-based vibe scoring failed: {e}, using fallback")
            # Fallback to existing keyword-based approach
            return self._calculate_keyword_interest_score(opportunity)
    
    def _calculate_keyword_interest_score(self, opportunity: EmailOpportunity) -> float:
        """Fallback keyword-based interest scoring."""
        profile = self.load_profile()
        interests = [i.lower() for i in profile.get('interests', [])]
        opportunity_text = f"{opportunity.title} {opportunity.notes}".lower()
        
        if not interests:
            return 0.5
        
        # Direct matches
        direct_matches = sum(1 for interest in interests if interest in opportunity_text)
        
        # Partial matches with technical terms
        partial_score = 0
        tech_indicators = ['ai', 'tech', 'software', 'programming', 'algorithm', 'system', 'platform', 'framework']
        for indicator in tech_indicators:
            if indicator in opportunity_text:
                partial_score += 0.1
        
        # Calculate final score
        base_score = direct_matches / len(interests) if interests else 0
        final_score = min(base_score + partial_score, 1.0)
        
        return final_score
    
    def _calculate_urgency_score(self, deadlines: str, time_sensitivity: Dict[str, int]) -> float:
        """Calculate urgency score based on deadline proximity."""
        try:
            # Simple heuristic: look for date patterns in deadline text
            from dateutil.parser import parse
            import re
            
            # Extract potential dates from deadline text
            date_patterns = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}', deadlines)
            
            if not date_patterns:
                return 0.3  # No clear deadline, medium urgency
            
            # Parse the first found date
            deadline_date = parse(date_patterns[0], fuzzy=True)
            days_until = (deadline_date - datetime.now()).days
            
            if days_until <= time_sensitivity.get('urgent_days', 7):
                return 1.0
            elif days_until <= time_sensitivity.get('important_days', 30):
                return 0.7
            elif days_until <= time_sensitivity.get('exploratory_days', 90):
                return 0.4
            else:
                return 0.1
                
        except Exception:
            return 0.3  # Default medium urgency if parsing fails
    
    def should_exclude(self, opportunity: EmailOpportunity) -> bool:
        """Check if opportunity should be excluded based on profile using LLM-based contextual understanding."""
        profile = self.load_profile()
        
        exclusions = [e.lower() for e in profile.get('exclusions', [])]
        avoid_fields = [a.lower() for a in profile.get('avoid_fields', [])]
        
        opportunity_text = f"{opportunity.title} {opportunity.organization} {opportunity.notes}".lower()
        
        # First, check for obvious spam/unwanted patterns (keep some keyword filtering for clear cases)
        obvious_spam_patterns = ['pyramid scheme', 'mlm', 'get rich quick', 'binary options', 'forex trading']
        for pattern in obvious_spam_patterns:
            if pattern in opportunity_text:
                return True
        
        # For more nuanced exclusions like "marketing" or "sales", use contextual analysis
        contextual_exclusions = [e for e in exclusions if e not in obvious_spam_patterns]
        contextual_avoid_fields = avoid_fields
        
        if contextual_exclusions or contextual_avoid_fields:
            # Use LLM to determine if this is genuinely uninteresting vs contextually relevant
            return self._llm_based_exclusion_check(opportunity, contextual_exclusions, contextual_avoid_fields)
        
        return False
    
    def _llm_based_exclusion_check(self, opportunity: EmailOpportunity, exclusions: List[str], avoid_fields: List[str]) -> bool:
        """Use LLM to make contextual decisions about whether to exclude content."""
        try:
            # Import here to avoid circular imports
            from .extraction import LLMExtractionService
            import dspy
            
            # Simple prompt to evaluate contextual relevance
            context_evaluator = dspy.ChainOfThought(
                "title, organization, content, exclusions, avoid_fields -> should_exclude: bool, reasoning: str"
            )
            
            exclusion_prompt = f"""
            Analyze if this content should be excluded based on user preferences:
            
            Title: {opportunity.title}
            Organization: {opportunity.organization}
            Content: {opportunity.notes[:500]}...
            
            User wants to avoid: {', '.join(exclusions + avoid_fields)}
            
            However, the user is interested in technical content, AI/ML, software engineering, and industry intelligence.
            
            Consider context: Is this content actually about what the user wants to avoid, or does it just mention those terms 
            in a technical/analytical context that would be interesting?
            
            Examples of what TO EXCLUDE: Job postings for sales roles, MLM schemes, cryptocurrency trading promotions
            Examples of what to KEEP: Technical articles about marketing technology, AI in sales, security analysis of tracking
            """
            
            result = context_evaluator(
                title=opportunity.title,
                organization=opportunity.organization, 
                content=opportunity.notes[:500],
                exclusions=str(exclusions),
                avoid_fields=str(avoid_fields)
            )
            
            # Convert boolean result to string comparison
            should_exclude = str(result.should_exclude).lower() == 'true'
            return should_exclude
            
        except Exception as e:
            # Fallback to more lenient keyword filtering if LLM fails
            self.logger.warning(f"LLM-based exclusion check failed: {e}, using fallback")
            
            # Only exclude if exclusion terms are primary focus (not just mentioned)
            for exclusion in exclusions:
                # More sophisticated keyword check - must be prominent in title or heavily in content
                if exclusion in opportunity.title.lower():
                    return True
                elif opportunity.notes.lower().count(exclusion) > 3:  # Mentioned multiple times
                    return True
            
            return False


class DatabaseManager:
    """Manages SQLite database operations for storing processed emails and opportunities."""
    
    def __init__(self, db_path: str = "data/sentinel.db"):
        self.db_path = db_path
        self._ensure_directory()
        self._initialize_db()
    
    def _ensure_directory(self):
        """Ensure the database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _initialize_db(self):
        """Initialize database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    uid TEXT PRIMARY KEY,
                    processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    subject TEXT,
                    sender TEXT,
                    date_received TIMESTAMP,
                    account_name TEXT DEFAULT 'Primary Account'
                );
                
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT,
                    title TEXT,
                    organization TEXT,
                    opportunity_type TEXT,
                    eligibility TEXT,
                    location TEXT,
                    deadlines TEXT,
                    notes TEXT,
                    email_date TIMESTAMP,
                    processed_date TIMESTAMP,
                    priority_score REAL,
                    category TEXT,
                    original_urls TEXT,
                    primary_url TEXT,
                    urls_with_context TEXT,
                    mailto_addresses TEXT,
                    calendar_links TEXT,
                    attachment_info TEXT,
                    email_headers TEXT,
                    deadlines_from_links TEXT,
                    account_name TEXT DEFAULT 'Primary Account',
                    FOREIGN KEY (uid) REFERENCES processed_emails (uid)
                );
                
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_date DATE,
                    high_priority_count INTEGER,
                    exploratory_count INTEGER,
                    summary_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_processed_emails_uid ON processed_emails(uid);
                CREATE INDEX IF NOT EXISTS idx_processed_emails_account ON processed_emails(account_name);
                CREATE INDEX IF NOT EXISTS idx_opportunities_category ON opportunities(category);
                CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(priority_score);
                CREATE INDEX IF NOT EXISTS idx_opportunities_primary_url ON opportunities(primary_url);
                CREATE INDEX IF NOT EXISTS idx_opportunities_account ON opportunities(account_name);
            """)
            
            # Run migration to add new columns to existing databases
            self._migrate_database()
    
    def is_email_processed(self, uid: str) -> bool:
        """Check if email UID has already been processed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM processed_emails WHERE uid = ?", (uid,))
            return cursor.fetchone() is not None
    
    def mark_email_processed(self, uid: str, subject: str, sender: str, date_received: datetime, account_name: str = "Primary Account"):
        """Mark email as processed with account information."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_emails (uid, subject, sender, date_received, account_name) VALUES (?, ?, ?, ?, ?)",
                (uid, subject, sender, date_received, account_name)
            )
    
    def save_opportunity(self, opportunity: EmailOpportunity):
        """Save extracted opportunity to database."""
        import json
        
        # Extract account name from composite UID if present
        account_name = "Primary Account"
        if hasattr(opportunity, 'account_name'):
            account_name = opportunity.account_name
        elif ':' in opportunity.uid:
            account_name = opportunity.uid.split(':', 1)[0]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO opportunities 
                (uid, title, organization, opportunity_type, eligibility, location, 
                 deadlines, notes, email_date, processed_date, priority_score, category,
                 original_urls, primary_url, urls_with_context, mailto_addresses,
                 calendar_links, attachment_info, email_headers, deadlines_from_links, account_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opportunity.uid, opportunity.title, opportunity.organization,
                opportunity.opportunity_type, opportunity.eligibility, opportunity.location,
                opportunity.deadlines, opportunity.notes, opportunity.email_date,
                opportunity.processed_date, opportunity.priority_score, opportunity.category,
                json.dumps(opportunity.original_urls) if opportunity.original_urls else None,
                opportunity.primary_url,
                json.dumps(opportunity.urls_with_context) if opportunity.urls_with_context else None,
                json.dumps(opportunity.mailto_addresses) if opportunity.mailto_addresses else None,
                json.dumps(opportunity.calendar_links) if opportunity.calendar_links else None,
                json.dumps(opportunity.attachment_info) if opportunity.attachment_info else None,
                json.dumps(opportunity.email_headers) if opportunity.email_headers else None,
                json.dumps(opportunity.deadlines_from_links) if opportunity.deadlines_from_links else None,
                account_name
            ))
    
    def get_recent_opportunities(self, days: int = 1) -> List[EmailOpportunity]:
        """Get opportunities from the last N days."""
        import json
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM opportunities 
                WHERE processed_date >= ?
                ORDER BY priority_score DESC, processed_date DESC
            """, (cutoff_date,))
            
            opportunities = []
            for row in cursor.fetchall():
                # Parse JSON fields safely
                try:
                    original_urls = json.loads(row['original_urls']) if row['original_urls'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    original_urls = []
                
                try:
                    urls_with_context = json.loads(row['urls_with_context']) if row['urls_with_context'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    urls_with_context = []
                
                try:
                    mailto_addresses = json.loads(row['mailto_addresses']) if row['mailto_addresses'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    mailto_addresses = []
                
                try:
                    calendar_links = json.loads(row['calendar_links']) if row['calendar_links'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    calendar_links = []
                
                try:
                    attachment_info = json.loads(row['attachment_info']) if row['attachment_info'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    attachment_info = []
                
                try:
                    email_headers = json.loads(row['email_headers']) if row['email_headers'] else {}
                except (KeyError, TypeError, json.JSONDecodeError):
                    email_headers = {}
                
                try:
                    deadlines_from_links = json.loads(row['deadlines_from_links']) if row['deadlines_from_links'] else []
                except (KeyError, TypeError, json.JSONDecodeError):
                    deadlines_from_links = []
                
                try:
                    primary_url = row['primary_url']
                except KeyError:
                    primary_url = None
                
                opportunities.append(EmailOpportunity(
                    uid=row['uid'],
                    title=row['title'],
                    organization=row['organization'],
                    opportunity_type=row['opportunity_type'],
                    eligibility=row['eligibility'],
                    location=row['location'],
                    deadlines=row['deadlines'],
                    notes=row['notes'],
                    email_date=datetime.fromisoformat(row['email_date']),
                    processed_date=datetime.fromisoformat(row['processed_date']),
                    priority_score=row['priority_score'],
                    category=row['category'],
                    original_urls=original_urls,
                    primary_url=row['primary_url'] if 'primary_url' in row.keys() else None,
                    urls_with_context=urls_with_context,
                    mailto_addresses=mailto_addresses,
                    calendar_links=calendar_links,
                    attachment_info=attachment_info,
                    email_headers=email_headers,
                    deadlines_from_links=deadlines_from_links
                ))
            
            return opportunities
    
    def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old processed emails and opportunities."""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM opportunities WHERE processed_date < ?", (cutoff_date,))
            conn.execute("DELETE FROM processed_emails WHERE processed_date < ?", (cutoff_date,))
    
    def _migrate_database(self):
        """Migrate existing database to add new metadata columns and account support."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check which columns already exist in opportunities table
            cursor.execute("PRAGMA table_info(opportunities)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            # Define new columns and their SQL types
            new_columns = {
                'original_urls': 'TEXT',
                'primary_url': 'TEXT', 
                'urls_with_context': 'TEXT',
                'mailto_addresses': 'TEXT',
                'calendar_links': 'TEXT',
                'attachment_info': 'TEXT',
                'email_headers': 'TEXT',
                'deadlines_from_links': 'TEXT',
                'account_name': "TEXT DEFAULT 'Primary Account'"
            }
            
            # Add any missing columns to opportunities table
            for column_name, column_type in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE opportunities ADD COLUMN {column_name} {column_type}")
                        logging.info(f"Added column {column_name} to opportunities table")
                    except sqlite3.OperationalError as e:
                        # Column might already exist, or other error
                        logging.warning(f"Could not add column {column_name}: {e}")
            
            # Check which columns already exist in processed_emails table
            cursor.execute("PRAGMA table_info(processed_emails)")
            existing_processed_columns = [column[1] for column in cursor.fetchall()]
            
            # Add account_name column to processed_emails table if missing
            if 'account_name' not in existing_processed_columns:
                try:
                    cursor.execute("ALTER TABLE processed_emails ADD COLUMN account_name TEXT DEFAULT 'Primary Account'")
                    logging.info("Added account_name column to processed_emails table")
                except sqlite3.OperationalError as e:
                    logging.warning(f"Could not add account_name column to processed_emails: {e}")
            
            # Add indexes for performance if they don't exist
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_opportunities_primary_url ON opportunities(primary_url)",
                "CREATE INDEX IF NOT EXISTS idx_opportunities_account ON opportunities(account_name)",
                "CREATE INDEX IF NOT EXISTS idx_processed_emails_account ON processed_emails(account_name)"
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except sqlite3.OperationalError:
                    pass  # Index might already exist


def setup_logging(log_directory: str = "logs/", log_level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    Path(log_directory).mkdir(parents=True, exist_ok=True)
    
    log_file = Path(log_directory) / f"sentinel_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('sentinel')


def safe_extract_text(text: str, max_length: int = 1000) -> str:
    """Safely extract and clean text for processing."""
    if not text:
        return ""
    
    # Remove excessive whitespace and normalize
    cleaned = ' '.join(text.split())
    
    # Truncate if too long
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    
    return cleaned


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity between two texts using sentence transformers."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Use a lightweight model for similarity
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        embeddings1 = model.encode([text1])
        embeddings2 = model.encode([text2])
        
        similarity = cosine_similarity(embeddings1, embeddings2)[0][0]
        return float(similarity)
        
    except ImportError:
        # Fallback to simple keyword overlap if sentence-transformers not available
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Convert to numpy arrays and reshape for sklearn
        v1 = np.array(vec1).reshape(1, -1)
        v2 = np.array(vec2).reshape(1, -1)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(v1, v2)[0][0]
        return float(similarity)
        
    except Exception:
        # Fallback to manual calculation
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)