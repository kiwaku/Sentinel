# 🛡️ Sentinel - Email Opportunity Extraction System

An intelligent email processing system that automatically identifies and extracts opportunities from your inbox using AI.

## Features

- **AI-Powered Extraction**: Uses LLM to identify relevant opportunities from emails
- **Smart Filtering**: Personalized filtering based on your interests and preferences
- **Multiple Email Accounts**: Support for monitoring multiple email sources
- **Clean CLI Interface**: Simple commands for searching and managing opportunities
- **Email Summaries**: Automated daily summaries of new opportunities
- **Secure Configuration**: Environment-based credential management
- **Local Storage**: All data stored locally with SQLite database

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/sentinel.git
cd sentinel
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
- `SOURCE_EMAIL_1_USERNAME` - Your email address
- `SOURCE_EMAIL_1_PASSWORD` - Your Gmail app-specific password  
- `LLM_API_KEY` - Your Together AI API key
- `SUMMARY_RECIPIENT_EMAIL` - Where to send summaries

### 3. Configure Settings

```bash
# Copy config templates
cp config/config.example.json config/config.json
cp config/profile.example.json config/profile.json

# Customize your profile and preferences
nano config/profile.json
```

### 4. Run Sentinel

```bash
# Test the system
python3 test_environment/final_validator.py

# Search for opportunities
python3 cli.py search "fellowship"

# Update your profile
python3 cli.py profile

# Run full pipeline
python3 main.py
```

## Commands

- `python3 cli.py search <keyword>` - Search existing opportunities
- `python3 cli.py profile` - Update your profile interactively
- `python3 main.py` - Run full email processing pipeline
- `python3 list_accounts.py` - List configured email accounts

## Configuration

### Email Setup

1. Enable 2-factor authentication on your Gmail account
2. Generate an app-specific password
3. Add credentials to `.env` file

### Multiple Email Accounts

You can add multiple source email accounts directly in your `.env` file:

```bash
# Source Email #1
SOURCE_EMAIL_1_NAME=Work Email
SOURCE_EMAIL_1_USERNAME=your-work-email@gmail.com
SOURCE_EMAIL_1_PASSWORD=your-app-password

# Source Email #2
SOURCE_EMAIL_2_NAME=Personal Email
SOURCE_EMAIL_2_USERNAME=your-personal-email@gmail.com
SOURCE_EMAIL_2_PASSWORD=your-app-password
```

See [docs/MULTI_ACCOUNT_GUIDE.md](docs/MULTI_ACCOUNT_GUIDE.md) for detailed configuration options.

### LLM Setup

