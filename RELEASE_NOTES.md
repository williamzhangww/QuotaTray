# QuotaTray 0.8.2

An unofficial Windows tray monitor for OpenAI Codex usage limits.

## Highlights

- Normally displays the 5-hour remaining quota in the Windows tray icon.
- When Weekly remaining falls below 10%, switches the tray number to Weekly remaining and uses a red background with black text.
- At 10% or above, returns to the normal 5-hour display and colors. Missing Weekly data does not trigger the warning state.
- Weekly 0% retains the exhausted behavior: the tray shows `0` and the tooltip hides the 5-hour block.
- Displays reset credits when available.
- Continues using `%LOCALAPPDATA%\QuotaTray` and does not migrate data from the earlier CodexUsageMonitor namespace.

## Requirements

- Windows x64.
- OpenAI Codex installed and authenticated for the same Windows user.
- Microsoft Visual C++ Redistributable x64, version 14.44 or newer.

## Privacy

QuotaTray does not read Codex `auth.json` credentials or browser cookies. It does not collect prompts, conversations, source code, or user files. QuotaTray has no first-party telemetry.

## Installer

- File: `QuotaTray-0.8.2-Setup.exe`
- SHA256: `810857171324E0658CBC7173F9652A28357553CEBF25122D8B12F63BCD3DE5FA`
- The installer is unsigned. Windows SmartScreen may display a warning.
- Verify the download against `SHA256SUMS.txt` on the [v0.8.2 GitHub Release](https://github.com/williamzhangww/QuotaTray/releases/tag/v0.8.2).

The Qt and PySide6 LGPL source archives corresponding to the bundled runtime are included with the release. QuotaTray source code is licensed under MIT; third-party components retain their respective licenses.

## Disclaimer

QuotaTray is an independent, unofficial third-party project. It is not affiliated with, endorsed by, or sponsored by OpenAI.

---

# QuotaTray 0.8.1

An unofficial Windows tray monitor for OpenAI Codex usage limits.

## Highlights

- Shows remaining 5-hour quota directly in the Windows tray icon and Weekly quota in the tooltip.
- Shows `0` in the tray when the Weekly quota is exhausted.
- Displays reset credits when available.
- Stores quota history and settings locally under `%LOCALAPPDATA%\QuotaTray`.
- Reads quota through the local Codex App Server `account/rateLimits/read` method.
- Uses the clean QuotaTray program and data namespace. It does not migrate settings or history from earlier product versions.

## Requirements

- Windows x64.
- OpenAI Codex installed and authenticated for the same Windows user.
- Microsoft Visual C++ Redistributable x64, version 14.44 or newer.

## Privacy

QuotaTray does not read Codex `auth.json` credentials or browser cookies. It does not collect prompts, conversations, source code, or user files. QuotaTray has no first-party telemetry.

## Installer

- File: `QuotaTray-0.8.1-Setup.exe`
- SHA256: `61C748DB389492447F8ACCB764FA16C646159C46240B2C392436942DAB47C4C0`
- The installer is unsigned. Windows SmartScreen may display a warning.
- Verify the download against `SHA256SUMS.txt` on the [v0.8.1 GitHub Release](https://github.com/williamzhangww/QuotaTray/releases/tag/v0.8.1).

The Qt and PySide6 LGPL source archives corresponding to the bundled runtime are included with the release. QuotaTray source code is licensed under MIT; third-party components retain their respective licenses.

## Disclaimer

QuotaTray is an independent, unofficial third-party project. It is not affiliated with, endorsed by, or sponsored by OpenAI.
