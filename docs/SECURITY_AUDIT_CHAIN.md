# Audit hash-chain concurrency

DevPilot maintains one tamper-evident audit hash chain per workspace. The chain head must be serialized for the full database transaction that creates the next event; reading the current head and releasing a lock before commit is not sufficient.

## Write contract

`app.services.audit.record()` acquires the workspace serialization primitive before reading the current `AuditEvent.event_hash` and relies on the caller's existing commit/rollback boundary to release it.

- PostgreSQL and dialects with row locking use `SELECT ... FOR UPDATE` on the existing `workspaces` row.
- SQLite has no row-level `FOR UPDATE`, so DevPilot issues a no-op `UPDATE workspaces SET slug = slug` for the target workspace before reading the chain head. This obtains SQLite's transaction write lock. A concurrent writer must wait; if a transaction already holds a stale SQLite snapshot, SQLite may reject the write with `SQLITE_BUSY` rather than allow two events to share the same previous hash.

The lock is workspace-scoped on databases with row-level locking. SQLite naturally serializes writers at database level.

## Invariants

For committed events in one workspace:

1. the first event has an empty `previous_hash`;
2. every following event points to the immediately preceding committed event hash;
3. a transaction rollback must not publish an audit head;
4. concurrent transactions must serialize or fail, never create sibling hashes;
5. `verify_chain()` remains the verification authority for stored chains.

## Testing

`tests/test_audit_concurrency.py` holds the first SQLite audit transaction open while a second writer attempts to record an event. The second writer must remain blocked until the first transaction commits; after both commits, `verify_chain()` must report a valid two-event chain.

The same test module also compiles the PostgreSQL workspace lock statement and requires `FOR UPDATE`, protecting the production locking contract from accidental removal.
