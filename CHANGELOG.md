# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
where applicable.

## [Unreleased]

### Security

- Private structured error events and access logs without reset tokens or request data.
- Signed, expiring email verification and throttled password reset requests.

- Shared login/admin/registration throttling with hashed identifiers.
- Fail-closed production secret and host validation, strict CSP and private caching.
- Bounded request bodies and note lengths.
- Removed local SQLite database from Git tracking without deleting local data.

### Added

- Restorable trash, owner-scoped projects/tags, recurrence with month-end anchors, and subtasks.
- Account preferences, password recovery, verified-email opt-in reminders, and per-user timezones.
- Turkish UI, installable PWA, and a generic offline fallback without cached private data.
- SQLite backup/restore commands and scheduled off-host backup/recovery rehearsals.
- Navy/lavender palette and refreshed sample-data demo.

- Quick-add due dates, priority/undated filters, and selectable page sizes.
- Task duplication, tomorrow/next-week scheduling, and save-and-add-another.
- CSV export with formula-text protection, expandable notes, and keyboard shortcuts.
- Quick task capture, today/upcoming views, and configurable sorting.
- Private JSON export and configurable application time zone.
- Preserved list context after task edits/status changes and resilient pagination.
- Responsive Daymark workspace with progress summaries and accessible forms.
- Task priorities, optional due dates, overdue filters, search, and pagination.
- POST-only, retry-safe task completion and reopening.
- Database-aware health endpoint and regression tests.
- Legacy database import with conflict detection and backup documentation.

### Fixed

- Enforced task ownership for detail, update, delete, and status operations.
- Escaped search field attributes and corrected logout to use a CSRF-protected POST.
- Corrected nested login redirects and preserved safe return URLs.
- Imported existing task records without changing ownership or timestamps.

<!--
When preparing a release, move relevant entries from Unreleased into a dated
version section. Use Added, Changed, Deprecated, Removed, Fixed, and Security
headings as appropriate.
-->
