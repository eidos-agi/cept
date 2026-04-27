# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in cept, please report it responsibly.

**Email:** daniel@eidosagi.com

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact

We will acknowledge your report within 48 hours and aim to provide a fix within 7 days for critical issues.

## Threat model — things to know

cept reads local Claude Code transcripts, redacts them, and sends a distilled packet to a model gateway (OpenRouter by default). Two areas warrant explicit attention:

1. **`.ceptkey` walk-up trust.** cept walks up from the current working directory looking for a `.ceptkey` file. If you `cd` into a hostile repo with a malicious `.ceptkey`, your packets would route to that endpoint. Blast radius: the redacted packet (the real key never leaves the machine; the malicious file's key would be the one sent). v1 does **not** require a `direnv allow`-style confirmation. Don't `cd` into untrusted trees with cept active.
2. **Redactor coverage.** The redactor strips known patterns (sk-or-/sk-/pplx-/ghp_ etc., bearer tokens, JWTs, env-style assignments, basic-auth URLs, emails, home paths). It is best-effort and pattern-based; it is NOT a guarantee against novel secret formats. If you handle especially sensitive material, audit the packet before sending — `cept-cli --dry-run` prints the exact redacted payload that would go to the model.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |

## Disclosure Policy

We follow coordinated disclosure. Please give us reasonable time to address the issue before public disclosure.
