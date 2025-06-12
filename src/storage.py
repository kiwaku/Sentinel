"""
Storage module for managing opportunity data and system state.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .utils import DatabaseManager, EmailOpportunity


class StorageService:
    """Enhanced storage service for managing opportunities and system state."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    def save_opportunities(self, opportunities: List[EmailOpportunity]) -> int:
        """Save a list of opportunities to the database."""
        saved_count = 0
        
        for opportunity in opportunities:
            try:
                self.db.save_opportunity(opportunity)
                saved_count += 1
            except Exception as e:
                self.logger.error(f"Error saving opportunity {opportunity.uid}: {e}")
        
        self.logger.info(f"Saved {saved_count}/{len(opportunities)} opportunities to database")
        return saved_count
    
    def get_opportunities_for_summary(self, days: int = 1) -> Dict[str, List[EmailOpportunity]]:
        """Get opportunities categorized for daily summary."""
        opportunities = self.db.get_recent_opportunities(days)
        
        categorized = {
            'high_priority': [],
            'exploratory': []
        }
        
        for opp in opportunities:
            if opp.category == 'high_priority':
                categorized['high_priority'].append(opp)
            else:
                categorized['exploratory'].append(opp)
        
        return categorized
    
    def export_opportunities_to_json(self, opportunities: List[EmailOpportunity], file_path: str):
        """Export opportunities to JSON file for backup or analysis."""
        try:
            # Convert opportunities to dictionaries
            data = []
            for opp in opportunities:
                opp_dict = {
                    'uid': opp.uid,
                    'title': opp.title,
                    'organization': opp.organization,
                    'opportunity_type': opp.opportunity_type,
                    'eligibility': opp.eligibility,
                    'location': opp.location,
                    'deadlines': opp.deadlines,
                    'notes': opp.notes,
                    'email_date': opp.email_date.isoformat() if opp.email_date else None,
                    'processed_date': opp.processed_date.isoformat(),
                    'priority_score': opp.priority_score,
                    'category': opp.category,
                    # Add new metadata fields
                    'original_urls': opp.original_urls,
                    'primary_url': opp.primary_url,
                    'urls_with_context': opp.urls_with_context,
                    'mailto_addresses': opp.mailto_addresses,
                    'calendar_links': opp.calendar_links,
                    'attachment_info': opp.attachment_info,
                    'email_headers': opp.email_headers,
                    'deadlines_from_links': opp.deadlines_from_links
                }
                data.append(opp_dict)
            
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Exported {len(opportunities)} opportunities to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error exporting opportunities to JSON: {e}")
            raise
    
    def import_opportunities_from_json(self, file_path: str) -> List[EmailOpportunity]:
        """Import opportunities from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            opportunities = []
            for item in data:
                opportunity = EmailOpportunity(
                    uid=item['uid'],
                    title=item['title'],
                    organization=item['organization'],
                    opportunity_type=item['opportunity_type'],
                    eligibility=item['eligibility'],
                    location=item['location'],
                    deadlines=item['deadlines'],
                    notes=item['notes'],
                    email_date=datetime.fromisoformat(item['email_date']) if item['email_date'] else None,
                    processed_date=datetime.fromisoformat(item['processed_date']),
                    priority_score=item['priority_score'],
                    category=item['category'],
                    # Add new metadata fields with defaults for backward compatibility
                    original_urls=item.get('original_urls', []),
                    primary_url=item.get('primary_url'),
                    urls_with_context=item.get('urls_with_context', []),
                    mailto_addresses=item.get('mailto_addresses', []),
                    calendar_links=item.get('calendar_links', []),
                    attachment_info=item.get('attachment_info', []),
                    email_headers=item.get('email_headers', {}),
                    deadlines_from_links=item.get('deadlines_from_links', [])
                )
                opportunities.append(opportunity)
            
            self.logger.info(f"Imported {len(opportunities)} opportunities from {file_path}")
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error importing opportunities from JSON: {e}")
            raise
    
    def get_processing_statistics(self, days: int = 7) -> Dict:
        """Get processing statistics for the last N days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get opportunity counts by category
                stats = {}
                
                cursor = conn.execute("""
                    SELECT category, COUNT(*) as count
                    FROM opportunities 
                    WHERE processed_date >= ?
                    GROUP BY category
                """, (cutoff_date,))
                
                for row in cursor.fetchall():
                    stats[f"{row['category']}_count"] = row['count']
                
                # Get total processed emails
                cursor = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM processed_emails
                    WHERE processed_date >= ?
                """, (cutoff_date,))
                
                stats['emails_processed'] = cursor.fetchone()['count']
                
                # Get average priority score
                cursor = conn.execute("""
                    SELECT AVG(priority_score) as avg_score
                    FROM opportunities
                    WHERE processed_date >= ?
                """, (cutoff_date,))
                
                result = cursor.fetchone()
                stats['average_priority_score'] = float(result['avg_score']) if result['avg_score'] else 0.0
                
                # Get opportunities by day
                cursor = conn.execute("""
                    SELECT DATE(processed_date) as date, COUNT(*) as count
                    FROM opportunities
                    WHERE processed_date >= ?
                    GROUP BY DATE(processed_date)
                    ORDER BY date
                """, (cutoff_date,))
                
                daily_counts = {}
                for row in cursor.fetchall():
                    daily_counts[row['date']] = row['count']
                
                stats['daily_counts'] = daily_counts
                stats['period_days'] = days
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {e}")
            return {}
    
    def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old data and create backup if needed."""
        try:
            # Get count before cleanup
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM opportunities")
                old_count = cursor.fetchone()[0]
            
            # Perform cleanup
            self.db.cleanup_old_data(retention_days)
            
            # Get count after cleanup
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM opportunities")
                new_count = cursor.fetchone()[0]
            
            cleaned_count = old_count - new_count
            self.logger.info(f"Cleaned up {cleaned_count} old opportunities (retention: {retention_days} days)")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
    
    def backup_database(self, backup_path: str):
        """Create a backup of the database."""
        try:
            import shutil
            
            # Ensure backup directory exists
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Copy database file
            shutil.copy2(self.db.db_path, backup_path)
            
            self.logger.info(f"Database backed up to {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Error backing up database: {e}")
            raise
    
    def get_similar_opportunities(self, opportunity: EmailOpportunity, limit: int = 5) -> List[EmailOpportunity]:
        """Find similar opportunities in the database."""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Simple similarity based on organization and opportunity type
                cursor = conn.execute("""
                    SELECT * FROM opportunities
                    WHERE (organization LIKE ? OR opportunity_type LIKE ?)
                    AND uid != ?
                    ORDER BY priority_score DESC
                    LIMIT ?
                """, (
                    f"%{opportunity.organization}%",
                    f"%{opportunity.opportunity_type}%",
                    opportunity.uid,
                    limit
                ))
                
                similar_opportunities = []
                for row in cursor.fetchall():
                    # Parse JSON fields safely
                    original_urls = json.loads(row['original_urls']) if row.get('original_urls') else []
                    urls_with_context = json.loads(row['urls_with_context']) if row.get('urls_with_context') else []
                    mailto_addresses = json.loads(row['mailto_addresses']) if row.get('mailto_addresses') else []
                    calendar_links = json.loads(row['calendar_links']) if row.get('calendar_links') else []
                    attachment_info = json.loads(row['attachment_info']) if row.get('attachment_info') else []
                    email_headers = json.loads(row['email_headers']) if row.get('email_headers') else {}
                    deadlines_from_links = json.loads(row['deadlines_from_links']) if row.get('deadlines_from_links') else []
                    
                    similar_opp = EmailOpportunity(
                        uid=row['uid'],
                        title=row['title'],
                        organization=row['organization'],
                        opportunity_type=row['opportunity_type'],
                        eligibility=row['eligibility'],
                        location=row['location'],
                        deadlines=row['deadlines'],
                        notes=row['notes'],
                        email_date=datetime.fromisoformat(row['email_date']) if row['email_date'] else None,
                        processed_date=datetime.fromisoformat(row['processed_date']),
                        priority_score=row['priority_score'],
                        category=row['category'],
                        original_urls=original_urls,
                        primary_url=row.get('primary_url'),
                        urls_with_context=urls_with_context,
                        mailto_addresses=mailto_addresses,
                        calendar_links=calendar_links,
                        attachment_info=attachment_info,
                        email_headers=email_headers,
                        deadlines_from_links=deadlines_from_links
                    )
                    similar_opportunities.append(similar_opp)
                
                return similar_opportunities
                
        except Exception as e:
            self.logger.error(f"Error finding similar opportunities: {e}")
            return []
    
    def update_opportunity_category(self, uid: str, new_category: str) -> bool:
        """Update the category of an opportunity."""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE opportunities SET category = ? WHERE uid = ?",
                    (new_category, uid)
                )
                
                if cursor.rowcount > 0:
                    self.logger.info(f"Updated opportunity {uid} category to {new_category}")
                    return True
                else:
                    self.logger.warning(f"No opportunity found with UID {uid}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error updating opportunity category: {e}")
            return False
    
    def get_opportunities_by_organization(self, organization: str) -> List[EmailOpportunity]:
        """Get all opportunities from a specific organization."""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT * FROM opportunities
                    WHERE organization LIKE ?
                    ORDER BY processed_date DESC
                """, (f"%{organization}%",))
                
                opportunities = []
                for row in cursor.fetchall():
                    # Parse JSON fields safely
                    original_urls = json.loads(row['original_urls']) if row.get('original_urls') else []
                    urls_with_context = json.loads(row['urls_with_context']) if row.get('urls_with_context') else []
                    mailto_addresses = json.loads(row['mailto_addresses']) if row.get('mailto_addresses') else []
                    calendar_links = json.loads(row['calendar_links']) if row.get('calendar_links') else []
                    attachment_info = json.loads(row['attachment_info']) if row.get('attachment_info') else []
                    email_headers = json.loads(row['email_headers']) if row.get('email_headers') else {}
                    deadlines_from_links = json.loads(row['deadlines_from_links']) if row.get('deadlines_from_links') else []
                    
                    opportunity = EmailOpportunity(
                        uid=row['uid'],
                        title=row['title'],
                        organization=row['organization'],
                        opportunity_type=row['opportunity_type'],
                        eligibility=row['eligibility'],
                        location=row['location'],
                        deadlines=row['deadlines'],
                        notes=row['notes'],
                        email_date=datetime.fromisoformat(row['email_date']) if row['email_date'] else None,
                        processed_date=datetime.fromisoformat(row['processed_date']),
                        priority_score=row['priority_score'],
                        category=row['category'],
                        original_urls=original_urls,
                        primary_url=row.get('primary_url'),
                        urls_with_context=urls_with_context,
                        mailto_addresses=mailto_addresses,
                        calendar_links=calendar_links,
                        attachment_info=attachment_info,
                        email_headers=email_headers,
                        deadlines_from_links=deadlines_from_links
                    )
                    opportunities.append(opportunity)
                
                return opportunities
                
        except Exception as e:
            self.logger.error(f"Error getting opportunities by organization: {e}")
            return []