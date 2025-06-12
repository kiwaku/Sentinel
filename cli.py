#!/usr/bin/env python3
"""
Sentinel CLI - Simple utilities for the email opportunity extraction system
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils import ProfileManager, DatabaseManager
from src.storage import StorageService


def search_opportunities(args):
    """Search opportunities by keyword."""
    try:
        db = DatabaseManager()
        
        with db.connect() as conn:
            conn.row_factory = db.Row
            
            query = """
                SELECT * FROM opportunities 
                WHERE title LIKE ? OR organization LIKE ? OR notes LIKE ?
                ORDER BY priority_score DESC, processed_date DESC
                LIMIT ?
            """
            
            search_term = f"%{args.keyword}%"
            cursor = conn.execute(query, (search_term, search_term, search_term, args.limit))
            
            results = cursor.fetchall()
            
            if not results:
                print(f"No opportunities found matching '{args.keyword}'")
                return
            
            print(f"\n🔍 SEARCH RESULTS for '{args.keyword}' ({len(results)} found)")
            print("=" * 60)
            
            for i, opp in enumerate(results, 1):
                print(f"\n{i}. {opp['title']}")
                print(f"   Organization: {opp['organization']}")
                print(f"   Type: {opp['opportunity_type']}")
                print(f"   Score: {opp['priority_score']:.2f}")
                print(f"   Date: {opp['processed_date']}")
                if args.verbose:
                    print(f"   Notes: {opp['notes'][:200]}...")
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False


def update_profile(args):
    """Interactive profile update."""
    try:
        profile_manager = ProfileManager('config/profile.json')
        profile = profile_manager.load_profile()
        
        print("🔧 PROFILE UPDATE")
        print("Current profile settings:")
        print(json.dumps(profile, indent=2))
        
        print("\nWhat would you like to update?")
        print("1. Interests")
        print("2. Preferred locations")
        print("3. Exclusions")
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1":
            print("\nCurrent interests:", profile.get('interests', []))
            new_interests = input("Enter new interests (comma-separated): ").strip()
            if new_interests:
                profile['interests'] = [i.strip() for i in new_interests.split(',')]
        
        elif choice == "2":
            print("\nCurrent locations:", profile.get('preferred_locations', []))
            new_locations = input("Enter new locations (comma-separated): ").strip()
            if new_locations:
                profile['preferred_locations'] = [l.strip() for l in new_locations.split(',')]
        
        elif choice == "3":
            print("\nCurrent exclusions:", profile.get('exclusions', []))
            new_exclusions = input("Enter new exclusions (comma-separated): ").strip()
            if new_exclusions:
                profile['exclusions'] = [e.strip() for e in new_exclusions.split(',')]
        
        # Save updated profile
        with open("config/profile.json", "w") as f:
            json.dump(profile, f, indent=2)
        
        print("✅ Profile updated successfully")
        
    except Exception as e:
        print(f"❌ Profile update failed: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sentinel CLI - Simple utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search opportunities')
    search_parser.add_argument('keyword', help='Search keyword')
    search_parser.add_argument('--limit', type=int, default=10, help='Maximum results')
    search_parser.add_argument('--verbose', action='store_true', help='Show detailed results')
    
    # Profile command
    subparsers.add_parser('profile', help='Update profile interactively')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    if args.command == 'search':
        search_opportunities(args)
    elif args.command == 'profile':
        update_profile(args)


if __name__ == "__main__":
    main()
