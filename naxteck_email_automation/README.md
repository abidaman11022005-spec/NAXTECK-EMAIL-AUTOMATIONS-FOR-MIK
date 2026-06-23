# NAXTECK Email Automation
## Powered by NAXTECK Marketing Solutions

## What It Does
- 📊 Sends daily report every morning at 9am
- 🔍 Checks campaigns every hour silently
- 🚨 Sends alert email ONLY if something is wrong
- ✅ No email if everything is normal

## Setup
1. Fill in .env file with your credentials
2. Install packages: pip install -r requirements.txt
3. Run: python automation.py

## .env File
- META_ACCESS_TOKEN: Get from developers.facebook.com/tools/explorer
- META_AD_ACCOUNT_ID: Your ad account IDs separated by comma
- CLIENT_NAMES: Client names matching account IDs order
- EMAIL_FROM: Your Gmail address
- EMAIL_PASSWORD: Gmail app password (16 digits)
- EMAIL_TO: Where to send reports

## Alert Rules
- 🚨 CPA > Rs.600 = High CPA alert
- ⚠️ CTR < 1% = Low CTR alert
- 🎉 ROAS > 2.5x = Scale budget alert