1. Get a Together AI API key from [together.ai](https://together.ai)
2. Add API key to `.env` file

### Profile Customization

Edit `config/profile.json` to set:
- Your interests and preferences
- Opportunity types you're looking for
- Locations and exclusions

## Security

- All sensitive data is stored in `.env` (not committed to Git)
- Database files are excluded from version control
- No credentials are hardcoded in source code
- All email processing happens locally

## Testing

```bash
# Run comprehensive system validation
python3 test_environment/final_validator.py

# Quick validation
python3 test_environment/validator.py
```

<details>
<summary><strong>Key Technologies Used</strong></summary>

#### Large Language Models (LLM)
- Integration with Together AI API for AI-powered opportunity extraction  
- DSPy framework for advanced prompt engineering and LLM orchestration  
- Support for multiple LLM providers (Together AI, Ollama)

#### Natural Language Processing
- Semantic filtering using sentence embeddings  
- Text similarity scoring with cosine similarity  
- Adaptive thresholding for intelligent content relevance detection  
- Named Entity Recognition for organization and opportunity extraction

#### Machine Learning
- Sentence-Transformers for semantic text comparison  
- Vector embeddings for content similarity analysis  
- Interest-based scoring with supervised classification  
- Profile-based opportunity ranking

#### Data Management
- SQLite database for local data storage  
- Pandas for structured data manipulation  
- Pydantic for data validation and schema enforcement  
- JSON-based configuration management

#### Email Processing
- IMAP/SMTP protocol implementation  
- Multi-account email management  
- HTML parsing and text extraction  
- Metadata processing and entity extraction

#### Security & Privacy
- Environment-based credential management (`python-dotenv`)  
- Local processing of sensitive email data  
- App-specific password support  
- Secure environment variable handling

#### System Architecture
- Modular service-oriented design  
- Configurable pipeline with extensible components  
- Fallback mechanisms for service degradation  
- Comprehensive logging and error handling

#### Testing & Reliability
- Comprehensive test suite for components and end-to-end validation  
- Automated validation of system functionality  
- Performance monitoring for resource usage  
- Memory leak detection

</details>
## Project Structure

```
sentinel/
├── cli.py                 # Command-line interface
├── main.py               # Main application
├── list_accounts.py      # Account verification tool
├── src/                  # Core modules
│   ├── extraction.py     # AI-powered extraction
│   ├── filtering.py      # Opportunity filtering
│   ├── storage.py        # Database operations
│   └── utils.py         # Utilities and config
├── config/              # Configuration templates
├── docs/                # Documentation
├── test_environment/    # Validation tests
└── requirements.txt     # Python dependencies
```

## Configuration Reference

### Email Settings
| Setting | Description | Example |
|---------|-------------|---------|
| `imap_server` | IMAP server address | `imap.gmail.com` |
| `imap_port` | IMAP port (usually 993) | `993` |
| `smtp_server` | SMTP server address | `smtp.gmail.com` |
| `smtp_port` | SMTP port (usually 587) | `587` |
| `username` | Your email address | `user@gmail.com` |
| `password` | App password or OAuth token | `your-app-password` |

### Profile Settings
| Setting | Description |
|---------|-------------|
| `interests` | Keywords matching your interests |
| `exclusions` | Keywords to exclude (spam, unwanted topics) |
| `preferred_opportunities` | Types of opportunities you want |
| `preferred_locations` | Geographic or remote preferences |
| `time_sensitivity` | Deadline urgency thresholds |
| `scoring_weights` | Weights for priority calculation |

### Processing Settings
| Setting | Description | Default |
|---------|-------------|---------|
| `batch_size` | Emails processed per batch | `10` |
| `max_emails_per_run` | Maximum emails per execution | `100` |
| `similarity_threshold` | Deduplication threshold | `0.8` |
| `days_back_initial` | Initial lookback period | `7` |

## Workflow

1. **Email Ingestion** - Connects to your email accounts
2. **AI Analysis** - LLM evaluates emails for opportunities  
3. **Smart Filtering** - Filters based on your profile
4. **Storage** - Saves opportunities to local database
5. **Summarization** - Sends daily email summaries

## Troubleshooting

### Common Issues

** Email Connection Failed**
```bash
# Test email settings
python3 main.py test

# Check if app password is configured correctly
# Verify IMAP/SMTP settings for your provider
```

** No Opportunities Found**
```bash
# Check your profile settings
python3 cli.py profile

# Verify email search criteria
# Lower the similarity threshold in config
```

### Email Provider Settings

| Provider | IMAP Server | SMTP Server | Notes |
|----------|------------|-------------|--------|
| Gmail | `imap.gmail.com:993` | `smtp.gmail.com:587` | Requires App Password |
| Outlook | `outlook.office365.com:993` | `smtp.office365.com:587` | Works with regular password |
| Yahoo | `imap.mail.yahoo.com:993` | `smtp.mail.yahoo.com:587` | Requires App Password |

## Security & Privacy

- **Local Processing**: All data stays on your machine
- **Secure Storage**: SQLite database with local file access only
- **Environment Variables**: Sensitive data stored in `.env` (excluded from Git)
- **App Passwords**: Uses secure app passwords instead of main email password

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python3 test_environment/final_validator.py`
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## Support

- Check the test environment for validation
- Review configuration templates
- Ensure all environment variables are set
- See [docs/MULTI_ACCOUNT_GUIDE.md](docs/MULTI_ACCOUNT_GUIDE.md) for advanced configuration

---

**Security Note**: This system processes your personal emails locally and securely. Sensitive information like email passwords and API keys are stored in `.env` and configuration files that are excluded from version control in `.gitignore`. Always verify these files are not accidentally committed when making changes.

