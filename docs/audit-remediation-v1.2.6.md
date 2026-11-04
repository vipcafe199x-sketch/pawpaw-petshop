# v1.2.6 — Audit remediation and rollout notes

## Scope

- Checkout carries an idempotency key and delivery note. The database saves the request result in the same transaction as the order and stock changes. Reusing a key for a different payload is rejected. If the network outcome is uncertain, the browser checks the result or retries the same request. Older API clients that omit the key do not receive the deduplication guarantee.
- Admin search escapes user-controlled text. Guest lookup returns fewer fields and is rate-limited; registration is rate-limited and password hashing runs outside the event loop. Limits are process-local and depend on a correctly configured trusted proxy. **Guest OTP and admin MFA remain unimplemented**, and a distributed limiter/WAF is still needed for multi-worker deployments.
- Booking validates dates and hours in Vietnam time, shows current slot availability, and releases cancelled slots. The unique index remains authoritative if two people book simultaneously. A transactional migration preserves old appointments.
- Return requests require delivered status. New deliveries store the transition time, and the current FAQ's seven-day rule is enforced. Historical delivered orders lacking a timestamp are accepted for manual date verification; no historical delivery date is invented. This policy should be confirmed by the shop owner.
- Product listing supports server-side paging and filters; the cart loads exact product IDs. The maximum slider position means unlimited.
- Backup script includes database and uploads. A proposed safe-release script retains the old container until health checks succeed, with rollback on failure. It is not wired into the existing tag workflow in this PR.

## Important rollout limits

- **Do not tag or release this PR yet.** The GitHub integration could not update workflow files, so the existing tag deploy workflow is unchanged and does not use the proposed safe-release script. Workflow permissions and a reviewed CI/deploy update are required. Production-like staging and a backup/restore rehearsal are also required. The script has only been tested with simulated Docker, not a real production host.
- The proposed deployment guard creates a database backup before migration when invoked. The new schema is intended to remain readable by the previous application version, but rollback does **not** automatically restore the database; restore only after assessing subsequent writes, to avoid losing data.
- Pause writes for a consistent database-and-upload backup. The script does not encrypt or copy the backup off-site; the operator must do so, schedule backups, and test restoration.
- CSRF/request limits and idempotency do not replace monitoring, MFA, OTP, WAF or penetration testing. Do not claim a full security audit.
- The seven-day return rule uses the recorded transition to delivered, which may differ from the actual carrier delivery time; reconcile and confirm this policy before relying on it.
