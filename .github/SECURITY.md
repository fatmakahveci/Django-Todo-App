# Security Policy

## Supported Versions

Security fixes target the latest code on the default branch. Older releases,
forks, and other branches are not guaranteed to receive backported fixes.

## Reporting a Vulnerability

Please do not disclose security vulnerabilities in public issues, discussions,
or pull requests.

Report a vulnerability through this repository's
[private vulnerability reporting](https://github.com/fatmakahveci/Django-Todo-App/security/advisories/new).
If that option is unavailable, contact the repository owner through the
[GitHub profile](https://github.com/fatmakahveci) to arrange a private reporting
channel.

If no private contact method is listed, open an issue asking only for a private
security contact. Do not include vulnerability details in that issue.

### What to Include

- A short description of the vulnerability and its potential impact.
- The affected commit or version, Python and Django versions, and relevant
  configuration.
- Reproduction steps or a minimal proof of concept using test accounts and
  synthetic data.
- Any required access or prerequisites, such as an authenticated account.
- Suggested mitigations, if available.

Remove passwords, session cookies, secret keys, and personal data from reports,
logs, and screenshots.

## Scope and Safe Testing

Relevant reports include authentication bypass, access to another user's tasks,
unauthorized task changes or deletion, injection, cross-site scripting,
cross-site request forgery, and exposure of sensitive information.

Test only on a local instance or a system you have explicit permission to test.
Use accounts and data you control. Avoid accessing other users' data, disrupting
services, or performing destructive tests on shared deployments.

## Handling and Disclosure

Reports will be reviewed as promptly as possible. Maintainers may request more
information to reproduce the issue and will coordinate remediation and public
disclosure with the reporter through the private reporting channel. No fixed
response or resolution time is guaranteed.

Please allow time for investigation and a fix before publishing exploit details.
State whether you would like to be credited in any public advisory.

## Deployment Context

The checked-in settings in `config/settings.py` are for local development:
they enable `DEBUG` and contain a development secret key. They should not be
treated as a production configuration. Never reuse the checked-in key for a
public deployment or commit production credentials or personal task data.

## Application Controls

- All task operations and exports enforce authentication and task ownership.
- Mutations require POST and CSRF protection; user content is template-escaped.
- Login and admin login share 10 attempts per normalized username per five-minute
  window. Authentication POSTs also share 40 attempts per IP per window;
  registration permits five attempts per IP. Successful requests count too.
- Counters are shared through the database and store keyed hashes instead of raw
  usernames/IPs. Expired records are cleaned during later authentication requests,
  after a five-minute grace period for requests crossing window boundaries.
- Dynamic responses prohibit caching and include a restrictive Content Security
  Policy. Production requires HTTPS cookies, a strong signing key, and explicit hosts.
- Request bodies are limited to 64 KiB and 50 form fields; task notes to 10,000 characters.

Account throttling can temporarily affect legitimate users if someone targets
that username. Fixed windows do not fully prevent distributed attacks; combine
application protection with reverse-proxy limits and monitoring where needed.

Only configure `AUTH_TRUSTED_PROXIES` for proxies you control that overwrite
`X-Real-IP`. Otherwise forwarded IP headers are ignored. Never expose the
container directly when trusting forwarded HTTPS or client-IP headers.

The local database is excluded from future commits and release archives. Old
commits can still contain database copies or secrets. Rotate/revoke any production
credentials or sessions that were committed and coordinate history cleanup separately.
