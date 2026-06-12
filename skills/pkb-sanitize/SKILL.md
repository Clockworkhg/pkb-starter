# pkb-sanitize — Privacy Scan & Sanitization

## When to Use
- User runs `/sanitize <file>` or `/sanitize <directory>`
- Before sharing knowledge base content externally
- Before committing sensitive-looking files
- Pre-flight check before git push to public repo

## Instructions

### 1. Scan Target
Scan the specified file or directory for sensitive patterns:

#### API Keys & Tokens
- `api_key=`, `apiKey:`, `apikey`
- `token=`, `"token":`, `access_token`
- `secret=`, `"secret":`, `client_secret`
- `password=`, `"password":`, `passwd`

#### Private Keys
- `-----BEGIN RSA PRIVATE KEY-----`
- `-----BEGIN OPENSSH PRIVATE KEY-----`
- `-----BEGIN EC PRIVATE KEY-----`
- `-----BEGIN PGP PRIVATE KEY BLOCK-----`

#### Personal Identifiable Info (PII)
- Email addresses: `xxx@xxx.xxx`
- Phone numbers: various formats
- ID card numbers: 18-digit Chinese ID pattern
- Credit card numbers: 13-19 digit patterns

#### Credential Files
- `.env`, `.env.local`, `.env.production`
- `credentials.json`, `serviceAccount.json`
- `*.pem`, `*.p12`, `*.pfx`, `*.key`, `*.keystore`, `*.jks`
- `id_rsa*`, `*_rsa`, `*.ppk`

### 2. Report
```
🔒 Sanitize Scan Report
═══════════════════════

🔴 Critical (must fix before sharing):
  - file:line — <pattern> found

🟡 Warning (review before sharing):
  - file:line — <potential pattern>

✅ Clean: N files

📊 Total: M files scanned, K patterns found
```

### 3. Auto-Sanitize (with --fix flag)
Replace detected patterns with placeholders:
- API keys → `REDACTED_api_key`
- Tokens → `REDACTED_token`
- Emails → `redacted@example.com`
- Private keys → `[REDACTED PRIVATE KEY]`

### 4. Pre-Commit Hook Integration
This skill is also called automatically by `/save` before git commit.
If critical patterns found → block commit, warn user.

## Safety Notes
- Sanitize creates a copy — never modifies original files
- Auto-sanitize is conservative: better to redact too much than too little
- Always review sanitized output before sharing
- This tool helps but cannot guarantee 100% detection — always manually review
