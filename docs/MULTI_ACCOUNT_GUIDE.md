# Multi-Account Configuration Guide

This guide explains how to configure multiple email accounts for the Sentinel email opportunity extraction system.

## Configuration Methods

There are two ways to configure email accounts in Sentinel:

1. **Environment Variables (Recommended)**: Define multiple accounts directly in your `.env` file
2. **JSON Configuration**: Define accounts in the `config.json` file

## Environment Variables Method

The simplest way to set up multiple email accounts is through environment variables in your `.env` file.

### Format

Use the following format in your `.env` file:

```
SOURCE_EMAIL_{number}_{parameter}=value
```

Where:
- `{number}` is a sequential number starting with 1 (SOURCE_EMAIL_1, SOURCE_EMAIL_2, etc.)
- `{parameter}` is one of the supported account parameters

### Required Parameters

- `USERNAME`: The email address
- `PASSWORD`: The email password or app-specific password

### Optional Parameters

- `NAME`: A friendly name for the account (default: "Account X")
- `IMAP_SERVER`: IMAP server address (default: imap.gmail.com)
- `IMAP_PORT`: IMAP port number (default: 993)
- `SMTP_SERVER`: SMTP server address (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP port number (default: 587)
- `USE_OAUTH`: Whether to use OAuth instead of password (default: false)

### Example

```
# Primary Email Account
SOURCE_EMAIL_1_NAME=Work Email
SOURCE_EMAIL_1_USERNAME=your-work-email@gmail.com
SOURCE_EMAIL_1_PASSWORD=your-app-specific-password
SOURCE_EMAIL_1_IMAP_SERVER=imap.gmail.com
SOURCE_EMAIL_1_SMTP_SERVER=smtp.gmail.com

# Personal Email Account
SOURCE_EMAIL_2_NAME=Personal Email
SOURCE_EMAIL_2_USERNAME=your-personal-email@gmail.com
SOURCE_EMAIL_2_PASSWORD=your-app-specific-password
# Using defaults for servers and ports
```

## JSON Configuration Method

You can also configure multiple email accounts in your `config.json` file:

```json
{
  "email_accounts": [
    {
      "account_name": "Work Email",
      "username": "your-work-email@gmail.com",
      "password": "your-app-specific-password",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "use_oauth": false
    },
    {
      "account_name": "Personal Email",
      "username": "your-personal-email@gmail.com",
      "password": "your-app-specific-password",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "use_oauth": false
    }
  ],
  
  // Other configuration sections...
}
```

## Priority

If both environment variables and JSON configuration are present, the environment variables will take precedence.

## Legacy Support

For backwards compatibility, the system still supports the original single-account configuration:

```
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-specific-password
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_SMTP_SERVER=smtp.gmail.com
```

This configuration will be used if no multiple email accounts are defined.
