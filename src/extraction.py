"""
LLM-based extraction module using DSPy with Together AI for structured opportunity extraction.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

import dspy
from pydantic import BaseModel, Field

from .email_ingestion import EmailMessage
from .utils import ConfigManager, EmailOpportunity, safe_extract_text, ProfileManager
from .semantic_filter import SemanticFilter


class OpportunityExtraction(dspy.Signature):
    """
    Extract structured opportunity information from email content.
    This includes formal opportunities AND interesting content like news articles that mention opportunities or valuable industry insights.
    """
    email_text: str = dspy.InputField(desc="The full email content.")
    
    output: list[dict[str, str]] = dspy.OutputField(desc="""
    Extracted opportunities or interesting content, where each entry contains:
    - title
    - organization
    - opportunity_type (fellowship, job opening, grant, conference, research position, scholarship, news_with_opportunities, interesting_content, industry_update)
    - eligibility
    - location
    - deadline
    - notes
    
    Include formal opportunities AND news articles that mention opportunities or provide valuable industry insights.
    Examples: "OpenAI Releases o3-pro" should be extracted as interesting_content with relevant details.
    """)


class OpportunityRelevanceSignature(dspy.Signature):
    """DSPy signature for determining if an email contains a relevant opportunity or interesting content."""
    
    email_content = dspy.InputField(desc="Email subject and body content to analyze")
    sender = dspy.InputField(desc="Email sender information")
    
    is_opportunity = dspy.OutputField(desc="TRUE if email contains a career/academic opportunity OR interesting industry content (news, updates, insights), FALSE otherwise")
    confidence = dspy.OutputField(desc="Confidence level (LOW, MEDIUM, HIGH)")
    reasoning = dspy.OutputField(desc="Brief explanation of the decision")


class LLMExtractionService:
    """Service for extracting opportunities from emails using LLM."""
    
    def __init__(self, config_manager: ConfigManager, profile_manager: ProfileManager = None):
        self.config = config_manager
        self.profile_manager = profile_manager
        self.logger = logging.getLogger(__name__)
        self._initialize_llm()
        self._setup_extractors()
        self._initialize_semantic_filter()
    
    def _initialize_llm(self):
        """Initialize DSPy with Together AI."""
        llm_config = self.config.get('llm')
        
        try:
            if llm_config['provider'] == 'together_ai':
                # Configure Together AI LLM using DSPy's LM class with LiteLLM format
                model = dspy.LM(
                    model=llm_config['model'],  # Format: together_ai/model_name
                    model_type='chat',
                    temperature=llm_config.get('temperature', 0.0),
                    max_tokens=llm_config.get('max_tokens', 2048),
                    api_key=llm_config['api_key']
                )
                
                dspy.settings.configure(lm=model)
                self.logger.info(f"Initialized Together AI LLM: {llm_config['model']}")
                
            elif llm_config['provider'] == 'ollama':
                # Fallback to Ollama for backward compatibility
                lm = dspy.LM(
                    model=f"ollama/{llm_config['model']}",
                    model_type='chat',
                    temperature=llm_config.get('temperature', 0.1),
                    max_tokens=llm_config.get('max_tokens', 2048)
                )
                dspy.settings.configure(lm=lm)
                self.logger.info(f"Initialized Ollama LLM: {llm_config['model']}")
            else:
                raise ValueError(f"Unsupported LLM provider: {llm_config['provider']}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    def _setup_extractors(self):
        """Set up DSPy modules for extraction."""
        self.relevance_checker = dspy.ChainOfThought(OpportunityRelevanceSignature)
        self.opportunity_extractor = dspy.Predict(OpportunityExtraction)
    
    def _initialize_semantic_filter(self):
        """Initialize semantic filter if profile manager is available."""
        try:
            if self.profile_manager:
                self.semantic_filter = SemanticFilter(self.config, self.profile_manager)
                if self.semantic_filter.client:
                    self.logger.info("Semantic filter initialized successfully")
                else:
                    self.logger.warning("Semantic filter initialization failed, will skip filtering")
                    self.semantic_filter = None
            else:
                self.logger.info("No profile manager provided, semantic filtering disabled")
                self.semantic_filter = None
        except Exception as e:
            self.logger.warning(f"Failed to initialize semantic filter: {e}")
            self.semantic_filter = None
    
    def is_relevant_opportunity(self, email: EmailMessage) -> tuple[bool, str]:
        """Check if email contains a relevant opportunity."""
        try:
            # Prepare email content for analysis
            email_content = f"Subject: {email.subject}\n\nBody: {email.body}"
            
            # Use LLM to determine relevance
            result = self.relevance_checker(
                email_content=email_content,
                sender=email.sender
            )
            
            is_relevant = result.is_opportunity.upper() == 'TRUE'
            confidence = result.confidence.upper()
            reasoning = result.reasoning
            
            self.logger.debug(
                f"Relevance check for email {email.uid}: "
                f"relevant={is_relevant}, confidence={confidence}, reasoning={reasoning}"
            )
            
            return is_relevant, f"{confidence}: {reasoning}"
            
        except Exception as e:
            self.logger.error(f"Error checking relevance for email {email.uid}: {e}")
            # Default to relevant if we can't determine (conservative approach)
            return True, "ERROR: Could not determine relevance"
    
    def extract_opportunity(self, email: EmailMessage) -> Optional[EmailOpportunity]:
        """Extract structured opportunity data from email."""
        try:
            # First check if email is relevant
            is_relevant, reasoning = self.is_relevant_opportunity(email)
            
            if not is_relevant:
                self.logger.debug(f"Email {email.uid} not relevant: {reasoning}")
                return None

            # Prepare email content for extraction
            email_text = f"Subject: {email.subject}\n\nBody: {email.body}"
            
            # Extract opportunity details using DSPy
            result = self.opportunity_extractor(email_text=email_text)
            
            # Parse the structured output
            opportunities = result.output
            if not opportunities or len(opportunities) == 0:
                self.logger.debug(f"No opportunities found in email {email.uid}")
                return None
            
            # Take the first opportunity (could extend to handle multiple)
            opp_data = opportunities[0]
            
            # Create opportunity object with metadata
            metadata = email.metadata or {}
            opportunity = EmailOpportunity(
                uid=email.composite_uid if hasattr(email, 'composite_uid') else email.uid,
                title=safe_extract_text(opp_data.get('title', ''), 200),
                organization=safe_extract_text(opp_data.get('organization', ''), 200),
                opportunity_type=safe_extract_text(opp_data.get('opportunity_type', ''), 100),
                eligibility=safe_extract_text(opp_data.get('eligibility', ''), 500),
                location=safe_extract_text(opp_data.get('location', ''), 200),
                deadlines=safe_extract_text(opp_data.get('deadline', ''), 300),
                notes=safe_extract_text(opp_data.get('notes', ''), 1000),
                email_date=email.date_received,
                # Add metadata fields
                original_urls=metadata.get('original_urls', []),
                urls_with_context=metadata.get('urls_with_context', []),
                mailto_addresses=metadata.get('mailto_addresses', []),
                calendar_links=metadata.get('calendar_links', []),
                attachment_info=metadata.get('attachment_info', []),
                email_headers=metadata.get('email_headers', {}),
                deadlines_from_links=metadata.get('deadlines_from_links', []),
                account_name=email.account_name if hasattr(email, 'account_name') else "Primary Account"
            )
            
            # Select primary URL using intelligent scoring
            opportunity.primary_url = self._select_primary_url(opportunity)
            
            self.logger.info(f"Extracted opportunity from email {email.uid}: {opportunity.title}")
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error extracting opportunity from email {email.uid}: {e}")
            return None
    
    def extract_opportunities_batch(self, emails: List[EmailMessage]) -> List[EmailOpportunity]:
        """Extract opportunities from a batch of emails with semantic pre-filtering."""
        opportunities = []
        
        self.logger.info(f"Starting opportunity extraction pipeline for {len(emails)} emails")
        
        # Step 1: Semantic pre-filtering (if available)
        emails_to_process = emails
        if self.semantic_filter:
            self.logger.info("Applying semantic pre-filtering...")
            emails_to_process = self.semantic_filter.filter_emails_batch(emails)
            
            filtered_count = len(emails_to_process)
            original_count = len(emails)
            filter_rate = (original_count - filtered_count) / original_count * 100 if original_count > 0 else 0
            
            self.logger.info(
                f"Semantic filtering results: {filtered_count}/{original_count} emails passed "
                f"({filter_rate:.1f}% filtered out)"
            )
        else:
            self.logger.info("Semantic filtering disabled, processing all emails")
        
        # Step 2: LLM-based extraction on filtered emails
        self.logger.info(f"Starting LLM extraction on {len(emails_to_process)} emails")
        
        for i, email in enumerate(emails_to_process, 1):
            try:
                self.logger.debug(f"Processing email {i}/{len(emails_to_process)}: {email.subject}")
                
                opportunity = self.extract_opportunity(email)
                if opportunity:
                    opportunities.append(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error processing email {i}: {e}")
                continue
        
        # Step 3: Summary statistics
        extraction_rate = len(opportunities) / len(emails_to_process) * 100 if emails_to_process else 0
        overall_rate = len(opportunities) / len(emails) * 100 if emails else 0
        
        self.logger.info(
            f"Extraction pipeline complete: {len(opportunities)} opportunities extracted\n"
            f"  - Extraction rate on filtered emails: {extraction_rate:.1f}%\n"
            f"  - Overall extraction rate: {overall_rate:.1f}%\n"
            f"  - Total emails processed: {len(emails)} -> {len(emails_to_process)} -> {len(opportunities)}"
        )
        
        return opportunities
    
    def get_pipeline_stats(self) -> dict:
        """Get statistics about the extraction pipeline."""
        stats = {
            "llm_initialized": hasattr(self, 'opportunity_extractor'),
            "semantic_filter": None
        }
        
        if self.semantic_filter:
            stats["semantic_filter"] = self.semantic_filter.get_filter_stats()
        
        return stats
    
    def test_extraction(self, sample_text: str) -> dict:
        """Test extraction functionality with sample text."""
        try:
            # Create a test email message
            test_email = EmailMessage(
                uid="test",
                subject="Test Opportunity",
                sender="test@example.com",
                body=sample_text,
                date_received=datetime.now()  # Provide a valid datetime
            )
            
            # Test relevance checking
            is_relevant, reasoning = self.is_relevant_opportunity(test_email)
            
            result = {
                "is_relevant": is_relevant,
                "reasoning": reasoning,
                "opportunity": None
            }
            
            if is_relevant:
                # Test extraction
                opportunity = self.extract_opportunity(test_email)
                if opportunity:
                    result["opportunity"] = {
                        "title": opportunity.title,
                        "organization": opportunity.organization,
                        "type": opportunity.opportunity_type,
                        "eligibility": opportunity.eligibility,
                        "location": opportunity.location,
                        "deadlines": opportunity.deadlines,
                        "notes": opportunity.notes
                    }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in test extraction: {e}")
            return {"error": str(e)}
    
    def _select_primary_url(self, opportunity: EmailOpportunity) -> Optional[str]:
        """Select the most relevant URL as the primary application link."""
        if not opportunity.urls_with_context:
            return opportunity.original_urls[0] if opportunity.original_urls else None
        
        # Score URLs based on relevance criteria
        url_scores = []
        
        for url_data in opportunity.urls_with_context:
            url = url_data['url']
            anchor_text = url_data['anchor_text'].lower()
            context = url_data['context'].lower()
            combined_text = f"{anchor_text} {context}"
            
            score = 0
            
            # High priority keywords in anchor text
            high_priority_keywords = [
                'apply', 'application', 'submit', 'register', 'enrollment',
                'nomination', 'proposal', 'deadline', 'form'
            ]
            for keyword in high_priority_keywords:
                if keyword in anchor_text:
                    score += 10
                elif keyword in context:
                    score += 5
            
            # Medium priority keywords
            medium_priority_keywords = [
                'details', 'information', 'more', 'learn', 'about',
                'program', 'opportunity', 'fellowship', 'grant'
            ]
            for keyword in medium_priority_keywords:
                if keyword in anchor_text:
                    score += 3
                elif keyword in context:
                    score += 1
            
            # Domain authority scoring
            if any(domain in url for domain in ['.edu', '.gov', '.org']):
                score += 5
            elif any(domain in url for domain in ['.com', '.net']):
                score += 2
            
            # PDF or form indicators
            if any(ext in url.lower() for ext in ['.pdf', 'form', 'application']):
                score += 8
            
            # Penalize social media or generic links
            if any(social in url.lower() for social in ['facebook', 'twitter', 'linkedin', 'instagram']):
                score -= 5
            elif any(generic in url.lower() for generic in ['unsubscribe', 'privacy', 'terms']):
                score -= 10
            
            url_scores.append((url, score))
        
        # Sort by score (highest first) and return the best URL
        if url_scores:
            url_scores.sort(key=lambda x: x[1], reverse=True)
            return url_scores[0][0] if url_scores[0][1] > 0 else None
        
        return None


class FallbackExtractor:
    """Fallback extraction using rule-based methods when LLM is unavailable."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common opportunity keywords
        self.opportunity_keywords = {
            'fellowship': ['fellowship', 'fellow program', 'research fellow'],
            'job': ['job opening', 'position available', 'hiring', 'career opportunity'],
            'conference': ['conference', 'symposium', 'workshop', 'summit'],
            'grant': ['grant', 'funding', 'award', 'scholarship'],
            'internship': ['internship', 'intern position', 'summer program']
        }
        
        # Exclusion patterns
        self.exclusion_patterns = [
            'unsubscribe', 'spam', 'marketing', 'advertisement',
            'promotional', 'newsletter only'
        ]
    
    def is_relevant_opportunity(self, email: EmailMessage) -> tuple[bool, str]:
        """Simple rule-based relevance checking."""
        content = f"{email.subject} {email.body}".lower()
        
        # Check for exclusion patterns
        for pattern in self.exclusion_patterns:
            if pattern in content:
                return False, f"Contains exclusion pattern: {pattern}"
        
        # Check for opportunity keywords
        for opp_type, keywords in self.opportunity_keywords.items():
            for keyword in keywords:
                if keyword in content:
                    return True, f"Contains {opp_type} keyword: {keyword}"
        
        return False, "No opportunity keywords found"
    
    def extract_basic_info(self, email: EmailMessage) -> Optional[EmailOpportunity]:
        """Extract basic opportunity information using rules."""
        is_relevant, reasoning = self.is_relevant_opportunity(email)
        
        if not is_relevant:
            return None
        
        # Determine opportunity type
        content = f"{email.subject} {email.body}".lower()
        opportunity_type = "unknown"
        
        for opp_type, keywords in self.opportunity_keywords.items():
            for keyword in keywords:
                if keyword in content:
                    opportunity_type = opp_type
                    break
            if opportunity_type != "unknown":
                break
        
        # Extract basic information
        return EmailOpportunity(
            uid=email.uid,
            title=email.subject[:200] if email.subject else "Untitled Opportunity",
            organization=self._extract_organization(email.sender),
            opportunity_type=opportunity_type,
            eligibility="See email for details",
            location="See email for details",
            deadlines="See email for deadlines",
            notes=safe_extract_text(email.body, 500),
            email_date=email.date_received
        )
    
    def _extract_organization(self, sender: str) -> str:
        """Extract organization name from sender email."""
        try:
            # Simple extraction from email domain
            if '@' in sender:
                domain = sender.split('@')[-1].split('>')[0]
                # Remove common email domains
                if domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                    return domain.replace('.com', '').replace('.edu', '').replace('.org', '').title()
            return "Unknown Organization"
        except:
            return "Unknown Organization"