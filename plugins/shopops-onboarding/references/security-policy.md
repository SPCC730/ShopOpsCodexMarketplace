# ShopOps Reporter WP1 Security Policy

WP1 is intentionally limited to local Reporter installation and read-only
diagnosis. It supports Apple Silicon macOS and Windows x64 with CPython 3.11 and
newer Python 3 versions. The current checksum-locked release contains wheelhouses
for 3.11, 3.12, 3.13, and 3.14; a newer interpreter must wait for its own
wheelhouse rather than reuse a different CPython ABI.

## Authorization

An explicit onboarding request can use doctor/update/contract subflows without
requiring the developer to name each skill. Those subflows retain their own
operation scope. Existing authorization for an unchanged concrete operation
remains valid. Installation
must run `probe` and `install-preview`, show the exact locked version and paths,
then stop for explicit developer confirmation of that version before `install`.
An unversioned request is not exact-version confirmation. The installer uses the bundled
wheelhouse with `pip --no-index`; it must not contact PyPI.

Doctor is reporting-only. It can probe, validate the locked preview, inspect the
Reporter runtime and stable shim, and request `--json status`; it must never
install, repair, remove, enroll, pair, or otherwise alter Reporter state.

## Scope

The unified guided workflow is unreleased and capability-gated; bundled 0.4.2
does not provide it. Its confirmed local scope may be analyzed and configured
as described in [guided-onboarding.md](guided-onboarding.md). Output-only edits,
contract submission and an individual real run have distinct concrete plans.
Batch onboarding never authorizes batch execution. Completion requires fresh
server evidence for the session's run, frozen contract and required artifacts.

WP1 never scans, connects to, or executes a business project. It includes no
MCP service, UI, browser extension, lifecycle hook, device enrollment, Reporter
cleanup command, publishing, push, or merge operation.

## Retention and Cleanup

Removing the Codex plugin does not remove the independent Reporter runtime,
device identity, queue, or project launch capability. Reporter cleanup is a
separate explicit operation outside WP1. Before any such future cleanup, it must
preview all affected runtime versions, device identity, queued runs, and
projects, then wait for explicit confirmation.
