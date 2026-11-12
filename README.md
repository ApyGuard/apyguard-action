# ApyGuard GitHub Action

Report the API changes in each pull request, and run ApyGuard's cloud-based API DAST scanner after you deploy.

> TL;DR: `mode: pr` builds the OpenAPI document of your API from its code on the base and head of a pull request, compares them, and comments with the endpoints the pull request adds or changes and the APIScout findings on them. `mode: scan` starts an ApyGuard scan task against your deployed API and gates the job on a severity threshold.

## What is ApyGuard?

ApyGuard is an automated API security scanner that checks your API endpoints for vulnerabilities, including the [OWASP API Top 10](https://owasp.org/www-project-api-security/).

## How This Action Works

### `mode: pr`

1. The action builds an OpenAPI document from the pull request's code with the APIScout engine, and another from its base commit. A spec file in the repository is read when APIScout recognizes no framework.
2. It compares the two and lists the endpoints the pull request adds, changes or removes.
3. It comments on the pull request with that list and the APIScout findings on the added and changed endpoints, and updates the same comment on each push. The report is also in the job summary.
4. The job fails when a finding is at `severity_threshold` or above (APIScout findings are High, Medium or Low).

Nothing is sent to ApyGuard in this mode: the code and the documents built from it stay on the runner. The engine and PyYAML, its one dependency, are installed from the action's `vendor/` folder without contacting a package index, and the action calls only the GitHub API, to comment.

APIScout reads Django, Express, FastAPI, Flask, NestJS, oRPC and Spring Boot (Java) projects.

### `mode: scan`

1. The action calls ApyGuard's API to start the scan task you created for CI/CD.
2. ApyGuard's cloud scanner reaches your target over the public Internet.
3. The action waits for the scan to finish (`timeout_minutes`) and fails the job if findings meet your threshold. Results are in the ApyGuard UI.

>Important: Your target must be publicly reachable by ApyGuard's scanners. If it's behind a VPN, private IP, or blocked by WAF rules, the scan will fail. See Networking requirements.

## Requirements

`mode: pr`
- A Linux X64 runner (`ubuntu-latest`).
- `actions/checkout` before this action, without `ref:` so the pull request's merge commit is checked out, and with `persist-credentials` left on (its default) so the action can fetch the base commit.
- `pull-requests: write` permission to comment. On pull requests from forks the token is read-only: the action then warns and the report stays in the job summary.

`mode: scan`
- An **ApyGuard account** with active subscription.
- An **API Key** to create scan.
- A **scan task** with proper configuration (server URL, authorization, custom headers etc.)
- A **publicly reacheable target URL** (e.g preview env, staging, or production).

Both modes run on Python 3.13 set up by `actions/setup-python`, which also becomes the job's `python` for the steps after this one.

## Sample Usage

```yaml
name: ApyGuard

on:
  pull_request:
  push:
    branches: [main]

jobs:
  api-changes:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v7
      - uses: ApyGuard/apyguard-action@v2
        with:
          mode: pr
          project_path: .           # Folder of the API project
          severity_threshold: High

  scan:
    needs: deploy                   # Your job that deploys the API
    runs-on: ubuntu-latest
    steps:
      - uses: ApyGuard/apyguard-action@v2
        with:
          mode: scan
          api_key: ${{ secrets.APYGUARD_API_KEY }}
          task_id: YOUR_TASK_ID
          severity_threshold: Medium
```

The whole workflow is in [examples/apyguard.yml](examples/apyguard.yml).

## Networking Requirements
- **Public reachability**: Target must be reachable from the Internet.
- **DNS & TLS**: Ensure DNS resolves and TLS certs are valid
- **Access controls**: If protected by WAF, IP allowlists, configure exceptions for the scanner
- **Rate limiting**: Scans can be request-intensive; consider relaxing rate limits during scan windows.

## Permissions
`mode: scan` only calls the ApyGuard API and needs no GitHub token permissions. `mode: pr` needs `pull-requests: write` to comment; keep the rest of the token's permissions minimal.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| mode | No | `pr` or `scan` (default `scan`) |
| api_key | In scan mode | Your ApyGuard API token |
| task_id | In scan mode | The task ID from ApyGuard platform |
| api_url | No | ApyGuard API URL (default `https://api.apyguard.com`) |
| severity_threshold | No | Fail at this severity or above: Critical, High, Medium, Low, Informational (default `Medium`) |
| project_path | No | pr mode: folder of the API project, relative to the repository root (default `.`) |
| github_token | No | pr mode: token that comments on the pull request (default `github.token`) |
| timeout_minutes | No | scan mode: how long to wait for the scan (default `120`) |

## Outputs

| Output | Description |
|--------|-------------|
| changed_endpoint_count | pr mode: endpoints the pull request adds or changes |
| finding_count | pr mode: APIScout findings on those endpoints |
| results | scan mode: vulnerability counts by severity, as JSON |

## Moving from v1
- `api_url` defaults to `https://api.apyguard.com`; drop a `/v1` suffix if you set one.
- `api_key` and `task_id` are still required for scans; with `mode: pr` they are not used.
- A scan that ends as Failed, Stopped or Cancelled now fails the job with its reason, and a scan that runs past `timeout_minutes` fails it too.
- v1 stays available as `@v1.0.0`.

## Troubleshooting
### Scan can't reach target
- Verify the URL is public and resolves via DNS.
- Check WAF/firewall and allow the scanner
- Ensure TLS cert chain is valid

### 401/403 from ApyGuard API
- Confirm **api_key**, **task_id** and **api_url** is valid.
- Ensure your ApyGuard subscription is active.

### APIScout found no API endpoints
- Set `project_path` to the folder that holds the API project.
- Check that the framework is one APIScout reads, or keep an OpenAPI file in that folder.

## License

The action's own code is licensed under the **Apache License 2.0** ([LICENSE](LICENSE)).

The APIScout Engine wheel in `vendor/` is proprietary to Atlada Cyber Security and is not covered by that license: it may be used only as part of this action, and may not be used on its own or redistributed. See [NOTICE](NOTICE).

PyYAML, also in `vendor/`, is distributed unmodified under its own MIT license, which is inside its wheel.

Copyright 2025-2026 **Atlada Cyber Security**.

---

## Support and Documentation

| Area                        | Link / Contact                                                                                                            |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| **General Issues**          | [GitHub Issues](https://github.com/ApyGuard/apyguard-action/issues)                                                      |
| **Discussions & Questions** | [GitHub Discussions](https://github.com/ApyGuard/apyguard-action/discussions)                                            |
| **Security Reporting**      | Use [GitHub Security Advisories](https://github.com/ApyGuard/apyguard-action/security) or email `security@apyguard.com`. |

---

Made with ❤️ by ApyGuard
