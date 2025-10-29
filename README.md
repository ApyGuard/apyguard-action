# ApyGuard GitHub Action

Run ApyGuard’s cloud-based API DAST scanner from your CI and surface the results on the ApyGuard platform.


> TL;DR: This action triggers a scan on ApyGuard Cloud for a publicly reachable target (your preview/staging/prod URL). The job can optionally wait for completion, gate merges on a severity threshold, and output links to the final report.

## What is ApyGuard?

ApyGuard is an automated API security scanner that checks your API endpoints for vulnerabilities, including the [OWASP API Top 10](https://owasp.org/www-project-api-security/).

## How This Action Works

1. The action calls ApyGuard’s API to create a DAST scan for your target.
2. ApyGuard’s cloud scanner reaches your target over the public Internet.
3. Results are viewable in the ApyGuard UI; the action can also poll for completion and fail the job if findings meet your threshold. 

>Important: Your target must be publicly reachable by ApyGuard’s scanners. If it’s behind a VPN, private IP, or blocked by WAF rules, the scan will fail. See Networking requirements. 

## Requirements
- An **ApyGuard account** with active subscription.
- An **API Key** to create scan.
- A **scan task** with proper configuration (server URL, authorization, custom headers etc.)
- A **publicly reacheable target URL** (e.g preview env, staging, or production).

## Sample Usage

```yaml
name: Run ApyGuard Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Run ApyGuard API Scanner
        uses: apyguard/apyguard-action@v1
        with:
          api_key: ${{ secrets.APYGUARD_API_KEY }}
          task_id: ${{ secrets.APYGUARD_TASK_ID }}
          api_url: "https://example-api.apyguard.com/v1/"  # Optional, defaults to production URL
          severity_threshold: "Medium" # Optional, default value "Medium"
```

## Networking Requirements
- **Public reachability**: Target must be reachable from the Internet.
- **DNS & TLS**: Ensure DNS resolves and TLS certs are valid
- **Access controls**: If protected by WAF, IP allowlists, configure exceptions for the scanner
- **Rate limiting**: Scans can be request-intensive; consider relaxing rate limits during scan windows.

## Permissions
This action only calls HTTP APIs. It doesn't require elevated GitHub token permissions. If you use any secrets/keys, keep the default **Github** token permissions minimal. 

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| api_key | Yes | Your ApyGuard API token |
| task_id | Yes | The task ID from ApyGuard platform |
| api_url | No | Custom API endpoint URL (defaults to production) |
| severity_threshold | No | Custom severity threshold (default value "Medium") |

## Outputs

| Output | Description |
|--------|-------------|
| results | JSON string containing the scan results |

## Troubleshooting
### Scan can't reach target
- Verify the URL is public and resolves via DNS.
- Check WAF/firewall and allow the scanner
- Ensure TLS cert chain is valid

### 401/403 from ApyGuard API
- Confirm **api_key**, **task_id** and **api_url** is valid.
- Ensure your ApyGuard subscription is active.

## License

This project is licensed under the **MIT License**.

Copyright (c) 2025 **ApyGuard**.

---

## Support and Documentation

| Area                        | Link / Contact                                                                                                            |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| **General Issues**          | [GitHub Issues](https://github.com/ApyGuard/apyguard-action/issues)                                                      |
| **Discussions & Questions** | [GitHub Discussions](https://github.com/ApyGuard/apyguard-action/discussions)                                            |
| **Security Reporting**      | Use [GitHub Security Advisories](https://github.com/ApyGuard/apyguard-action/security) or email `security@apyguard.com`. |

---

Made with ❤️ by ApyGuard
