"""
Profile-based filtering and scoring module for extracted opportunities.
"""

import logging
from typing import List, Tuple

from .utils import EmailOpportunity, ProfileManager, calculate_text_similarity


class OpportunityFilteringService:
    """Service for filtering and scoring opportunities based on user profile."""
    
    def __init__(self, profile_manager: ProfileManager):
        self.profile = profile_manager
        self.logger = logging.getLogger(__name__)
    
    def filter_and_score_opportunities(self, opportunities: List[EmailOpportunity]) -> Tuple[List[EmailOpportunity], List[EmailOpportunity]]:
        """Filter opportunities and return high priority and exploratory lists."""
        high_priority = []
        exploratory = []
        
        self.logger.info(f"Filtering and scoring {len(opportunities)} opportunities")
        
        for opportunity in opportunities:
            try:
                # First check if opportunity should be excluded
                if self.profile.should_exclude(opportunity):
                    self.logger.debug(f"Excluding opportunity: {opportunity.title}")
                    continue
                
                # Calculate priority score
                priority_score = self.profile.calculate_priority_score(opportunity)
                opportunity.priority_score = priority_score
                
                # Categorize based on score and content type
                if priority_score >= 0.7:
                    opportunity.category = "high_priority"
                    high_priority.append(opportunity)
                    self.logger.debug(f"High priority opportunity: {opportunity.title} (score: {priority_score:.2f})")
                elif priority_score >= 0.12:  # Lowered from 0.15 to 0.12 for better discovery
                    opportunity.category = "exploratory"
                    exploratory.append(opportunity)
                    self.logger.debug(f"Exploratory opportunity: {opportunity.title} (score: {priority_score:.2f})")
                else:
                    # Special handling for news/content types - more lenient threshold
                    if opportunity.opportunity_type in ['news_with_opportunities', 'interesting_content', 'industry_update']:
                        if priority_score >= 0.08:  # Lowered from 0.10 to 0.08 for interesting content
                            opportunity.category = "exploratory"
                            exploratory.append(opportunity)
                            self.logger.debug(f"Exploratory content: {opportunity.title} (score: {priority_score:.2f}, type: {opportunity.opportunity_type})")
                        else:
                            self.logger.debug(f"Low score content filtered out: {opportunity.title} (score: {priority_score:.2f})")
                    else:
                        self.logger.debug(f"Low score opportunity filtered out: {opportunity.title} (score: {priority_score:.2f})")
                
            except Exception as e:
                self.logger.error(f"Error filtering opportunity {opportunity.uid}: {e}")
                # Default to exploratory on error
                opportunity.category = "exploratory"
                exploratory.append(opportunity)
        
        # Sort by priority score
        high_priority.sort(key=lambda x: x.priority_score, reverse=True)
        exploratory.sort(key=lambda x: x.priority_score, reverse=True)
        
        self.logger.info(f"Filtered to {len(high_priority)} high priority and {len(exploratory)} exploratory opportunities")
        
        return high_priority, exploratory
    
    def apply_advanced_filters(self, opportunities: List[EmailOpportunity]) -> List[EmailOpportunity]:
        """Apply advanced filtering logic."""
        filtered = []
        profile_data = self.profile.load_profile()
        
        for opportunity in opportunities:
            try:
                # Check location preferences
                if not self._check_location_match(opportunity, profile_data):
                    self.logger.debug(f"Location mismatch for: {opportunity.title}")
                    continue
                
                # Check eligibility requirements
                if not self._check_eligibility_match(opportunity, profile_data):
                    self.logger.debug(f"Eligibility mismatch for: {opportunity.title}")
                    continue
                
                # Check deadline urgency
                if not self._check_deadline_relevance(opportunity, profile_data):
                    self.logger.debug(f"Deadline not relevant for: {opportunity.title}")
                    continue
                
                filtered.append(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error in advanced filtering for {opportunity.uid}: {e}")
                # Include opportunity if filtering fails (conservative approach)
                filtered.append(opportunity)
        
        return filtered
    
    def _check_location_match(self, opportunity: EmailOpportunity, profile_data: dict) -> bool:
        """Check if opportunity location matches preferences."""
        preferred_locations = [loc.lower() for loc in profile_data.get('preferred_locations', [])]
        
        if not preferred_locations:
            return True  # No location preference means accept all
        
        location_text = opportunity.location.lower()
        
        # Check for direct matches
        for preferred_loc in preferred_locations:
            if preferred_loc in location_text:
                return True
        
        # Special handling for remote/virtual
        if any(keyword in preferred_locations for keyword in ['remote', 'virtual', 'online']):
            if any(keyword in location_text for keyword in ['remote', 'virtual', 'online', 'anywhere']):
                return True
        
        return False
    
    def _check_eligibility_match(self, opportunity: EmailOpportunity, profile_data: dict) -> bool:
        """Check if user likely meets eligibility requirements."""
        eligibility_keywords = [kw.lower() for kw in profile_data.get('eligibility_keywords', [])]
        
        if not eligibility_keywords:
            return True  # No eligibility criteria means accept all
        
        eligibility_text = f"{opportunity.eligibility} {opportunity.notes}".lower()
        
        # Check if any eligibility keyword is mentioned
        for keyword in eligibility_keywords:
            if keyword in eligibility_text:
                return True
        
        # If no specific eligibility mentioned, assume it's open
        if not any(word in eligibility_text for word in ['required', 'must', 'only', 'exclusive']):
            return True
        
        return False
    
    def _check_deadline_relevance(self, opportunity: EmailOpportunity, profile_data: dict) -> bool:
        """Check if deadline is still relevant."""
        time_sensitivity = profile_data.get('time_sensitivity', {})
        max_days = time_sensitivity.get('exploratory_days', 90)
        
        try:
            from dateutil.parser import parse
            import re
            from datetime import datetime, timedelta
            
            # Extract dates from deadline text
            date_patterns = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}', opportunity.deadlines)
            
            if not date_patterns:
                return True  # No clear deadline, assume it's still relevant
            
            # Check if any deadline is within the acceptable range
            for date_str in date_patterns:
                try:
                    deadline_date = parse(date_str, fuzzy=True)
                    days_until = (deadline_date - datetime.now()).days
                    
                    if days_until >= -7 and days_until <= max_days:  # Allow 7 days past due
                        return True
                except:
                    continue
            
            return False  # All deadlines are too far out or too old
            
        except Exception:
            return True  # Default to relevant if parsing fails
    
    def calculate_similarity_scores(self, opportunities: List[EmailOpportunity]) -> List[EmailOpportunity]:
        """Calculate similarity scores for opportunities using optimized batch processing."""
        if not opportunities:
            return opportunities
            
        profile_data = self.profile.load_profile()
        interests_text = " ".join(profile_data.get('interests', []))
        
        if not interests_text.strip():
            self.logger.debug("No interests defined in profile, skipping similarity scoring")
            return opportunities
        
        # Batch process similarity calculations for better performance
        for opportunity in opportunities:
            try:
                opportunity_text = f"{opportunity.title} {opportunity.notes}"
                similarity = calculate_text_similarity(interests_text, opportunity_text)
                
                # Apply similarity boost with diminishing returns for very high scores
                similarity_boost = similarity * 0.2 * (1.0 - opportunity.priority_score * 0.5)
                opportunity.priority_score = min(opportunity.priority_score + similarity_boost, 1.0)
                
            except Exception as e:
                self.logger.error(f"Error calculating similarity for {opportunity.uid}: {e}")
        
        return opportunities
    
    def deduplicate_opportunities(self, opportunities: List[EmailOpportunity], similarity_threshold: float = 0.8) -> List[EmailOpportunity]:
        """Remove duplicate or very similar opportunities using optimized algorithm."""
        if len(opportunities) <= 1:
            return opportunities
        
        # Sort by priority score (descending) to prioritize keeping higher-scored items
        sorted_opportunities = sorted(opportunities, key=lambda x: x.priority_score, reverse=True)
        
        deduplicated = []
        skip_indices = set()
        
        for i, opp1 in enumerate(sorted_opportunities):
            if i in skip_indices:
                continue
            
            # Check against all lower-scored opportunities
            for j in range(i + 1, len(sorted_opportunities)):
                if j in skip_indices:
                    continue
                
                opp2 = sorted_opportunities[j]
                similarity = self._calculate_opportunity_similarity(opp1, opp2)
                
                if similarity >= similarity_threshold:
                    # Skip the lower-scored duplicate
                    skip_indices.add(j)
                    self.logger.debug(f"Marking as duplicate: {opp2.title} (similarity: {similarity:.3f})")
            
            deduplicated.append(opp1)
        
        # Restore original order (by processed_date or similar)
        deduplicated.sort(key=lambda x: getattr(x, 'processed_date', x.uid))
        
        self.logger.info(f"Deduplicated {len(opportunities)} to {len(deduplicated)} opportunities")
        return deduplicated
    
    def _calculate_opportunity_similarity(self, opp1: EmailOpportunity, opp2: EmailOpportunity) -> float:
        """Calculate similarity between two opportunities with caching optimization."""
        try:
            # Quick exact match checks first (most efficient)
            if opp1.uid == opp2.uid:
                return 1.0
            
            # Exact title match
            if opp1.title.strip().lower() == opp2.title.strip().lower():
                return 1.0
            
            # Same organization + same type = high similarity
            same_org = opp1.organization.lower().strip() == opp2.organization.lower().strip()
            same_type = opp1.opportunity_type.lower() == opp2.opportunity_type.lower()
            
            if same_org and same_type:
                # Still calculate title similarity for fine-grained comparison
                title_similarity = calculate_text_similarity(opp1.title, opp2.title)
                return max(0.8, title_similarity)  # At least 0.8 if same org+type
            
            # Detailed similarity calculation
            title_similarity = calculate_text_similarity(opp1.title, opp2.title)
            org_similarity = 1.0 if same_org else 0.0
            type_similarity = 1.0 if same_type else 0.0
            
            # Weighted combination with emphasis on title similarity
            weights = [0.6, 0.25, 0.15]  # title (increased), org, type
            similarities = [title_similarity, org_similarity, type_similarity]
            
            overall_similarity = sum(w * s for w, s in zip(weights, similarities))
            return overall_similarity
            
        except Exception as e:
            self.logger.error(f"Error calculating opportunity similarity: {e}")
            return 0.0
    
    def get_filtering_stats(self, original_count: int, filtered_count: int) -> dict:
        """Get filtering statistics."""
        return {
            "original_count": original_count,
            "filtered_count": filtered_count,
            "filtered_out": original_count - filtered_count,
            "retention_rate": filtered_count / original_count if original_count > 0 else 0.0
        }