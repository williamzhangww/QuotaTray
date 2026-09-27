# Security policy

## Reporting a vulnerability

Please do not report security vulnerabilities in a public issue. Use GitHub's private vulnerability reporting feature for this repository.

The repository owner must create the public repository and enable GitHub Private Vulnerability Reporting before making the repository public. Until it is enabled, do not publish the repository or invite vulnerability reports through public issues.

Include the affected QuotaTray version, Windows version, steps to reproduce, and impact. Do not include credentials, tokens, private Codex data, or unrelated personal information.

## Supported versions

Security fixes are intended for the latest public stable release. QuotaTray 0.8.0 is a release candidate for public preparation and is not currently published as a public release.

## Scope

QuotaTray is a local Windows tray application. It starts the user's installed Codex App Server and requests `account/rateLimits/read`. The application stores quota snapshots, logs, and settings locally. It does not implement authentication, process prompts/conversation content, read browser cookies, or provide its own telemetry or update service. Vulnerabilities in Codex, Windows, Qt, Python, and other upstream dependencies should also be reported to their respective maintainers when they affect QuotaTray's packaging or use.
