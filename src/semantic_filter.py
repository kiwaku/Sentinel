"""
Semantic filtering module for pre-filtering emails using Together AI embeddings.
"""

import json
import logging
from typing import List, Optional

try:
    from together import Together
except ImportError:
    Together = None

from .email_ingestion import EmailMessage
from .utils import ConfigManager, ProfileManager


class SemanticFilter:
    """Semantic email filtering using Together AI embeddings."""
    
    def __init__(self, config_manager: ConfigManager, profile_manager: ProfileManager):
        self.config = config_manager
        self.profile_manager = profile_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize whitelist and blacklist for sender filtering
        self.sender_whitelist = [
            # Add trusted senders here - these emails will ALWAYS bypass semantic filtering
            'dan@tldrnewsletter.com',  # TLDR Newsletter - always interesting tech content
            'fellowship@nsf.gov',  # NSF fellowship emails - always important
            'opportunities@stanford.edu',  # Stanford opportunities - research focused
            'grants@nih.gov',  # NIH grants - medical research funding
            'noreply@acm.org',  # ACM conference notifications
            'info@ieee.org',  # IEEE professional opportunities
            
            # You can add more email addresses like this:
            # 'important-sender@example.com',
            # 'newsletter@trusted-source.org',
        ]
        
        self.sender_blacklist = [
            # Add blocked senders here - these emails will be IMMEDIATELY rejected
            'marketing@amazon.com',  # Amazon marketing emails
            'promotions@linkedin.com',  # LinkedIn promotional emails
            'newsletter@medium.com',  # Medium newsletter (too broad)
            'noreply@coursera.com',  # Coursera promotional emails
            
            # You can add email addresses like this:
            # 'promotions@shopping-site.com',
            # 'newsletter@irrelevant-service.com',
        ]
        
        # Initialize Together AI client
        llm_config = self.config.get('llm')
        
        # Check if Together AI is available
        if Together is None:
            self.logger.warning("Together AI SDK not available - semantic filtering disabled")
            self.client = None
            return
        
        try:
            self.client = Together(api_key=llm_config.get('api_key'))
            self.embedding_model = "togethercomputer/m2-bert-80M-8k-retrieval"
            self.similarity_threshold = 0.20  # Lowered from 0.25 to capture more content including news
            self.profile_embedding = None
            self._generate_profile_embedding()
            self.logger.info("Semantic filter initialized with Together AI embeddings")
        except Exception as e:
            self.logger.error(f"Failed to initialize semantic filter: {e}")
            self.client = None
    
    def _generate_profile_embedding(self):
        """Generate embedding for intelligence discovery system optimized for weak signal detection."""
        try:
            profile = self.profile_manager.load_profile()
            profile_parts = []
            
            # 1️⃣ OPPORTUNITY-ORIENTED DISCOVERY
            # Core interests with opportunity context (from existing profile)
            interests = profile.get('interests', [])
            if interests:
                profile_parts.append("Core technical interests: " + " ".join(interests))
            
            # Traditional research opportunities with high-value signals
            research_opportunities = [
                "research fellowship", "postdoc position", "PhD funding", "graduate research assistantship",
                "research collaboration", "academic research position", "university research lab",
                "NSF fellowship", "NIH fellowship", "DARPA research", "industry research lab",
                "Google Research", "Microsoft Research", "OpenAI research", "Anthropic research",
                "research internship", "summer research program", "visiting researcher",
                # Additional high-value research signals
                "GRFP", "graduate research fellowship program", "predoctoral fellowship",
                "NDSEG fellowship", "DOE SCGSR", "Hertz fellowship", "Ford foundation fellowship",
                "NIST fellowship", "NASA fellowship", "DOD fellowship", "intelligence community",
                "Stanford HAI", "MIT CSAIL", "Berkeley AI", "CMU ML", "DeepMind internship",
                "research scientist", "visiting scholar", "sabbatical", "collaboration opportunity"
            ]
            profile_parts.append("Research opportunities: " + " ".join(research_opportunities))
            
            # High-value startup and industry roles
            startup_signals = [
                "founding engineer", "early engineer", "technical co-founder", "startup opportunity",
                "seed stage", "series A", "YC company", "stealth startup", "founding team",
                "technical lead", "principal engineer", "staff engineer", "research engineer",
                "AI engineer", "machine learning engineer", "platform engineer", "infrastructure engineer"
            ]
            profile_parts.append("High-value roles: " + " ".join(startup_signals))
            
            # 2️⃣ CAPABILITY EXPANSION SIGNALS  
            # Developer tools and platforms for technical capacity expansion
            dev_tools_signals = [
                "developer preview", "early access", "beta program", "technical preview",
                "API access", "platform launch", "new framework", "developer tools",
                "SDK release", "open source", "GitHub", "developer program",
                "free credits", "academic license", "student access", "pro account",
                "cloud credits", "compute credits", "API credits", "free tier",
                # Enhanced developer ecosystem signals
                "GitHub copilot", "cursor IDE", "anthropic claude", "openai API",
                "together AI", "hugging face", "weights and biases", "W&B",
                "modal labs", "replicate", "paperspace", "vast.ai", "runpod",
                "lambda labs", "academic discount", "student developer pack",
                "google colab pro", "jupyter notebooks", "VSCode extensions",
                "developer conference", "hackathon", "coding competition", "bounty program"
            ]
            profile_parts.append("Developer tools expansion: " + " ".join(dev_tools_signals))
            
            # Advanced technical domains for capability expansion
            advanced_tech_domains = [
                "agent systems", "multi-agent", "LLM orchestration", "AI infrastructure",
                "brain-computer interface", "BCI", "neural interface", "neurotech",
                "spiking neural networks", "neuromorphic", "red teaming", "AI safety",
                "adversarial ML", "LLM security", "OS security", "systems security",
                "cryptocurrency security", "blockchain security", "zero-knowledge",
                "compression algorithms", "pipeline optimization", "distributed systems",
                # Enhanced emerging tech domains
                "large language models", "foundation models", "multimodal AI", "diffusion models",
                "reinforcement learning from human feedback", "RLHF", "constitutional AI",
                "retrieval augmented generation", "RAG", "vector databases", "embeddings",
                "prompt engineering", "few-shot learning", "in-context learning",
                "neural architecture search", "automated ML", "interpretability", "mechanistic interpretability",
                "alignment research", "AI governance", "compute governance", "model evaluation"
            ]
            profile_parts.append("Advanced technical domains: " + " ".join(advanced_tech_domains))
            
            # 🗞️ NEWS & INDUSTRY INTELLIGENCE
            # News articles, announcements, and industry updates that mention opportunities or trends
            news_tech_signals = [
                "announces", "releases", "launches", "unveils", "introduces", "debuts",
                "breakthrough", "innovation", "update", "version", "new feature",
                "industry news", "tech news", "research news", "company news",
                "press release", "announcement", "blog post", "article", "report",
                "OpenAI", "Google", "Microsoft", "Apple", "Meta", "Amazon", "NVIDIA",
                "Tesla", "SpaceX", "Anthropic", "Mistral", "Cohere", "Hugging Face",
                "news about", "minute read", "breaking", "exclusive", "insider",
                "tech industry", "AI industry", "startup ecosystem", "venture capital",
                "funding round", "acquisition", "partnership", "collaboration",
                "product launch", "platform update", "service announcement",
                "research findings", "study reveals", "survey shows", "data shows",
                "trend analysis", "market report", "industry insight", "expert opinion"
            ]
            profile_parts.append("News & industry intelligence: " + " ".join(news_tech_signals))

            # 3️⃣ INTELLECTUAL LEVERAGE SIGNALS
            # Research and knowledge discovery indicators
            intellectual_signals = [
                "research paper", "preprint", "arXiv", "new publication", "breakthrough",
                "technical blog", "deep dive", "tutorial", "framework documentation",
                "white paper", "technical report", "conference paper", "journal publication",
                "technical talk", "keynote", "workshop", "seminar", "webinar",
                "community invite", "Discord server", "Slack workspace", "private beta",
                "technical community", "research group", "study group", "reading group"
            ]
            profile_parts.append("Intellectual leverage: " + " ".join(intellectual_signals))
            
            # 4️⃣ MARKET & STRATEGY INTEL
            # Industry intelligence and strategic signals
            market_intel_signals = [
                "funding announcement", "Series A", "Series B", "acquisition", "merger",
                "startup launch", "company launch", "product launch", "platform launch",
                "AI startup", "neurotech startup", "security startup", "infrastructure startup",
                "venture capital", "investment", "valuation", "IPO", "public offering",
                "strategic partnership", "collaboration announcement", "joint venture",
                "talent acquisition", "hiring spree", "team expansion", "new office"
            ]
            profile_parts.append("Market intelligence: " + " ".join(market_intel_signals))
            
            # 5️⃣ WEAK SIGNAL AMPLIFICATION
            # Semantic anchors to catch edge cases and weak signals
            weak_signal_anchors = [
                "invitation only", "exclusive access", "limited spots", "application deadline",
                "early bird", "first access", "insider", "preview", "sneak peek",
                "confidential", "stealth", "unannounced", "upcoming", "launching soon",
                "behind the scenes", "insider information", "private demo", "closed beta",
                "waitlist", "priority access", "VIP access", "member exclusive",
                # Enhanced weak signal detection
                "alpha version", "prototype", "pilot program", "research preview",
                "invitation code", "invite only", "referral needed", "application required",
                "limited availability", "first come first served", "while supplies last",
                "select participants", "qualified candidates", "pre-registration",
                "expression of interest", "manifestation of interest", "intent to participate",
                "recruiting now", "applications open", "nominations open", "now accepting"
            ]
            profile_parts.append("Weak signal indicators: " + " ".join(weak_signal_anchors))
            
            # 📊 CONFERENCE & EVENT INTELLIGENCE
            # Academic conferences and industry events for networking and discovery
            conference_event_signals = [
                "conference", "symposium", "workshop", "summit", "meetup", "seminar",
                "NeurIPS", "ICML", "ICLR", "AAAI", "IJCAI", "ACL", "EMNLP", "CVPR", "ICCV",
                "ECCV", "SIGCHI", "UIST", "CSCW", "CHI", "FAccT", "AISTATS", "UAI",
                "call for papers", "CFP", "abstract submission", "paper deadline",
                "conference registration", "early bird registration", "student discount",
                "travel grant", "conference scholarship", "presentation opportunity",
                "poster session", "oral presentation", "workshop proposal",
                "tutorial submission", "demo track", "industry track", "academic track",
                "keynote speaker", "invited talk", "panel discussion", "roundtable"
            ]
            profile_parts.append("Conference & event intelligence: " + " ".join(conference_event_signals))
            
            # 💰 FUNDING & GRANT INTELLIGENCE
            # Grant opportunities and funding announcements for research and development
            funding_grant_signals = [
                "grant opportunity", "funding opportunity", "research grant", "innovation grant",
                "SBIR", "STTR", "small business innovation research", "small business technology transfer",
                "NSF grant", "NIH grant", "DOE grant", "NASA grant", "DARPA grant",
                "award notification", "grant award", "funding announcement", "RFP", "request for proposals",
                "proposal deadline", "grant deadline", "application deadline", "funding deadline",
                "phase I", "phase II", "phase III", "proof of concept", "feasibility study",
                "seed funding", "pilot funding", "bridge funding", "supplemental funding",
                "equipment grant", "travel grant", "conference grant", "publication fee",
                "open philanthropy", "schmidt futures", "mozilla foundation", "chan zuckerberg",
                "google.org", "microsoft AI for good", "facebook research", "amazon research"
            ]
            profile_parts.append("Funding & grant intelligence: " + " ".join(funding_grant_signals))
            
            # 6️⃣ ELIGIBILITY AND CONTEXT
            # Personal qualifications and context (from existing profile)
            eligibility = profile.get('eligibility_keywords', [])
            if eligibility:
                profile_parts.append("Personal qualifications: " + " ".join(eligibility))
            
            # Location preferences for remote/distributed opportunities
            locations = profile.get('preferred_locations', [])
            if locations:
                profile_parts.append("Location preferences: " + " ".join(locations))
            
            # 7️⃣ HIGH-RECALL OPPORTUNITY INDICATORS
            # Broad opportunity detection patterns (optimized for recall over precision)
            broad_opportunity_patterns = [
                "opportunity", "position", "role", "opening", "vacancy", "hiring",
                "recruiting", "talent", "candidate", "application", "apply now",
                "join us", "we're hiring", "team member", "looking for", "seeking",
                "deadline", "due date", "applications close", "limited time",
                "notification", "announcement", "update", "news", "launch",
                "available", "accepting", "registration", "sign up", "interested"
            ]
            profile_parts.append("Broad opportunity patterns: " + " ".join(broad_opportunity_patterns))
            
            # Combine all parts with strategic weighting (duplicate high-priority sections)
            profile_text_components = [
                # Core interests weighted heavily (3x for maximum relevance)
                profile_parts[0], profile_parts[0], profile_parts[0],
                # Research opportunities weighted heavily (3x) 
                profile_parts[1], profile_parts[1], profile_parts[1],
                # News & industry intelligence weighted moderately (2x for trend awareness)
                profile_parts[3], profile_parts[3],
                # Funding & grant intelligence weighted heavily (2x for high-value opportunities)
                profile_parts[8], profile_parts[8],
                # Conference & event intelligence weighted moderately (2x for networking value)
                profile_parts[7], profile_parts[7],
                # All other components once
                *profile_parts[2:3], *profile_parts[4:7], profile_parts[9:],
                # Add weak signal amplification one extra time for better edge case detection
                profile_parts[6]
            ]
            
            profile_text = " ".join(profile_text_components)
            
            self.profile_embedding = self._get_embedding(profile_text)
            self.logger.info(f"Intelligence discovery profile embedding generated: {len(profile_text)} chars, optimized for weak signal detection")
            
        except Exception as e:
            self.logger.error(f"Failed to generate profile embedding: {e}")
            self.profile_embedding = None
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using Together AI."""
        if not self.client or not text.strip():
            return None
        
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text.strip()
            )
            return response.data[0].embedding
            
        except Exception as e:
            self.logger.warning(f"Failed to get embedding: {e}")
            # Return None to skip semantic filtering for this email
            return None
    
    def _prepare_email_text(self, email: EmailMessage) -> str:
        """Prepare email text for embedding, focusing on opportunity indicators."""
        # Combine subject and body with priority to subject line
        subject = email.subject or ''
        body = email.body[:1500] if email.body else ''  # Increased body length for more context
        
        # Create weighted text that emphasizes subject and key opportunity indicators
        # Triple weight for subject line (often contains the most important keywords)
        email_text = f"{subject} {subject} {subject} {body}".strip()
        
        # Extract and emphasize any potential deadline or urgency indicators
        urgency_keywords = ['deadline', 'due', 'expires', 'closing', 'last chance', 'final', 'urgent']
        opportunity_keywords = ['fellowship', 'grant', 'position', 'opportunity', 'application', 'apply']
        
        # Add extra weight to emails containing high-value signals
        text_lower = email_text.lower()
        if any(keyword in text_lower for keyword in urgency_keywords + opportunity_keywords):
            # Add the subject line two more times for high-signal emails
            email_text = f"{subject} {subject} {email_text}"
        
        return email_text
    
    def _calculate_similarity(self, email_embedding: List[float]) -> float:
        """Calculate cosine similarity between email and profile embeddings."""
        if not self.profile_embedding or not email_embedding:
            return 0.0
        
        try:
            # Use consolidated similarity function from utils
            from .utils import calculate_cosine_similarity
            return calculate_cosine_similarity(self.profile_embedding, email_embedding)
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate similarity: {e}")
            return 0.0
    
    def is_semantically_relevant(self, email: EmailMessage) -> tuple[bool, float]:
        """
        Check if email is semantically relevant to user profile.
        Uses adaptive thresholding for better weak signal detection.
        
        Returns:
            tuple: (is_relevant, similarity_score)
        """
        # Skip semantic filtering if not properly initialized
        if not self.client or not self.profile_embedding:
            self.logger.debug(f"Semantic filter not available for email {email.uid}, allowing through")
            return True, 1.0
        
        try:
            # Prepare email text
            email_text = self._prepare_email_text(email)
            if not email_text:
                self.logger.debug(f"Empty email text for {email.uid}, rejecting")
                return False, 0.0
            
            # Get email embedding
            email_embedding = self._get_embedding(email_text)
            if not email_embedding:
                self.logger.debug(f"Failed to get embedding for email {email.uid}, allowing through")
                return True, 1.0
            
            # Calculate similarity
            similarity_score = self._calculate_similarity(email_embedding)
            
            # Adaptive threshold based on email characteristics
            adaptive_threshold = self._get_adaptive_threshold(email)
            is_relevant = similarity_score >= adaptive_threshold
            
            self.logger.debug(
                f"Semantic filter for email {email.uid}: "
                f"similarity={similarity_score:.3f}, adaptive_threshold={adaptive_threshold:.3f}, relevant={is_relevant}"
            )
            
            return is_relevant, similarity_score
            
        except Exception as e:
            self.logger.warning(f"Semantic filtering failed for email {email.uid}: {e}")
            # Default to allowing email through if filtering fails
            return True, 1.0
    
    def _get_adaptive_threshold(self, email: EmailMessage) -> float:
        """Get adaptive threshold based on email characteristics for better weak signal detection."""
        base_threshold = self.similarity_threshold
        
        # High-value signals that should lower the threshold (be more permissive)
        high_value_signals = [
            'fellowship', 'grant', 'funding', 'nsf', 'nih', 'darpa', 'research',
            'opportunity', 'position', 'application', 'deadline', 'conference',
            'workshop', 'beta', 'early access', 'invitation', 'exclusive'
        ]
        
        # Check subject line for high-value signals
        subject_lower = (email.subject or '').lower()
        high_value_count = sum(1 for signal in high_value_signals if signal in subject_lower)
        
        # Check sender for academic or research institutions
        sender_lower = (email.sender or '').lower()
        institutional_signals = ['edu', 'gov', 'nsf', 'nih', 'research', 'university', 'institute']
        institutional_count = sum(1 for signal in institutional_signals if signal in sender_lower)
        
        # Adjust threshold based on signals
        threshold_adjustment = 0.0
        
        # Lower threshold for high-value signals (more permissive)
        if high_value_count > 0:
            threshold_adjustment -= 0.05 * high_value_count  # Lower by 0.05 per signal
        
        # Lower threshold for institutional senders
        if institutional_count > 0:
            threshold_adjustment -= 0.03 * institutional_count  # Lower by 0.03 per institutional signal
        
        # Cap the adjustment to prevent threshold from going too low or high
        threshold_adjustment = max(-0.15, min(0.05, threshold_adjustment))
        
        adaptive_threshold = base_threshold + threshold_adjustment
        
        # Ensure threshold stays within reasonable bounds
        adaptive_threshold = max(0.1, min(0.4, adaptive_threshold))
        
        return adaptive_threshold
    
    def _is_sender_whitelisted(self, email: EmailMessage) -> bool:
        """Check if email sender is in the whitelist."""
        if not self.sender_whitelist:
            return False
        
        sender = email.sender or ''
        sender_lower = sender.lower()
        
        for whitelisted_sender in self.sender_whitelist:
            if whitelisted_sender.lower() in sender_lower:
                return True
        
        return False
    
    def _is_sender_blacklisted(self, email: EmailMessage) -> bool:
        """Check if email sender is in the blacklist."""
        if not self.sender_blacklist:
            return False
        
        sender = email.sender or ''
        sender_lower = sender.lower()
        
        for blacklisted_sender in self.sender_blacklist:
            if blacklisted_sender.lower() in sender_lower:
                return True
        
        return False

    def filter_emails_batch(self, emails: List[EmailMessage]) -> List[EmailMessage]:
        """Filter a batch of emails using sender whitelist/blacklist and semantic similarity."""
        if not emails:
            return []
        
        # Step 1: Apply sender whitelist/blacklist filtering FIRST
        pre_filtered_emails = []
        whitelisted_count = 0
        blacklisted_count = 0
        
        for email in emails:
            # Check blacklist first - immediate rejection
            if self._is_sender_blacklisted(email):
                blacklisted_count += 1
                self.logger.debug(f"Email {email.uid} from {email.sender} BLACKLISTED - rejected")
                continue
            
            # Check whitelist - bypass semantic filtering
            if self._is_sender_whitelisted(email):
                whitelisted_count += 1
                pre_filtered_emails.append(email)
                self.logger.debug(f"Email {email.uid} from {email.sender} WHITELISTED - bypassing semantic filter")
                continue
            
            # Not whitelisted or blacklisted - add to semantic filtering queue
            pre_filtered_emails.append(email)
        
        # Log whitelist/blacklist statistics
        if whitelisted_count > 0 or blacklisted_count > 0:
            self.logger.info(
                f"Sender filtering: {whitelisted_count} whitelisted, {blacklisted_count} blacklisted, "
                f"{len(pre_filtered_emails) - whitelisted_count} for semantic analysis"
            )
        
        # Step 2: Apply semantic filtering only to non-whitelisted emails
        if not self.client or not self.profile_embedding:
            self.logger.info("Semantic filter not available, returning sender-filtered emails")
            return pre_filtered_emails
        
        # Separate whitelisted emails from those needing semantic filtering
        whitelisted_emails = []
        emails_for_semantic_filtering = []
        
        for email in pre_filtered_emails:
            if self._is_sender_whitelisted(email):
                whitelisted_emails.append(email)
            else:
                emails_for_semantic_filtering.append(email)
        
        # Apply semantic filtering to non-whitelisted emails
        semantically_filtered_emails = []
        similarity_scores = []
        adaptive_thresholds = []
        
        if emails_for_semantic_filtering:
            self.logger.info(f"Starting semantic filtering of {len(emails_for_semantic_filtering)} emails (excluding {len(whitelisted_emails)} whitelisted)")
            
            for email in emails_for_semantic_filtering:
                is_relevant, similarity_score = self.is_semantically_relevant(email)
                adaptive_threshold = self._get_adaptive_threshold(email)
                
                similarity_scores.append(similarity_score)
                adaptive_thresholds.append(adaptive_threshold)
                
                if is_relevant:
                    semantically_filtered_emails.append(email)
                    self.logger.debug(f"Email {email.uid} passed semantic filter (score: {similarity_score:.3f}, threshold: {adaptive_threshold:.3f})")
                else:
                    self.logger.debug(f"Email {email.uid} rejected by semantic filter (score: {similarity_score:.3f}, threshold: {adaptive_threshold:.3f})")
        
        # Combine whitelisted emails with semantically filtered emails
        final_filtered_emails = whitelisted_emails + semantically_filtered_emails
        
        # Log comprehensive statistics
        total_emails = len(emails)
        final_count = len(final_filtered_emails)
        
        if similarity_scores:
            avg_score = sum(similarity_scores) / len(similarity_scores)
            max_score = max(similarity_scores)
            min_score = min(similarity_scores)
            avg_threshold = sum(adaptive_thresholds) / len(adaptive_thresholds)
            min_threshold = min(adaptive_thresholds)
            max_threshold = max(adaptive_thresholds)
            
            self.logger.info(
                f"Similarity scores - avg: {avg_score:.3f}, min: {min_score:.3f}, max: {max_score:.3f}"
            )
            self.logger.info(
                f"Adaptive thresholds - avg: {avg_threshold:.3f}, min: {min_threshold:.3f}, max: {max_threshold:.3f}, "
                f"base: {self.similarity_threshold}"
            )
        
        self.logger.info(
            f"Complete filtering: {final_count}/{total_emails} emails passed "
            f"({final_count/total_emails*100:.1f}% pass rate) - "
            f"{whitelisted_count} whitelisted, {len(semantically_filtered_emails)} semantic, {blacklisted_count} blacklisted"
        )
        
        return final_filtered_emails
    
    def get_filter_stats(self) -> dict:
        """Get semantic filter statistics."""
        return {
            "enabled": self.client is not None and self.profile_embedding is not None,
            "model": self.embedding_model,
            "threshold": self.similarity_threshold,
            "profile_embedding_size": len(self.profile_embedding) if self.profile_embedding else 0,
            "whitelist_count": len(self.sender_whitelist),
            "blacklist_count": len(self.sender_blacklist),
            "whitelist_senders": self.sender_whitelist.copy() if self.sender_whitelist else [],
            "blacklist_senders": self.sender_blacklist.copy() if self.sender_blacklist else []
        }
