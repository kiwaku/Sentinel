#!/usr/bin/env python
"""
List all configured email accounts in the Sentinel system.
This script helps verify that your email account configuration is correct.
"""

import os
import sys
from pathlib import Path

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import ConfigManager

def list_email_accounts():
    """List all configured email accounts."""
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    if 'email_accounts' in config and config['email_accounts']:
        print(f"\n📧 Found {len(config['email_accounts'])} configured email accounts:")
        print("-" * 50)
        
        for i, account in enumerate(config['email_accounts'], 1):
            print(f"Account #{i}: {account.get('account_name', 'Unnamed')}")
            print(f"  • Username: {account.get('username', 'N/A')}")
            print(f"  • IMAP Server: {account.get('imap_server', 'N/A')}")
            print(f"  • SMTP Server: {account.get('smtp_server', 'N/A')}")
            print(f"  • OAuth: {'Yes' if account.get('use_oauth') else 'No'}")
            print("-" * 50)
    elif 'email' in config:
        print("\n📧 Found single email account configuration:")
        print("-" * 50)
        print(f"Username: {config['email'].get('username', 'N/A')}")
        print(f"IMAP Server: {config['email'].get('imap_server', 'N/A')}")
        print(f"SMTP Server: {config['email'].get('smtp_server', 'N/A')}")
        print(f"OAuth: {'Yes' if config['email'].get('use_oauth') else 'No'}")
        print("-" * 50)
        print("\nTo configure multiple accounts, use the SOURCE_EMAIL_X_* format in your .env file.")
        print("See docs/MULTI_ACCOUNT_GUIDE.md for details.")
    else:
        print("\n❌ No email accounts configured!")
        print("Please check your configuration in config.json or .env file.")
        print("See docs/MULTI_ACCOUNT_GUIDE.md for setup instructions.")

if __name__ == "__main__":
    list_email_accounts()
