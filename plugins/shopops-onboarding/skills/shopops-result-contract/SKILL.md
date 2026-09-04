---
name: shopops-result-contract
description: Analyze an explicitly selected external SOP project, draft and validate its ShopOps result contract, and submit the confirmed immutable contract for administrator review.
---

Act only when the developer explicitly invokes this skill for a specific project. This skill extends
`shopops-onboarding`; it does not create a second plugin and it never executes business code.

## Safety boundary

- Confirm the intended project root before reading files.
- Read only source files, README or other project documentation, tests, package manifests, and
  explicitly identified output schemas or representative samples. Do not read `.env`, credentials,
  cookies, tokens, private keys, browser profiles, production databases, or arbitrary historical
  output directories.
- Never upload source code or sample business data. ShopOps receives only the result contract and,
  during later Reporter runs, fields and artifacts explicitly allowed by that contract.
- Generate declarations only. Never generate or run an adapter script, `eval`, template expression,
  dynamic import, shell command, or other executable mapping.
- Do not run the SOP itself. A test run is a separate developer action.

## Contract workflow

1. Verify `shopops-report --json status` reports Reporter `0.3.0` or newer and locate the existing
   `.shopops/integration.yaml`. If the Reporter is older, stop and direct the developer to invoke
   `$shopops-update`; do not update it from this skill.
2. Inspect the allowed project files and identify:
   - the process entry point and stable project or script version;
   - the files produced on a completed, partial, no-change, and failed run;
   - the business status field and its exact source values;
   - a short headline, optional description, bounded metrics and details;
   - material completion claims and the log or artifact evidence supporting each claim;
   - full artifacts that should remain available in ShopOps.
3. Ask the developer about every ambiguous status, field meaning, unit, privacy class, or completion
   rule. Never infer a business failure from a field name or from exit code zero.
4. Present the proposed contract before writing. Use stable English keys and separate Chinese labels.
   Every metric, detail, claim, and artifact must declare exactly one visibility:
   `public`, `internal`, `sensitive`, or `forbidden`. Sensitive and forbidden values are never included
   in the mapped run result.
5. After explicit confirmation, write `.shopops/result-contract.yaml` with schema
   `shopops.result_contract.v1`. Use only normalized project-relative sources of type `json`, `csv`,
   `xlsx`, or bounded `text`. JSON selectors are RFC 6901 pointers; tabular selectors are exact column
   names; text selectors are limited to `text`, `line_count`, or `contains:<literal>`.
6. Add four sanitized fixtures under `.shopops/result-samples/` covering `completed`, `partial`,
   `no_change`, and `failed`, and reference them from `samples`. Fixtures must describe shape and
   expected status without containing live business records or secrets.
7. Run `shopops-report --json result-contract validate --project-dir <project-root>`. Resolve all
   validation failures without weakening the privacy boundary. Then run
   `shopops-report --json result-contract preview --project-dir <project-root>` only if current output
   files are explicitly approved for local inspection. Preview does not upload the output.
8. Show the exact contract digest, project fingerprint, fields, completion mapping, warnings, and
   sample coverage. Wait for explicit confirmation of that digest before submission.
9. Submit with `shopops-report --json result-contract submit --project-dir <project-root>`. Report the
   returned immutable version and `pending` review status. The project may run while pending, but its
   results are marked unverified until a ShopOps administrator approves that exact version.

When project source or result shape changes, create and submit a new contract version. Never overwrite
or claim to amend an already submitted version.
