# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Concern

We take security seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security concerns
2. Email the maintainers directly or use GitHub's private vulnerability reporting feature
3. Include as much detail as possible:
   - Description of the issue
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Updates**: We will provide status updates as we investigate
- **Resolution**: We aim to address confirmed issues promptly
- **Credit**: We will credit reporters in the release notes (unless you prefer to remain anonymous)

### Scope

This policy applies to:
- The Trade Nexus application code
- Official Docker images
- CI/CD configurations

### Out of Scope

- Third-party dependencies (report to upstream maintainers)
- Issues in forked repositories
- Social engineering attempts

## Best Practices for Contributors

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive configuration
- Follow secure coding guidelines
- Keep dependencies updated

## Security Updates

Security updates will be released as patch versions and announced in the GitHub releases.
