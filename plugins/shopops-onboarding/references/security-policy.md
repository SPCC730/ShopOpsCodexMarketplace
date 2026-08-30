# ShopOps Reporter WP1 Security Policy

WP1 is intentionally limited to local Reporter installation and read-only
diagnosis. It supports macOS Apple Silicon and CPython 3.11 or 3.12 only.

## Authorization

The onboarding and doctor skills run only when explicitly invoked. Onboarding
must run `probe` and `install-preview`, show the exact locked version and paths,
then stop for explicit developer confirmation of that version before `install`.
The original request is not confirmation. The installer uses the bundled
wheelhouse with `pip --no-index`; it must not contact PyPI.

Doctor is reporting-only. It can probe, validate the locked preview, inspect the
Reporter runtime and stable shim, and request `--json status`; it must never
install, repair, remove, enroll, pair, or otherwise alter Reporter state.

## Scope

WP1 never scans, connects to, or executes a business project. It includes no
MCP service, UI, browser extension, lifecycle hook, device enrollment, Reporter
cleanup command, publishing, push, or merge operation.

## Retention and Cleanup

Removing the Codex plugin does not remove the independent Reporter runtime,
device identity, queue, or project launch capability. Reporter cleanup is a
separate explicit operation outside WP1. Before any such future cleanup, it must
preview all affected runtime versions, device identity, queued runs, and
projects, then wait for explicit confirmation.
