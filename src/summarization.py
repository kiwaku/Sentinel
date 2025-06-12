"""
Email summarization and report generation module.
"""

import logging
import smtplib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from .utils import ConfigManager, EmailOpportunity


class SentinelReportGenerator:
    """Enhanced report generator for Sentinel v1.4 with recall-focused link filtering."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # v1.4 Link Filtering: Prioritize recall over precision
        # Focus on keeping ALL potentially useful links while filtering only obvious footer noise
        
        # Actionable anchor text patterns - keep these regardless of URL structure
        self.actionable_anchor_patterns = [
            r'apply', r'register', r'sign\s+up', r'enroll', r'join',
            r'learn\s+more', r'get\s+started', r'details', r'information',
            r'view\s+course', r'course\s+page', r'program\s+info',
            r'official\s+site', r'explore', r'discover', r'find\s+out',
            r'register\s+now', r'apply\s+now', r'submit', r'participate',
            r'access', r'portal', r'dashboard', r'platform', r'website',
            r'read\s+article', r'full\s+article', r'continue\s+reading',
            r'download', r'form', r'requirements', r'guidelines',
            # News and content patterns
            r'read\s+more', r'view\s+online', r'full\s+story', r'see\s+more',
            r'minute\s+read', r'view\s+article', r'read\s+now', r'learn\s+about',
            r'blog\s+post', r'news\s+article', r'press\s+release', r'announcement',
            r'industry\s+insight', r'expert\s+analysis', r'research\s+findings',
            r'company\s+blog', r'tech\s+news', r'latest\s+update'
        ]
        
        # Hard footer boilerplate patterns - only filter these obvious non-actionable links
        self.hard_footer_patterns = [
            r'^unsubscribe$', r'^manage\s+preferences$', r'^privacy\s+policy$',
            r'^terms\s+of\s+service$', r'^terms\s+and\s+conditions$',
            r'^help$', r'^support$', r'^contact\s+us$',
            r'^follow\s+us$', r'^social\s+media$', r'^facebook$', r'^twitter$',
            r'^linkedin$', r'^instagram$', r'^youtube$',
            r'^update\s+profile$', r'^email\s+preferences$'
        ]
        
        # Completely useless anchor text patterns - filter these but be very conservative
        self.useless_anchor_patterns = [
            r'^$', r'^\s*$',  # Empty or whitespace-only
            r'^https?://', r'^www\.', r'^\.\.\.$', r'^…$',  # Raw URLs or dots
            r'^click\s+here$', r'^here$', r'^link$'  # Only the most generic
        ]
    
    def generate_daily_discovery_report(self, opportunities: Dict[str, List[EmailOpportunity]], 
                                      processing_stats: Dict = None) -> str:
        """Generate the enhanced Sentinel v1.3 daily discovery report."""
        high_priority = opportunities.get('high_priority', [])
        exploratory = opportunities.get('exploratory', [])
        
        # Limit opportunities as configured
        max_high_priority = self.config.get('summary.max_high_priority', 10)
        max_exploratory = self.config.get('summary.max_exploratory', 15)
        
        high_priority = high_priority[:max_high_priority]
        exploratory = exploratory[:max_exploratory]
        
        # Build report sections
        report_lines = []
        
        # Header
        report_lines.extend(self._generate_header(high_priority, exploratory, processing_stats))
        
        # High Priority Section
        report_lines.extend(self._generate_high_priority_section(high_priority))
        
        # Exploratory Discoveries Section
        report_lines.extend(self._generate_exploratory_section(exploratory))
        
        # Footer
        report_lines.extend(self._generate_footer())
        
        return '\n'.join(report_lines)
    
    def _generate_header(self, high_priority: List[EmailOpportunity], 
                        exploratory: List[EmailOpportunity], processing_stats: Dict = None) -> List[str]:
        """Generate the report header with processing statistics."""
        today = datetime.now().strftime('%B %d, %Y')
        total_opportunities = len(high_priority) + len(exploratory)
        
        # Calculate scan period from opportunities
        scan_period_text = self._calculate_scan_period(high_priority + exploratory)
        
        # Default processing stats if not provided
        emails_processed = processing_stats.get('emails_processed', 'N/A') if processing_stats else 'N/A'
        
        return [
            f"🛡️ SENTINEL DAILY DISCOVERY REPORT — {today}",
            "",
            f"📅 {scan_period_text}",
            f"📊 Emails Processed: {emails_processed} | Opportunities Extracted: {total_opportunities} | Engine: Sentinel v1.4",
            "------------------------------------------------------------",
            ""
        ]
    
    def _generate_high_priority_section(self, high_priority: List[EmailOpportunity]) -> List[str]:
        """Generate the high priority opportunities section."""
        lines = ["🔥 High Priority (Immediate Action Recommended)", ""]
        
        if not high_priority:
            lines.extend([
                "(No high priority opportunities found today.)",
                "------------------------------------------------------------",
                ""
            ])
        else:
            for opp in high_priority:
                lines.extend(self._format_priority_opportunity(opp))
                lines.extend(["------------------------------------------------------------", ""])
        
        return lines
    
    def _generate_exploratory_section(self, exploratory: List[EmailOpportunity]) -> List[str]:
        """Generate the exploratory discoveries section."""
        lines = ["🔎 Exploratory Discoveries", ""]
        
        if not exploratory:
            lines.extend([
                "(No exploratory opportunities found today.)",
                "------------------------------------------------------------",
                ""
            ])
        else:
            for opp in exploratory:
                lines.extend(self._format_exploratory_opportunity(opp))
                lines.extend(["------------------------------------------------------------", ""])
        
        return lines
    
    def _format_priority_opportunity(self, opp: EmailOpportunity) -> List[str]:
        """Format a high priority opportunity with enhanced presentation."""
        score_percentage = f"{opp.priority_score * 100:.0f}%" if opp.priority_score else "N/A"
        
        # Format email date for debugging
        email_date_str = ""
        if hasattr(opp, 'email_date') and opp.email_date:
            try:
                if isinstance(opp.email_date, str):
                    from datetime import datetime
                    email_date = datetime.fromisoformat(opp.email_date.replace('Z', '+00:00'))
                else:
                    email_date = opp.email_date
                email_date_str = f"- 📧 Email Date: {email_date.strftime('%Y-%m-%d %H:%M')}"
            except:
                email_date_str = f"- 📧 Email Date: {opp.email_date}"
        
        lines = [
            f"### 🚨 {opp.title}",
            "",
            f"- Organization: {opp.organization}",
            f"- Type: {opp.opportunity_type}",
            f"- Location: {opp.location}",
            f"- 🗓 Deadline: {opp.deadlines if opp.deadlines and opp.deadlines != 'Not specified' else '❌ Not provided'}",
            f"- 🔬 Relevance Score: {score_percentage}",
        ]
        
        # Add email date if available
        if email_date_str:
            lines.append(email_date_str)
        
        lines.append("")
        
        # Add summary
        if opp.notes:
            lines.extend([
                "**Summary:**",
                opp.notes,
                ""
            ])
        
        # Add filtered resources using enhanced scoring
        resources = self._extract_and_filter_resources_enhanced(opp)
        if resources:
            lines.extend(["**Resources:**"])
            for anchor_text, url in resources:
                lines.append(f"- [{url}]({url})")
            lines.append("")
        
        # Add Gmail source link
        gmail_link = self._generate_gmail_source_link(opp)
        if gmail_link:
            lines.extend([
                "**View Original Email:**",
                f"- [View in Gmail]({gmail_link})",
                ""
            ])
        
        return lines
    
    def _format_exploratory_opportunity(self, opp: EmailOpportunity) -> List[str]:
        """Format an exploratory opportunity with clean presentation."""
        score_percentage = f"{opp.priority_score * 100:.0f}%" if opp.priority_score else "N/A"
        
        # Format email date for debugging
        email_date_str = ""
        if hasattr(opp, 'email_date') and opp.email_date:
            try:
                if isinstance(opp.email_date, str):
                    from datetime import datetime
                    email_date = datetime.fromisoformat(opp.email_date.replace('Z', '+00:00'))
                else:
                    email_date = opp.email_date
                email_date_str = f"- 📧 Email Date: {email_date.strftime('%Y-%m-%d %H:%M')}"
            except:
                email_date_str = f"- 📧 Email Date: {opp.email_date}"
        
        lines = [
            f"### 🎯 {opp.title}",
            "",
            f"- Organization: {opp.organization}",
            f"- Type: {opp.opportunity_type}",
            f"- Location: {opp.location}",
            f"- 🗓 Deadline: {opp.deadlines if opp.deadlines and opp.deadlines != 'Not specified' else '❌ Not provided'}",
            f"- 🔬 Relevance Score: {score_percentage}",
        ]
        
        # Add email date if available
        if email_date_str:
            lines.append(email_date_str)
        
        lines.append("")
        
        # Add summary
        if opp.notes:
            summary = opp.notes[:300] + "..." if len(opp.notes) > 300 else opp.notes
            lines.extend([
                "**Summary:**",
                summary,
                ""
            ])
        
        # Add filtered resources using enhanced scoring
        resources = self._extract_and_filter_resources_enhanced(opp)
        if resources:
            lines.extend(["**Resources:**"])
            for anchor_text, url in resources:
                lines.append(f"- [{url}]({url})")
            lines.append("")
        
        # Add Gmail source link
        gmail_link = self._generate_gmail_source_link(opp)
        if gmail_link:
            lines.extend([
                "**View Original Email:**",
                f"- [View in Gmail]({gmail_link})",
                ""
            ])
        
        return lines
    
    def _extract_and_filter_resources(self, opp: EmailOpportunity) -> List[Tuple[str, str]]:
        """Extract and filter resource links according to filtering rules."""
        resources = []
        seen_urls = set()
        
        # Extract from primary URL
        if opp.primary_url and self._should_keep_url(opp.primary_url):
            anchor_text = self._generate_clean_anchor_text(opp.primary_url, "Apply Here")
            resources.append((anchor_text, opp.primary_url))
            seen_urls.add(opp.primary_url)
        
        # Extract from urls_with_context
        if hasattr(opp, 'urls_with_context') and opp.urls_with_context:
            for link_data in opp.urls_with_context:
                if isinstance(link_data, dict):
                    url = link_data.get('url', '')
                    original_anchor = link_data.get('anchor_text', '')
                    
                    # Check for duplicates BEFORE processing
                    if url and url not in seen_urls and self._should_keep_url(url, original_anchor):
                        clean_anchor = self._generate_clean_anchor_text(url, original_anchor)
                        resources.append((clean_anchor, url))
                        seen_urls.add(url)
        
        # Extract from original_urls if available (but be selective)
        if hasattr(opp, 'original_urls') and opp.original_urls and len(resources) < 3:
            for url in opp.original_urls[:3]:  # Only top 3
                if url and url not in seen_urls and self._should_keep_url(url):
                    clean_anchor = self._generate_clean_anchor_text(url, "View Details")
                    resources.append((clean_anchor, url))
                    seen_urls.add(url)
        
        # Sort by relevance (apply/register links first)
        resources.sort(key=lambda x: (
            0 if any(pattern in x[0].lower() for pattern in ['apply', 'register', 'enroll']) else 1,
            x[0].lower()
        ))
        
        return resources[:4]  # Limit to top 4 resources for better readability
    
    def _should_keep_url(self, url: str, anchor_text: str = "") -> bool:
        """
        Determine if a URL should be kept based on improved filtering rules.
        Strategy: Intelligent precision - keep relevant links while filtering noise.
        """
        url_lower = url.lower()
        anchor_lower = anchor_text.lower() if anchor_text else ""
        
        # Step 1: Always filter out completely useless anchor text
        if anchor_text:
            for pattern in self.useless_anchor_patterns:
                if re.search(pattern, anchor_lower, re.IGNORECASE):
                    return False
        
        # Step 2: Always filter out hard footer boilerplate
        if anchor_text:
            for pattern in self.hard_footer_patterns:
                if re.search(pattern, anchor_lower, re.IGNORECASE):
                    return False
        
        # Step 3: Filter out non-English generic phrases that are likely navigation/UI elements
        if anchor_text and self._is_likely_navigation_text(anchor_text):
            return False
        
        # Step 4: Always keep URLs with actionable anchor text (highest priority)
        if anchor_text:
            for pattern in self.actionable_anchor_patterns:
                if re.search(pattern, anchor_lower, re.IGNORECASE):
                    return True
        
        # Step 5: Analyze URL for opportunity relevance
        if self._is_opportunity_relevant_url(url):
            return True
        
        # Step 6: Filter obvious tracking/newsletter URLs
        obvious_tracking = [
            'unsubscribe', 'email-preferences', 'manage-subscription',
            'privacy-policy', 'terms-of-service', 'utm_', 'tracking',
            'newsletter', 'email-digest', 'marketing'
        ]
        
        for tracking_term in obvious_tracking:
            if tracking_term in url_lower:
                return False
        
        # Step 7: Default decision based on context
        parsed = urlparse(url)
        if parsed.scheme in ['http', 'https'] and parsed.netloc:
            # Keep if anchor text suggests it's relevant, even if we can't parse the language
            if anchor_text and len(anchor_text.strip()) > 5:
                # If anchor text contains opportunity-related keywords in any language
                if self._contains_opportunity_keywords(anchor_text, url):
                    return True
                # Otherwise, be more conservative with non-English text
                if not self._is_likely_english_text(anchor_text):
                    return False
            return True
        
        return False
    
    def _is_likely_navigation_text(self, text: str) -> bool:
        """Check if text appears to be generic navigation/UI elements."""
        text_lower = text.lower().strip()
        
        # Common navigation patterns in multiple languages
        navigation_patterns = [
            # English
            r'^view all$', r'^see more$', r'^read more$', r'^continue$',
            r'^next$', r'^previous$', r'^back$', r'^home$', r'^menu$',
            r'^login$', r'^logout$', r'^profile$', r'^account$',
            r'^all rights reserved$', r'^copyright$', r'^terms$', r'^privacy$',
            
            # Generic UI elements that appear in many languages
            r'^\w{1,3}$',  # Very short text (likely buttons/icons)
            r'^[0-9]+$',   # Just numbers
            r'^[^\w\s]+$', # Only punctuation/symbols
            
            # Japanese navigation/UI patterns (more comprehensive)
            r'を視聴する$',      # "watch/view" suffix
            r'に参加する$',      # "participate in" suffix  
            r'を確認する$',      # "check/verify" suffix
            r'を作成$',         # "create" suffix
            r'に参加$',         # "join" suffix
            r'^アカウント$',     # "account"
            r'^ログイン$',       # "login"
            r'^ホーム$',        # "home"
            r'^メニュー$',       # "menu"
            r'^視聴する$',       # "watch"
            r'^確認する$',       # "check"
            r'^参加する$',       # "participate"
            r'^ビデオを見る$',    # "watch video"
            r'^基調講演$',       # "keynote"
            r'^セッション$',     # "session"
            r'^紹介$',          # "introduction"
            r'^理解$',          # "understanding"
        ]
        
        for pattern in navigation_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _is_opportunity_relevant_url(self, url: str) -> bool:
        """Check if URL path suggests it's opportunity-related or contains interesting content."""
        url_lower = url.lower()
        
        # Traditional opportunity-specific URL patterns
        opportunity_patterns = [
            '/apply', '/application', '/register', '/registration',
            '/enroll', '/enrollment', '/submit', '/nomination',
            '/fellowship', '/scholarship', '/grant', '/funding',
            '/opportunity', '/program', '/course', '/training',
            '/career', '/job', '/position', '/internship',
            '/competition', '/challenge', '/contest',
            '/deadline', '/requirements', '/eligibility'
        ]
        
        # News and content URL patterns
        content_patterns = [
            '/blog', '/news', '/article', '/post', '/press',
            '/announcement', '/release', '/update', '/insight',
            '/research', '/report', '/analysis', '/story'
        ]
        
        for pattern in opportunity_patterns + content_patterns:
            if pattern in url_lower:
                return True
        
        return False
    
    def _contains_opportunity_keywords(self, text: str, url: str) -> bool:
        """Check if text or URL contains opportunity-related keywords or interesting content indicators."""
        combined_text = f"{text} {url}".lower()
        
        # Traditional opportunity keywords
        opportunity_keywords = [
            # English
            'apply', 'application', 'register', 'enroll', 'submit',
            'fellowship', 'scholarship', 'grant', 'opportunity',
            'program', 'course', 'training', 'career', 'job',
            'competition', 'challenge', 'deadline', 'form',
            
            # News and content keywords
            'announces', 'releases', 'launches', 'unveils', 'introduces',
            'breakthrough', 'innovation', 'update', 'news', 'article',
            'minute read', 'blog post', 'press release', 'industry',
            'research findings', 'study', 'report', 'analysis',
            
            # Common in URLs regardless of language
            'apply', 'register', 'enroll', 'program', 'course',
            'opportunity', 'fellowship', 'scholarship', 'job',
            'blog', 'news', 'article', 'post', 'announcement'
        ]
        
        for keyword in opportunity_keywords:
            if keyword in combined_text:
                return True
        
        return False
    
    def _is_likely_english_text(self, text: str) -> bool:
        """Basic heuristic to check if text is likely English."""
        if not text:
            return True
        
        # Simple check: if text contains mostly ASCII characters, likely English
        ascii_chars = sum(1 for char in text if ord(char) < 128)
        total_chars = len(text)
        
        if total_chars == 0:
            return True
        
        ascii_ratio = ascii_chars / total_chars
        return ascii_ratio > 0.8  # 80% ASCII characters suggests English
    
    def _generate_clean_anchor_text(self, url: str, original_anchor: str = "") -> str:
        """Return the raw URL without any anchor text generation or truncation."""
        # Always return the complete URL as-is
        return url
    
    def _generate_footer(self) -> List[str]:
        """Generate the report footer."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return [
            f"🔧 Report generated at: {timestamp}"
        ]
    
    def _calculate_scan_period(self, opportunities: List[EmailOpportunity]) -> str:
        """Calculate and format the scan period from opportunities."""
        from datetime import timedelta
        
        if not opportunities:
            # Default to last 7 days if no opportunities
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            return f"Scan Period: {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')} (7 days)"
        
        # Find date range from actual opportunities
        email_dates = []
        for opp in opportunities:
            if hasattr(opp, 'email_date') and opp.email_date:
                try:
                    if isinstance(opp.email_date, str):
                        date = datetime.fromisoformat(opp.email_date.replace('Z', '+00:00'))
                    else:
                        date = opp.email_date
                    email_dates.append(date)
                except:
                    continue
        
        if email_dates:
            start_date = min(email_dates)
            end_date = max(email_dates)
            days_span = (end_date - start_date).days + 1
            
            if start_date.strftime('%Y') == end_date.strftime('%Y'):
                if start_date.strftime('%B') == end_date.strftime('%B'):
                    # Same month and year
                    return f"Scan Period: {start_date.strftime('%B %d')} - {end_date.strftime('%d, %Y')} ({days_span} days)"
                else:
                    # Same year, different months
                    return f"Scan Period: {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')} ({days_span} days)"
            else:
                # Different years
                return f"Scan Period: {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')} ({days_span} days)"
        else:
            # Fallback if no valid dates found
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            return f"Scan Period: {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')} (7 days)"
    
    def _generate_gmail_source_link(self, opp: EmailOpportunity) -> str:
        """Generate Gmail source link for the original email."""
        if hasattr(opp, 'email_headers') and opp.email_headers and opp.email_headers.get('message_id'):
            try:
                message_id = opp.email_headers['message_id'].strip('<>')
                return f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
            except:
                return ""
        return ""
    
    def _calculate_url_relevance(self, url: str, anchor_text: str, context: str, opportunity) -> int:
        """
        Calculate URL relevance score (0-10) for intelligent filtering.
        This is the core intelligence for reducing URL noise.
        """
        score = 0
        
        # Normalize text for analysis
        url_lower = url.lower()
        anchor_lower = anchor_text.lower()
        context_lower = context.lower()
        combined_text = f"{anchor_lower} {context_lower}"
        
        # 1. High-value action words in anchor text (most important)
        high_value_actions = [
            'apply', 'application', 'submit', 'register', 'enroll', 'nomination',
            'proposal', 'deadline', 'form', 'portal', 'fellowship', 'grant',
            'registration', 'signup', 'sign up', 'join', 'participate'
        ]
        for action in high_value_actions:
            if action in anchor_lower:
                score += 3
            elif action in context_lower:
                score += 1
        
        # 2. Domain authority scoring
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower()
            if any(tld in domain for tld in ['.edu', '.gov']):  # Educational/government
                score += 2
            elif '.org' in domain:  # Non-profit organizations
                score += 1
        except:
            pass  # Skip if URL parsing fails
        
        # 3. File type and form indicators
        if any(ext in url_lower for ext in ['.pdf', '/form', '/application', '/apply']):
            score += 2
        
        # 4. Content type matching with opportunity
        opp_type = opportunity.opportunity_type.lower()
        if opp_type in combined_text:
            score += 1
        
        # 5. Organization name matching
        org_words = opportunity.organization.lower().split()
        for word in org_words:
            if len(word) > 3 and word in combined_text:  # Skip short words like "Inc"
                score += 1
        
        # 6. Medium priority keywords
        medium_priority_keywords = [
            'details', 'information', 'more info', 'learn more', 'about',
            'program', 'opportunity', 'conference', 'event', 'course'
        ]
        for keyword in medium_priority_keywords:
            if keyword in anchor_lower:
                score += 2
            elif keyword in context_lower:
                score += 1
        
        # 7. Penalties for irrelevant content
        penalty_patterns = [
            'unsubscribe', 'privacy', 'terms', 'cookie', 'facebook', 'twitter',
            'linkedin', 'instagram', 'youtube', 'social', 'share', 'follow',
            'advertise', 'sponsor', 'promotion', 'discount'
        ]
        for pattern in penalty_patterns:
            if pattern in combined_text:
                score -= 3
        
        # 8. Generic link penalties
        generic_anchors = ['click here', 'read more', 'here', 'link', 'view', 'see more']
        if any(generic in anchor_lower for generic in generic_anchors):
            score -= 1
        
        # 9. Empty or very short anchor text penalty
        if len(anchor_text.strip()) < 3:
            score -= 2
        
        return max(0, min(10, score))  # Clamp between 0 and 10

    def _extract_and_filter_resources_enhanced(self, opp: EmailOpportunity) -> List[Tuple[str, str]]:
        """Extract and filter resource links using enhanced relevance scoring."""
        resources = []
        seen_urls = set()
        
        # Extract from primary URL
        if opp.primary_url and opp.primary_url not in seen_urls:
            anchor_text = self._generate_clean_anchor_text(opp.primary_url, "Apply Here")
            resources.append((anchor_text, opp.primary_url))
            seen_urls.add(opp.primary_url)
        
        # Extract from urls_with_context using enhanced scoring
        if hasattr(opp, 'urls_with_context') and opp.urls_with_context:
            url_scores = []
            for link_data in opp.urls_with_context:
                if isinstance(link_data, dict):
                    url = link_data.get('url', '')
                    anchor_text = link_data.get('anchor_text', '')
                    context = link_data.get('context', '')
                    
                    if url and url not in seen_urls:
                        # Use the same scoring algorithm as EmailSummaryService
                        score = self._calculate_url_relevance(url, anchor_text, context, opp)
                        url_scores.append((score, url, anchor_text))
            
            # Sort by relevance and take top scoring URLs
            url_scores.sort(reverse=True)
            relevant_urls = [(url, anchor if anchor else self._generate_clean_anchor_text(url)) 
                           for score, url, anchor in url_scores if score >= 4][:2]  # Top 2
            
            for url, anchor in relevant_urls:
                if url not in seen_urls:
                    resources.append((anchor, url))
                    seen_urls.add(url)
        
        return resources


class EmailSummaryService:
    """Service for generating and sending email summaries with enhanced Sentinel v1.3 formatting."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.report_generator = SentinelReportGenerator(config_manager)

    def _calculate_url_relevance(self, url: str, anchor_text: str, context: str, opportunity) -> int:
        """
        Calculate URL relevance score (0-10) for intelligent filtering.
        Delegates to the SentinelReportGenerator to avoid code duplication.
        """
        return self.report_generator._calculate_url_relevance(url, anchor_text, context, opportunity)

    def generate_daily_summary(self, opportunities: Dict[str, List[EmailOpportunity]], 
                             processing_stats: Dict = None) -> Dict[str, str]:
        """Generate daily summary email content with enhanced v1.3 formatting."""
        high_priority = opportunities.get('high_priority', [])
        exploratory = opportunities.get('exploratory', [])
        
        # Generate subject
        total_count = len(high_priority) + len(exploratory)
        subject = f"🛡️ Sentinel Daily Discovery — {total_count} Opportunities ({datetime.now().strftime('%Y-%m-%d')})"
        
        # Generate enhanced text content
        text_content = self.report_generator.generate_daily_discovery_report(opportunities, processing_stats)
        
        # Generate HTML content (convert markdown-style to HTML)
        html_content = self._convert_text_to_html(text_content)
        
        return {
            'subject': subject,
            'text': text_content,
            'html': html_content
        }
    
    def _convert_text_to_html(self, text_content: str) -> str:
        """Convert the markdown-style text content to HTML for email."""
        html_lines = []
        lines = text_content.split('\n')
        
        html_lines.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Sentinel Daily Discovery Report</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
                .stats { font-size: 14px; opacity: 0.9; }
                .section { margin-bottom: 30px; }
                .section-title { font-size: 24px; color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }
                .opportunity { background: #f8f9fa; border-left: 4px solid #3498db; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
                .high-priority { border-left-color: #e74c3c; background: #fef9f9; }
                .opportunity h3 { margin-top: 0; color: #2c3e50; }
                .meta-list { list-style: none; padding: 0; margin: 15px 0; }
                .meta-list li { padding: 5px 0; }
                .summary { font-style: italic; color: #555; margin: 15px 0; padding: 15px; background: #ecf0f1; border-radius: 5px; }
                .resources { margin: 15px 0; }
                .resources ul { list-style: none; padding: 0; }
                .resources li { padding: 8px 0; }
                .resources a { color: #3498db; text-decoration: none; font-weight: 500; }
                .resources a:hover { text-decoration: underline; }
                .separator { border: none; border-top: 2px solid #bdc3c7; margin: 20px 0; }
                .footer { text-align: center; margin-top: 40px; padding: 20px; background: #ecf0f1; border-radius: 5px; color: #7f8c8d; }
                .no-opportunities { text-align: center; color: #7f8c8d; font-style: italic; padding: 30px; background: #f8f9fa; border-radius: 5px; }
            </style>
        </head>
        <body>
        """)
        
        in_opportunity = False
        in_resources = False
        current_opportunity_class = ""
        
        for line in lines:
            line = line.strip()
            
            # Header section
            if line.startswith("🛡️ SENTINEL DAILY DISCOVERY REPORT"):
                html_lines.append(f'<div class="header"><h1>{line}</h1></div>')
            elif line.startswith("📅 Scan Period"):
                html_lines.append(f'<div class="stats">{line}</div>')
            elif line.startswith("📊 Emails Processed"):
                html_lines.append(f'<div class="stats">{line}</div>')
            
            # Section titles
            elif line.startswith("🔥 High Priority"):
                html_lines.append('<div class="section"><h2 class="section-title">🔥 High Priority (Immediate Action Recommended)</h2>')
            elif line.startswith("🔎 Exploratory Discoveries"):
                html_lines.append('<div class="section"><h2 class="section-title">🔎 Exploratory Discoveries</h2>')
            
            # Opportunities
            elif line.startswith("### 🚨"):
                if in_opportunity:
                    html_lines.append('</div>')
                current_opportunity_class = "opportunity high-priority"
                title = line.replace("### 🚨 ", "")
                html_lines.append(f'<div class="{current_opportunity_class}"><h3>🚨 {title}</h3>')
                html_lines.append('<ul class="meta-list">')
                in_opportunity = True
            elif line.startswith("### 🎯"):
                if in_opportunity:
                    html_lines.append('</div>')
                current_opportunity_class = "opportunity"
                title = line.replace("### 🎯 ", "")
                html_lines.append(f'<div class="{current_opportunity_class}"><h3>🎯 {title}</h3>')
                html_lines.append('<ul class="meta-list">')
                in_opportunity = True
            
            # Metadata
            elif line.startswith("- ") and in_opportunity and not in_resources:
                html_lines.append(f'<li>{line[2:]}</li>')
            
            # Summary
            elif line == "**Summary:**":
                html_lines.append('</ul><div class="summary">')
            elif line == "**Resources:**":
                html_lines.append('</div><div class="resources"><strong>Resources:</strong><ul>')
                in_resources = True
            elif line == "**View Original Email:**":
                html_lines.append('</div><div class="resources"><strong>View Original Email:</strong><ul>')
                in_resources = True
            
            # Resource links
            elif line.startswith("- [") and in_resources:
                # Convert markdown link to HTML, using raw URL as display text
                import re
                match = re.match(r'- \[(.*?)\]\((.*?)\)', line)
                if match:
                    anchor_text, url = match.groups()
                    html_lines.append(f'<li><a href="{url}" target="_blank">{url}</a></li>')
            
            # Separators
            elif line.startswith("----"):
                if in_resources:
                    html_lines.append('</ul></div>')
                    in_resources = False
                if in_opportunity:
                    html_lines.append('</div>')
                    in_opportunity = False
                html_lines.append('<hr class="separator">')
            
            # No opportunities messages
            elif "(No high priority opportunities found today.)" in line:
                html_lines.append('<div class="no-opportunities">No high priority opportunities found today.</div>')
            elif "(No exploratory opportunities found today.)" in line:
                html_lines.append('<div class="no-opportunities">No exploratory opportunities found today.</div>')
            
            # Footer
            elif line.startswith("🔧 Report generated at"):
                html_lines.append(f'<div class="footer"><p>{line}</p></div>')
            
            # Regular text (summary content)
            elif line and not line.startswith("🛡️") and not line.startswith("📊") and line != "**Summary:**" and line != "**Resources:**":
                if in_opportunity and not in_resources and not line.startswith("- "):
                    html_lines.append(f'<p>{line}</p>')
        
        # Close any open tags
        if in_resources:
            html_lines.append('</ul></div>')
        if in_opportunity:
            html_lines.append('</div>')
        
        html_lines.append('</div></body></html>')
        
        return '\n'.join(html_lines)
        lines = []
        
        # Header
        lines.append("SENTINEL DAILY OPPORTUNITY REPORT")
        lines.append("=" * 50)
        lines.append(f"Report Date: {datetime.now().strftime('%B %d, %Y')}")
        lines.append(f"Total Opportunities: {len(high_priority) + len(exploratory)}")
        lines.append("")
        
        # High Priority Section
        if high_priority:
            lines.append("🔥 HIGH PRIORITY OPPORTUNITIES")
            lines.append("-" * 30)
            
            for i, opp in enumerate(high_priority, 1):
                lines.append(f"{i}. {opp.title}")
                lines.append(f"   Organization: {opp.organization}")
                lines.append(f"   Type: {opp.opportunity_type}")
                lines.append(f"   Location: {opp.location}")
                lines.append(f"   Deadlines: {opp.deadlines}")
                lines.append(f"   Priority Score: {opp.priority_score:.2f}")
                
                # Add primary URL
                if opp.primary_url:
                    lines.append(f"   🔗 Apply: {opp.primary_url}")
                
                # Add contact information
                if opp.mailto_addresses:
                    contacts = []
                    for contact in opp.mailto_addresses:
                        if isinstance(contact, dict):
                            contacts.append(contact.get('email', contact))
                        else:
                            contacts.append(contact)
                    if contacts:
                        lines.append(f"   📧 Contact: {', '.join(contacts)}")
                
                if opp.notes:
                    lines.append(f"   Notes: {opp.notes[:200]}{'...' if len(opp.notes) > 200 else ''}")
                lines.append("")
        else:
            lines.append("🔥 HIGH PRIORITY OPPORTUNITIES")
            lines.append("-" * 30)
            lines.append("No high priority opportunities found today.")
            lines.append("")
        
        # Exploratory Section
        if exploratory:
            lines.append("🔍 EXPLORATORY OPPORTUNITIES")
            lines.append("-" * 30)
            
            for i, opp in enumerate(exploratory, 1):
                lines.append(f"{i}. {opp.title}")
                lines.append(f"   Organization: {opp.organization}")
                lines.append(f"   Type: {opp.opportunity_type}")
                lines.append(f"   Location: {opp.location}")
                lines.append(f"   Priority Score: {opp.priority_score:.2f}")
                
                # Add primary URL
                if opp.primary_url:
                    lines.append(f"   🔗 Apply: {opp.primary_url}")
                
                lines.append("")
        else:
            lines.append("🔍 EXPLORATORY OPPORTUNITIES")
            lines.append("-" * 30)
            lines.append("No exploratory opportunities found today.")
            lines.append("")
        
        # Footer
        lines.append("-" * 50)
        lines.append("Generated by Sentinel Email Opportunity Extraction System")
        lines.append(f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    def _generate_html_summary(self, high_priority: List[EmailOpportunity], exploratory: List[EmailOpportunity]) -> str:
        """Generate HTML summary."""
        html_parts = []
        
        # CSS styles
        styles = """
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 30px; }
            .header h1 { margin: 0; font-size: 24px; }
            .header .date { font-size: 16px; opacity: 0.9; margin-top: 5px; }
            .section { margin-bottom: 30px; }
            .section-title { font-size: 20px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 20px; }
            .opportunity { background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
            .high-priority { border-left-color: #e74c3c; }
            .opportunity-title { font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 8px; }
            .opportunity-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
            .meta-item { font-size: 14px; }
            .meta-label { font-weight: bold; color: #34495e; }
            .priority-score { background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; display: inline-block; }
            .high-priority-score { background: #e74c3c; }
            .notes { font-style: italic; color: #555; margin-top: 10px; padding: 10px; background: #ecf0f1; border-radius: 3px; }
            .primary-link { color: #e74c3c; font-weight: bold; text-decoration: none; }
            .primary-link:hover { text-decoration: underline; }
            a { color: #3498db; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .footer { text-align: center; margin-top: 40px; padding: 20px; background: #ecf0f1; border-radius: 5px; color: #7f8c8d; }
            .no-opportunities { text-align: center; color: #7f8c8d; font-style: italic; padding: 20px; }
        </style>
        """
        
        # HTML structure
        html_parts.append(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Sentinel Daily Report</title>
            {styles}
        </head>
        <body>
            <div class="header">
                <h1>🛡️ SENTINEL DAILY REPORT</h1>
                <div class="date">{datetime.now().strftime('%B %d, %Y')}</div>
                <div>Total Opportunities: {len(high_priority) + len(exploratory)}</div>
            </div>
        """)
        
        # High Priority Section
        html_parts.append('<div class="section">')
        html_parts.append('<h2 class="section-title">🔥 High Priority Opportunities</h2>')
        
        if high_priority:
            for opp in high_priority:
                html_parts.append(self._format_opportunity_html(opp, is_high_priority=True))
        else:
            html_parts.append('<div class="no-opportunities">No high priority opportunities found today.</div>')
        
        html_parts.append('</div>')
        
        # Exploratory Section
        html_parts.append('<div class="section">')
        html_parts.append('<h2 class="section-title">🔍 Exploratory Opportunities</h2>')
        
        if exploratory:
            for opp in exploratory:
                html_parts.append(self._format_opportunity_html(opp, is_high_priority=False))
        else:
            html_parts.append('<div class="no-opportunities">No exploratory opportunities found today.</div>')
        
        html_parts.append('</div>')
        
        # Footer
        html_parts.append(f"""
            <div class="footer">
                <p>Generated by Sentinel Email Opportunity Extraction System</p>
                <p>Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """)
        
        return "\n".join(html_parts)
    
    def _format_opportunity_html(self, opp: EmailOpportunity, is_high_priority: bool = False) -> str:
        """Format a single opportunity as HTML."""
        priority_class = "high-priority" if is_high_priority else ""
        score_class = "high-priority-score" if is_high_priority else ""
        
        html = f"""
        <div class="opportunity {priority_class}">
            <div class="opportunity-title">{opp.title}</div>
            <div class="opportunity-meta">
                <div class="meta-item">
                    <span class="meta-label">Organization:</span> {opp.organization}
                </div>
                <div class="meta-item">
                    <span class="meta-label">Type:</span> {opp.opportunity_type}
                </div>
                <div class="meta-item">
                    <span class="meta-label">Location:</span> {opp.location}
                </div>
                <div class="meta-item">
                    <span class="meta-label">Score:</span> 
                    <span class="priority-score {score_class}">{opp.priority_score:.2f}</span>
                </div>
            </div>
            <div class="meta-item">
                <span class="meta-label">Deadlines:</span> {opp.deadlines}
            </div>
        """
        
        # Add primary URL if available
        if opp.primary_url:
            html += f"""
            <div class="meta-item">
                <span class="meta-label">🔗 Apply Here:</span> 
                <a href="{opp.primary_url}" target="_blank" class="primary-link">{opp.primary_url}</a>
            </div>
            """
        
        # Add contact emails if available
        if opp.mailto_addresses:
            contacts = []
            for contact in opp.mailto_addresses:
                if isinstance(contact, dict):
                    email = contact.get('email', contact)
                    context = contact.get('context', '')
                    if context:
                        contacts.append(f'<a href="mailto:{email}">{email}</a> ({context})')
                    else:
                        contacts.append(f'<a href="mailto:{email}">{email}</a>')
                else:
                    contacts.append(f'<a href="mailto:{contact}">{contact}</a>')
            
            if contacts:
                html += f"""
                <div class="meta-item">
                    <span class="meta-label">📧 Contact:</span> {', '.join(contacts)}
                </div>
                """
        
        # Add additional links if available - Enhanced with intelligent filtering
        if hasattr(opp, 'urls_with_context') and opp.urls_with_context:
            # Calculate relevance scores for all URLs
            url_scores = []
            for link_data in opp.urls_with_context:
                if isinstance(link_data, dict):
                    url = link_data.get('url', '')
                    anchor_text = link_data.get('anchor_text', url)
                    context = link_data.get('context', '')
                    
                    if url and url != opp.primary_url:  # Don't duplicate primary URL
                        score = self._calculate_url_relevance(url, anchor_text, context, opp)
                        url_scores.append((score, url, anchor_text))
            
            # Sort by relevance (highest first) and take top 2
            url_scores.sort(reverse=True)
            relevant_urls = [(url, anchor) for score, url, anchor in url_scores if score >= 4][:2]
            
            if relevant_urls:
                additional_links = [f'<a href="{url}" target="_blank">{url}</a>' 
                                  for url, anchor in relevant_urls]
                html += f"""
                <div class="meta-item">
                    <span class="meta-label">🔗 Resources:</span> {', '.join(additional_links)}
                </div>
                """
        
        # Add Gmail source link for original email access
        if hasattr(opp, 'email_headers') and opp.email_headers and opp.email_headers.get('message_id'):
            message_id = opp.email_headers['message_id'].strip('<>')
            gmail_search_url = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
            html += f"""
            <div class="meta-item">
                <span class="meta-label">📧 Original Email:</span> 
                <a href="{gmail_search_url}" target="_blank">View in Gmail</a>
            </div>
            """
        
        if opp.notes:
            truncated_notes = opp.notes[:300] + "..." if len(opp.notes) > 300 else opp.notes
            html += f'<div class="notes">{truncated_notes}</div>'
        
        html += "</div>"
        return html
    
    def send_summary_email(self, summary_content: Dict[str, str], recipient: str = None) -> bool:
        """Send the summary email."""
        try:
            email_config = self.config.get('email')
            
            if recipient is None:
                recipient = self.config.get('summary.recipient_email', email_config['username'])
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = summary_content['subject']
            msg['From'] = email_config['username']
            msg['To'] = recipient
            
            # Attach text and HTML parts
            text_part = MIMEText(summary_content['text'], 'plain', 'utf-8')
            html_part = MIMEText(summary_content['html'], 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
            
            self.logger.info(f"Summary email sent successfully to {recipient}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send summary email: {e}")
            return False
    
    def generate_weekly_summary(self, opportunities: List[EmailOpportunity]) -> Dict[str, str]:
        """Generate weekly summary report."""
        # Group opportunities by category and day
        from collections import defaultdict
        
        daily_stats = defaultdict(lambda: {'high_priority': 0, 'exploratory': 0})
        high_priority_opps = []
        exploratory_opps = []
        
        for opp in opportunities:
            day_key = opp.processed_date.strftime('%Y-%m-%d')
            
            if opp.category == 'high_priority':
                daily_stats[day_key]['high_priority'] += 1
                high_priority_opps.append(opp)
            else:
                daily_stats[day_key]['exploratory'] += 1
                exploratory_opps.append(opp)
        
        # Sort by priority score
        high_priority_opps.sort(key=lambda x: x.priority_score, reverse=True)
        exploratory_opps.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Generate subject
        subject = f"Sentinel Weekly Report - {len(opportunities)} Opportunities ({datetime.now().strftime('%Y-W%U')})"
        
        # Generate content
        text_content = self._generate_weekly_text_summary(daily_stats, high_priority_opps[:10], exploratory_opps[:20])
        html_content = self._generate_weekly_html_summary(daily_stats, high_priority_opps[:10], exploratory_opps[:20])
        
        return {
            'subject': subject,
            'text': text_content,
            'html': html_content
        }
    
    def _generate_weekly_text_summary(self, daily_stats: dict, top_high_priority: List[EmailOpportunity], top_exploratory: List[EmailOpportunity]) -> str:
        """Generate weekly plain text summary."""
        lines = []
        
        # Header
        lines.append("SENTINEL WEEKLY OPPORTUNITY REPORT")
        lines.append("=" * 50)
        lines.append(f"Week ending: {datetime.now().strftime('%B %d, %Y')}")
        lines.append("")
        
        # Daily stats
        lines.append("DAILY BREAKDOWN")
        lines.append("-" * 20)
        for day, stats in sorted(daily_stats.items()):
            total = stats['high_priority'] + stats['exploratory']
            lines.append(f"{day}: {total} total ({stats['high_priority']} high priority, {stats['exploratory']} exploratory)")
        lines.append("")
        
        # Top opportunities
        if top_high_priority:
            lines.append("TOP HIGH PRIORITY OPPORTUNITIES")
            lines.append("-" * 30)
            for i, opp in enumerate(top_high_priority, 1):
                lines.append(f"{i}. {opp.title} - {opp.organization} (Score: {opp.priority_score:.2f})")
            lines.append("")
        
        if top_exploratory:
            lines.append("TOP EXPLORATORY OPPORTUNITIES")
            lines.append("-" * 30)
            for i, opp in enumerate(top_exploratory, 1):
                lines.append(f"{i}. {opp.title} - {opp.organization} (Score: {opp.priority_score:.2f})")
            lines.append("")
        
        lines.append("-" * 50)
        lines.append("Generated by Sentinel Email Opportunity Extraction System")
        
        return "\n".join(lines)
    
    def _generate_weekly_html_summary(self, daily_stats: dict, top_high_priority: List[EmailOpportunity], top_exploratory: List[EmailOpportunity]) -> str:
        """Generate weekly HTML summary."""
        # Similar to daily HTML but with weekly stats
        # Implementation would be similar to daily HTML generation
        # but focused on weekly aggregation and top opportunities
        return self._generate_html_summary(top_high_priority, top_exploratory)
    
    def test_email_sending(self) -> bool:
        """Test email sending configuration."""
        try:
            test_content = {
                'subject': 'Sentinel Test Email',
                'text': 'This is a test email from Sentinel to verify email configuration.',
                'html': '<p>This is a test email from <strong>Sentinel</strong> to verify email configuration.</p>'
            }
            
            email_config = self.config.get('email')
            recipient = email_config['username']  # Send to self
            
            return self.send_summary_email(test_content, recipient)
            
        except Exception as e:
            self.logger.error(f"Email test failed: {e}")
            return False