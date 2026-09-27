# QuotaTray 0.8.0

QuotaTray is an unofficial Windows tray monitor for OpenAI Codex usage limits.

## Highlights

- Shows the remaining five-hour quota in the tray icon and weekly quota in the tooltip.
- Supports the weekly exhausted display override and local Codex App Server integration.
- Stores quota history locally in SQLite.
- Does not parse `auth.json`, access browser cookies, or send QuotaTray telemetry.
- Installs per user on Windows x64.

## Requirements

- Windows x64.
- OpenAI Codex installed and authenticated for the same Windows user.
- Microsoft Visual C++ Redistributable x64 14.44 or newer.

## Distribution notes

The installer is currently unsigned, so Windows SmartScreen may display a warning. Verify the installer against `SHA256SUMS.txt` from the QuotaTray v0.8.0 GitHub Release.

QuotaTray is an unofficial third-party project and is not affiliated with or endorsed by OpenAI. QuotaTray source is licensed under MIT. Third-party components retain their respective licenses; see `THIRD_PARTY_NOTICES.md` and `licenses/`.
