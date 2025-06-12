#!/usr/bin/env python3
"""
Mock data generator for Sentinel testing
Creates realistic test data without using real emails or sensitive information
"""

import json
import random
from datetime import datetime, timedelta

class MockDataGenerator:
    """Generates mock email data for testing"""
    
    SUBJECTS = [
        "Partnership Opportunity - AI Development",
        "Speaking Opportunity at TechConf 2024", 
        "Collaboration Proposal - Machine Learning Project",
        "Investment Opportunity in Your Startup",
        "Guest Post Opportunity on AI Blog",
        "Consulting Opportunity - Data Science",
        "Joint Venture Proposal",
        "Conference Invitation - Keynote Speaker",
        "Product Launch Partnership",
        "Research Collaboration Opportunity",
        # Non-opportunities (should be filtered out)
        "Meeting Reminder",
        "Newsletter Subscription",
        "Password Reset Request",
        "Spam: Get Rich Quick!",
        "Re: Invoice #12345"
    ]
    
    SENDERS = [
        "ceo@aicompany.com",
        "events@techconference.org", 
        "partnerships@startup.io",
        "editor@techblog.com",
        "founder@mlcompany.com",
        "organizer@aiconf.com",
        "investor@vcfund.com",
        "research@university.edu",
        "bd@bigtech.com",
        "spam@badactor.com",
        "noreply@newsletter.com",
        "admin@system.com"
    ]
    
    OPPORTUNITY_CONTENT = [
        """Hi there,

We're reaching out because we believe there's a great opportunity for collaboration between our companies. We're working on cutting-edge AI solutions and think your expertise would be valuable.

Would you be interested in discussing a potential partnership? We're looking for:
- Technical collaboration on ML models
- Joint product development
- Shared research initiatives

Let me know if you'd like to set up a call to discuss further.

Best regards,
Sarah Johnson""",
        
        """Hello,

I hope this email finds you well. We're organizing TechConf 2024 and would love to have you as a keynote speaker.

Event Details:
- Date: March 15-17, 2024
- Location: San Francisco, CA
- Audience: 500+ tech professionals
- Topic: AI and the Future of Work

This would be a great opportunity to share your insights with the community. We can offer:
- Speaking fee: $5,000
- Travel and accommodation covered
- Networking opportunities

Please let me know if you're interested.

Best,
Conference Team""",

        """Dear AI Expert,

We're a fast-growing startup in the fintech space and are looking for AI consultants to help us build our next-generation product.

Project scope:
- Duration: 3-6 months
- Budget: $50,000-$100,000
- Focus: NLP for financial document processing
- Remote work possible

Your background seems like a perfect fit. Would you be available for a brief call to discuss the opportunity?

Thanks,
Tech Lead""",
    ]
    
    NON_OPPORTUNITY_CONTENT = [
        """This is your weekly newsletter with the latest tech news.

Unsubscribe here if you no longer wish to receive these emails.

Best regards,
Newsletter Team""",

        """Dear User,

We noticed a failed login attempt on your account. If this wasn't you, please reset your password immediately.

Click here to reset: [LINK]

Security Team""",

        """CONGRATULATIONS! You've won $1,000,000 in our lottery!

Click here to claim your prize now! Limited time offer!

[SUSPICIOUS LINK]""",
    ]
    
    def generate_mock_emails(self, count=20):
        """Generate mock emails for testing"""
        emails = []
        
        for i in range(count):
            is_opportunity = random.choice([True, True, False])  # 2/3 chance of opportunity
            
            if is_opportunity:
                subject = random.choice(self.SUBJECTS[:10])  # First 10 are opportunities
                content = random.choice(self.OPPORTUNITY_CONTENT)
                sender = random.choice(self.SENDERS[:9])  # First 9 are legitimate
            else:
                subject = random.choice(self.SUBJECTS[10:])  # Last 5 are non-opportunities  
                content = random.choice(self.NON_OPPORTUNITY_CONTENT)
                sender = random.choice(self.SENDERS[9:])  # Last 3 are spam/system
                
            email = {
                "id": f"test_email_{i+1:03d}",
                "subject": subject,
                "sender": sender,
                "content": content,
                "date": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                "is_opportunity": is_opportunity  # Ground truth for testing
            }
            
            emails.append(email)
            
        return emails
    
    def save_mock_emails(self, emails, filepath):
        """Save mock emails to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(emails, f, indent=2)
            
    def load_mock_emails(self, filepath):
        """Load mock emails from JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)

if __name__ == "__main__":
    generator = MockDataGenerator()
    emails = generator.generate_mock_emails(50)
    
    print(f"Generated {len(emails)} mock emails")
    print("Sample emails:")
    
    for i, email in enumerate(emails[:3]):
        print(f"\n--- Email {i+1} ---")
        print(f"Subject: {email['subject']}")
        print(f"Sender: {email['sender']}")
        print(f"Is Opportunity: {email['is_opportunity']}")
        print(f"Content Preview: {email['content'][:100]}...")
    
    # Save to file
    generator.save_mock_emails(emails, "mock_emails.json")
    print(f"\nSaved to mock_emails.json")
