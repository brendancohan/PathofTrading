> **WARNING:** An LLM was used to assist in this tool. Trigger warning for things like stupid redundant token wasting emojis in the installation script for example.

# Path of Trading v1.0

![Downloads](https://img.shields.io/github/downloads/brendancohan/PathofTrading/total?style=for-the-badge&color=blue)

A high-performance, Wayland-native Path of Exile 2 price-checking overlay. Built specifically for Linux users, this tool provides instant market pricing without the heavy overhead of Electron, utilizing the Quickshell QtQuick compositor framework for a seamless, native desktop experience.

## Features
- **Native Wayland Overlay:** Blazing fast rendering directly on your desktop via Quickshell.
- **Smart Bulk Price Checking:** Instantly fetch market averages for stackable items (Currency, Omens, Essences, Runes, Soul Cores, etc.) via `poe.ninja`—costing **zero** GGG API limit quota.
- **Accurate Live Market Data:** Complex gear and Waystones are parsed and queried against the live GGG Trade API using strict Instant Buyout ("Securable") market states.
- **Intelligent Stat Parsing:** Automatically translates localized stats (e.g., "30% reduced attribute requirements") and aggregates elemental resistances into streamlined search parameters.
- **Live GGG Rate Limit Sync:** Directly parses GGG's `X-Rate-Limit-Ip-State` headers. It perfectly tracks your 30/300s search quota and prevents the dreaded 30-minute IP lockouts, even factoring in concurrent browser searches.
- **Dynamic League Sync:** Automatically detects current Challenge Leagues and updates available options without needing manual code edits.
- **Wayland Clipboard Safe:** Uses kernel-level macro injection (`ydotool`) and an active polling loop to bypass Wayland/XWayland Proton clipboard synchronization races.

---

## Prerequisites
Because this is a native Linux tool, it requires a few system-level packages to function.

You must install the following via your distribution's package manager:
- `python3` and `pip`
- `wl-clipboard` (for Wayland clipboard interactions)
- `ydotool` (for kernel-level key automation)
- `quickshell` (for the UI overlay)

**Example for Arch Linux:**
```bash
sudo pacman -S python python-pip wl-clipboard ydotool
yay -S quickshell-git
```

### Important: Ydotool Setup
Because `ydotool` interacts directly with the Linux kernel via `uinput`, its background daemon must be running and accessible by your user.
Add the following to your Window Manager startup config (e.g., `hyprland.conf` or `autostart.conf`):
```bash
exec-once = ydotoold --socket-path=$XDG_RUNTIME_DIR/.ydotool_socket --socket-own=$(id -u):$(id -g)
```

---

## Installation

1. Clone or download this repository.
2. Run the included automated installer:
   ```bash
   cd pathoftrading-v1.0
   ./install.sh
   ```
3. The installer will create a private Python virtual environment (so it doesn't conflict with your system packages) and create a global executable symlink called `pathoftrading`.
4. **Automated Setup:** During installation, the script will ask if you want to automatically add the `CTRL+ALT+D` hotkey to your Window Manager configuration (supports Hyprland and Sway). You can also skip this to map it manually.

---

## Usage (Window Manager Setup)

This tool is designed to work universally across Linux environments (**Hyprland, Sway, KDE Plasma, GNOME, and X11**). 

If you chose to skip the automated hotkey mapping during installation, you simply need to bind the `pathoftrading` command to a keyboard shortcut using your system's standard settings.

**Important:** We highly recommend using a "Bind on Release" setting (where possible) to prevent your physical modifier keys from interfering with the automated `Ctrl+C` macro.

### Manual Configuration Examples:

**Hyprland (`~/.config/hypr/hyprland.conf`):**
```text
bindr = CTRL_ALT, D, exec, ~/.local/bin/pathoftrading
```

**Sway (`~/.config/sway/config`):**
```text
bindsym --release Mod1+Ctrl+d exec ~/.local/bin/pathoftrading
```

**KDE Plasma & GNOME:**
Go to your System Settings -> Keyboard -> Custom Shortcuts. Create a new shortcut, set the trigger to `Ctrl+Alt+D`, and set the action/command to `~/.local/bin/pathoftrading`.

### How to Price Check:
1. Hover your mouse over any item in Path of Exile 2.
2. Press and release your hotkey (e.g., `CTRL + ALT + D`).
3. The Path of Trading UI will instantly pop up. You can toggle specific modifiers on/off and click "Requery Trades" to narrow down the live market.
4. Click anywhere outside the window or press `ESC` to close it.

---

## Troubleshooting & Logs
If the tool isn't responding or you are experiencing issues with items not copying, you can check the global debug log:
```bash
cat ~/.cache/pathoftrading-v1.0/script.log
```

## Credits & Acknowledgements
This project was made possible by the incredible open-source tools and data provided by the Path of Exile community:

*   **[Exiled Exchange 2](https://github.com/Kvan7/Exiled-Exchange-2):** A core inspiration for the standalone architecture and best-practice management of the strict GGG API 300-second lockout windows.
*   **[Quickshell](https://github.com/quickshell-mirror/quickshell):** Wayland/QtQuick rendering engine that makes this native, lightweight UI possible.
*   **[Ydotool](https://github.com/ReimuNotMoe/ydotool):** Linux kernel-level input automation tool that allows us to securely bypass Proton/Wayland clipboard limitations.
*   **[poe.ninja](https://poe.ninja):** Utilized here to provide live, zero-quota bulk item pricing.
*   **[RePoE](https://github.com/brather1ng/RePoE):** Data structures of Path of Exile items. 
