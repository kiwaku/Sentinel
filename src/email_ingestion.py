"""
Email ingestion module for the Sentinel email opportunity extraction system.
Handles IMAP connection, email fetching, and UID tracking.
"""

import email
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Dict, List, Optional, Tuple

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from .utils import ConfigManager, DatabaseManager, safe_extract_text


class EmailMessage:
    """Represents a fetched email message."""
    
    def __init__(self, uid: str, subject: str, sender: str, body: str, date_received: datetime, 
                 metadata: Optional[dict] = None, account_name: str = "default"):
        self.uid = uid
        self.subject = subject
        self.sender = sender
        self.body = body
        self.date_received = date_received
        self.metadata = metadata or {}
        self.account_name = account_name
        # Create composite UID to prevent conflicts between accounts
        self.composite_uid = f"{account_name}:{uid}"
    
    def __repr__(self):
        return f"EmailMessage(account={self.account_name}, uid={self.uid}, subject='{self.subject[:50]}...', sender='{self.sender}')"


class EmailIngestionService:
    """Service for ingesting emails from IMAP server."""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    def connect_to_email(self, account_config: dict) -> IMAPClient:
        """Establish IMAP connection to email server for specific account."""
        try:
            # Create IMAP client
            client = IMAPClient(
                host=account_config['imap_server'],
                port=account_config['imap_port'],
                ssl=True
            )
            
            # Authenticate
            if account_config.get('use_oauth', False):
                self._authenticate_oauth(client, account_config)
            else:
                client.login(account_config['username'], account_config['password'])
            
            account_name = account_config.get('account_name', account_config['username'])
            self.logger.info(f"Successfully connected to {account_config['imap_server']} for account: {account_name}")
            return client
            
        except IMAPClientError as e:
            self.logger.error(f"Failed to connect to email server: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during email connection: {e}")
            raise
    
    def _authenticate_oauth(self, client: IMAPClient, account_config: Dict):
        """Authenticate using OAuth (placeholder for future implementation)."""
        # This is a placeholder for OAuth implementation
        # For now, fall back to basic authentication
        self.logger.warning("OAuth not implemented yet, falling back to basic auth")
        client.login(account_config['username'], account_config['password'])
    
    def fetch_new_emails(self, days_back: Optional[int] = None) -> List[EmailMessage]:
        """Fetch new emails from all configured accounts that haven't been processed yet."""
        all_emails = []
        
        # Get email account configurations
        email_accounts = self._get_email_accounts()
        
        for account_config in email_accounts:
            account_name = account_config.get('account_name', account_config.get('username', 'unknown'))
            
            try:
                self.logger.info(f"Processing emails from account: {account_name}")
                account_emails = self._fetch_emails_from_account(account_config, days_back)
                all_emails.extend(account_emails)
                
            except Exception as e:
                self.logger.error(f"Error processing account {account_name}: {e}")
                # Continue with other accounts even if one fails
                continue
        
        self.logger.info(f"Total emails fetched from all accounts: {len(all_emails)}")
        return all_emails
    
    def _get_email_accounts(self) -> List[dict]:
        """Get list of email account configurations."""
        # Support both old single-account and new multi-account format
        config_data = self.config.load_config()
        if 'email_accounts' in config_data:
            return self.config.get('email_accounts')
        elif 'email' in config_data:
            # Legacy single account format
            email_config = self.config.get('email')
            email_config['account_name'] = email_config.get('account_name', 'Primary Account')
            return [email_config]
        else:
            self.logger.error("No email configuration found")
            return []
    
    def _fetch_emails_from_account(self, account_config: dict, days_back: Optional[int] = None) -> List[EmailMessage]:
        """Fetch new emails from a specific account."""
        client = None
        account_name = account_config.get('account_name', account_config.get('username', 'unknown'))
        
        try:
            client = self.connect_to_email(account_config)
            client.select_folder('INBOX')
            
            # Determine date range for email search
            if days_back is None:
                days_back = self.config.get('processing.days_back_initial', 7)
            
            since_date = datetime.now() - timedelta(days=days_back)
            
            # Search for emails since the specified date
            search_criteria = ['SINCE', since_date.date()]
            message_uids = client.search(search_criteria)
            
            self.logger.info(f"Found {len(message_uids)} emails in {account_name} since {since_date.date()}")
            
            # Filter out already processed emails (using composite UID)
            new_uids = []
            for uid in message_uids:
                composite_uid = f"{account_name}:{uid}"
                if not self.db.is_email_processed(composite_uid):
                    new_uids.append(uid)
            
            self.logger.info(f"Found {len(new_uids)} new emails to process from {account_name}")
            
            # Limit batch size per account
            max_emails = self.config.get('processing.max_emails_per_run', 100)
            if len(new_uids) > max_emails:
                new_uids = new_uids[:max_emails]
                self.logger.info(f"Limited to {max_emails} emails for this run from {account_name}")
            
            # Fetch email messages
            emails = []
            for uid in new_uids:
                try:
                    email_msg = self._fetch_email_message(client, uid, account_name)
                    if email_msg:
                        emails.append(email_msg)
                        # NOTE: Do NOT mark as processed here!
                        # Emails should only be marked as processed after successful opportunity extraction
                except Exception as e:
                    self.logger.error(f"Error fetching email {uid} from {account_name}: {e}")
                    continue
            
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails from {account_name}: {e}")
            return []
        finally:
            if client:
                try:
                    client.logout()
                except:
                    pass
    
    def _fetch_email_message(self, client: IMAPClient, uid: int, account_name: str) -> Optional[EmailMessage]:
        """Fetch a single email message by UID from specific account."""
        try:
            # Fetch email data
            response = client.fetch(uid, ['RFC822', 'ENVELOPE'])
            
            if uid not in response:
                self.logger.warning(f"No data found for email UID {uid} in account {account_name}")
                return None
            
            # Parse email
            email_data = response[uid][b'RFC822']
            envelope = response[uid][b'ENVELOPE']
            
            msg = email.message_from_bytes(email_data)
            
            # Extract basic information
            subject = self._decode_header(msg.get('Subject', ''))
            sender = self._decode_header(msg.get('From', ''))
            
            # Extract date
            date_received = self._parse_email_date(envelope.date if envelope.date else datetime.now())
            
            # Extract body and metadata
            body, metadata = self._extract_email_body_and_metadata(msg)
            
            return EmailMessage(
                uid=str(uid),
                subject=subject,
                sender=sender,
                body=body,
                date_received=date_received,
                metadata=metadata,
                account_name=account_name
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing email {uid} from account {account_name}: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header handling various encodings."""
        if not header:
            return ""
        
        try:
            decoded_parts = decode_header(header)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            
            return decoded_string.strip()
            
        except Exception as e:
            self.logger.warning(f"Error decoding header '{header}': {e}")
            return str(header)
    
    def _parse_email_date(self, date_obj) -> datetime:
        """Parse email date object to datetime."""
        if isinstance(date_obj, datetime):
            return date_obj
        
        try:
            # Try to parse as string
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(str(date_obj))
        except:
            # Fallback to current time
            return datetime.now()
    
    def _extract_email_body(self, msg: email.message.Message) -> str:
        """Extract email body text from message."""
        body_text = ""
        
        try:
            if msg.is_multipart():
                # Handle multipart messages
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue
                    
                    # Extract text content
                    if content_type == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        part_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body_text += part_text + "\n"
                    elif content_type == "text/html" and not body_text:
                        # Use HTML as fallback if no plain text found
                        charset = part.get_content_charset() or 'utf-8'
                        html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body_text += self._html_to_text(html_content)
            else:
                # Handle simple messages
                content_type = msg.get_content_type()
                charset = msg.get_content_charset() or 'utf-8'
                
                if content_type == "text/plain":
                    body_text = msg.get_payload(decode=True).decode(charset, errors='ignore')
                elif content_type == "text/html":
                    html_content = msg.get_payload(decode=True).decode(charset, errors='ignore')
                    body_text = self._html_to_text(html_content)
        
        except Exception as e:
            self.logger.error(f"Error extracting email body: {e}")
            body_text = "Error extracting email content"
        
        # Clean and limit body text
        return safe_extract_text(body_text, max_length=5000)
    
    def _extract_urls_from_html(self, html_content: str) -> List[str]:
        """Extract all URLs from HTML content before conversion."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.warning("BeautifulSoup not available, falling back to regex URL extraction")
            return self._extract_urls_with_regex(html_content)
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            urls = []
            
            # Extract href attributes from anchor tags
            for link in soup.find_all('a', href=True):
                url = link['href']
                if url.startswith(('http://', 'https://')):
                    urls.append(url)
            
            # Extract URLs from plain text patterns as fallback
            url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
            text_urls = re.findall(url_pattern, html_content)
            urls.extend(text_urls)
            
            return list(set(urls))  # Remove duplicates
            
        except Exception as e:
            self.logger.warning(f"Error extracting URLs with BeautifulSoup: {e}")
            return self._extract_urls_with_regex(html_content)
    
    def _extract_urls_with_regex(self, html_content: str) -> List[str]:
        """Fallback URL extraction using regex."""
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        urls = re.findall(url_pattern, html_content)
        return list(set(urls))
    
    def _extract_email_metadata(self, html_content: str, email_headers: dict) -> dict:
        """Extract comprehensive metadata from email content and headers."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.warning("BeautifulSoup not available, limited metadata extraction")
            return {
                'urls_with_context': [],
                'mailto_addresses': [],
                'calendar_links': [],
                'attachment_info': [],
                'email_headers': email_headers,
                'original_urls': self._extract_urls_with_regex(html_content)
            }
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            metadata = {
                'urls_with_context': [],
                'mailto_addresses': [],
                'calendar_links': [],
                'attachment_info': [],
                'email_headers': email_headers,
                'original_urls': []
            }
            
            # Extract URLs with anchor text and context
            for link in soup.find_all('a', href=True):
                url = link['href']
                anchor_text = link.get_text(strip=True)
                
                if url.startswith(('http://', 'https://')):
                    metadata['urls_with_context'].append({
                        'url': url,
                        'anchor_text': anchor_text,
                        'context': link.parent.get_text(strip=True)[:200] if link.parent else ''
                    })
                    metadata['original_urls'].append(url)
                elif url.startswith('mailto:'):
                    email_addr = url.replace('mailto:', '').split('?')[0]
                    metadata['mailto_addresses'].append({
                        'email': email_addr,
                        'context': anchor_text
                    })
                elif url.endswith('.ics') or 'calendar' in url.lower():
                    metadata['calendar_links'].append({
                        'url': url,
                        'description': anchor_text
                    })
            
            # Extract attachment references
            for attachment_ref in soup.find_all(['a', 'link'], href=True):
                url = attachment_ref['href']
                if any(ext in url.lower() for ext in ['.pdf', '.doc', '.docx', '.xlsx', '.zip']):
                    metadata['attachment_info'].append({
                        'url': url,
                        'type': url.split('.')[-1].lower(),
                        'description': attachment_ref.get_text(strip=True)
                    })
            
            # Remove duplicates from original_urls
            metadata['original_urls'] = list(set(metadata['original_urls']))
            
            return metadata
            
        except Exception as e:
            self.logger.warning(f"Error extracting email metadata: {e}")
            return {
                'urls_with_context': [],
                'mailto_addresses': [],
                'calendar_links': [],
                'attachment_info': [],
                'email_headers': email_headers,
                'original_urls': self._extract_urls_with_regex(html_content)
            }
    
    def _extract_deadlines_from_link_context(self, urls_with_context: List[dict]) -> List[str]:
        """Extract deadline information from link anchor text and context."""
        deadlines = []
        date_patterns = [
            r'(?:due|deadline|apply by|submit by)[\s:]*([A-Za-z]+ \d{1,2}, \d{4})',
            r'(?:deadline)[\s:]*(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{1,2} [A-Za-z]+ \d{4})',
            r'([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})'
        ]
        
        for link_data in urls_with_context:
            combined_text = f"{link_data['anchor_text']} {link_data['context']}"
            
            for pattern in date_patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                deadlines.extend(matches)
        
        return list(set(deadlines))
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        try:
            from html.parser import HTMLParser
            
            class HTMLToTextParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_content = []
                
                def handle_data(self, data):
                    self.text_content.append(data)
                
                def get_text(self):
                    return ' '.join(self.text_content)
            
            parser = HTMLToTextParser()
            parser.feed(html_content)
            return parser.get_text()
            
        except Exception as e:
            self.logger.warning(f"Error converting HTML to text: {e}")
            # Fallback: simple tag removal
            import re
            return re.sub(r'<[^>]+>', '', html_content)
    
    def test_connection(self) -> bool:
        """Test email connection for all configured accounts and return success status."""
        email_accounts = self._get_email_accounts()
        
        if not email_accounts:
            self.logger.error("No email accounts configured")
            return False
        
        all_successful = True
        
        for account_config in email_accounts:
            account_name = account_config.get('account_name', account_config.get('username', 'unknown'))
            
            try:
                client = self.connect_to_email(account_config)
                client.logout()
                self.logger.info(f"Email connection test successful for account: {account_name}")
            except Exception as e:
                self.logger.error(f"Email connection test failed for account {account_name}: {e}")
                all_successful = False
        
        return all_successful
    
    def get_folder_list(self) -> List[str]:
        """Get list of available email folders."""
        client = None
        try:
            client = self.connect_to_email()
            folders = client.list_folders()
            folder_names = [folder[2] for folder in folders]
            self.logger.info(f"Available folders: {folder_names}")
            return folder_names
        except Exception as e:
            self.logger.error(f"Error getting folder list: {e}")
            return []
        finally:
            if client:
                try:
                    client.logout()
                except:
                    pass
    
    def _extract_email_body_and_metadata(self, msg: email.message.Message) -> Tuple[str, dict]:
        """Extract email body text and metadata from message."""
        body_text = ""
        html_content = ""
        email_headers = {
            'from': msg.get('From', ''),
            'to': msg.get('To', ''),
            'reply_to': msg.get('Reply-To', ''),
            'cc': msg.get('Cc', ''),
            'bcc': msg.get('Bcc', ''),
            'date': msg.get('Date', ''),
            'message_id': msg.get('Message-ID', '')
        }
        
        try:
            if msg.is_multipart():
                # Handle multipart messages
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue
                    
                    # Extract text content
                    if content_type == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        part_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body_text += part_text + "\n"
                    elif content_type == "text/html":
                        charset = part.get_content_charset() or 'utf-8'
                        html_part = part.get_payload(decode=True).decode(charset, errors='ignore')
                        html_content += html_part
                        if not body_text:  # Use HTML as fallback if no plain text found
                            body_text += self._html_to_text(html_part)
            else:
                # Handle simple messages
                content_type = msg.get_content_type()
                charset = msg.get_content_charset() or 'utf-8'
                
                if content_type == "text/plain":
                    body_text = msg.get_payload(decode=True).decode(charset, errors='ignore')
                elif content_type == "text/html":
                    html_content = msg.get_payload(decode=True).decode(charset, errors='ignore')
                    body_text = self._html_to_text(html_content)
        
        except Exception as e:
            self.logger.error(f"Error extracting email body and metadata: {e}")
            body_text = "Error extracting email content"
        
        # Extract metadata from HTML content if available
        metadata = {}
        if html_content:
            metadata = self._extract_email_metadata(html_content, email_headers)
        else:
            # Fallback for plain text emails
            metadata = {
                'urls_with_context': [],
                'mailto_addresses': [],
                'calendar_links': [],
                'attachment_info': [],
                'email_headers': email_headers,
                'original_urls': self._extract_urls_with_regex(body_text)
            }
        
        # Extract deadlines from link context
        metadata['deadlines_from_links'] = self._extract_deadlines_from_link_context(
            metadata.get('urls_with_context', [])
        )
        
        # Clean and limit body text
        clean_body = safe_extract_text(body_text, max_length=5000)
        
        return clean_body, metadata