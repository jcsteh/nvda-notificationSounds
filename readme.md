# Notification Sounds Add-on for NVDA

- Copyright 2026 James Teh
- License: GNU General Public License, version 2 or later

Notification Sounds plays a chosen wav file when a Windows notification matches text you configure.

## Configuring notification sounds

In NVDA, open the Settings dialog and select the **Notification sounds** category.
The list shows each rule's text, sound file and matching options.

Use **Add** or **Edit** to configure:

- The text a notification must contain.
- Whether that text is plain text or a regular expression.
- Whether matching is case sensitive.
- The wav file to play.

Use **Remove** to delete a rule.
Changes are written only when you press the OK or Apply button.
Rules are checked in the order they are listed.
Only the first matching rule plays a sound.
