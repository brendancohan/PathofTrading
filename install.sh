#!/bin/bash

echo "======================================"
echo "  Path of Trading v1.0 - Installer"
echo "======================================"

# 1. Dependency Checks
MISSING_DEPS=0
for cmd in python3 pip wl-paste ydotool quickshell; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ Missing dependency: $cmd"
        MISSING_DEPS=1
    else
        echo "✅ Found: $cmd"
    fi
done

if [ $MISSING_DEPS -eq 1 ]; then
    echo ""
    echo "Please install the missing dependencies before continuing."
    echo "For example, on Arch Linux:"
    echo "  sudo pacman -S python python-pip wl-clipboard ydotool"
    echo "  yay -S quickshell-git"
    exit 1
fi

echo ""
echo "⚙️  Setting up installation directory..."
INSTALL_DIR="$HOME/.local/share/pathoftrading-v1.0"
mkdir -p "$INSTALL_DIR"

# Copy files
echo "📂 Copying files to $INSTALL_DIR..."
cp backend.py "$INSTALL_DIR/"
cp PathofTrading.qml "$INSTALL_DIR/"
cp run_pricecheck.sh "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/run_pricecheck.sh"

echo "🐍 Creating Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate

echo "🔗 Creating global symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/run_pricecheck.sh" "$HOME/.local/bin/pathoftrading"

# Warn user if ydotool is not running/owned
YDOTOOL_SOCK="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket"
if [ ! -S "$YDOTOOL_SOCK" ]; then
    echo "⚠️  ydotool socket not found at $YDOTOOL_SOCK."
    echo "   Ensure 'ydotoold' is running as a user service for the macro to work."
    echo "   You can add this to your startup config:"
    echo "   ydotoold --socket-path=\$XDG_RUNTIME_DIR/.ydotool_socket --socket-own=\$(id -u):\$(id -g)"
fi

echo ""
echo "✅ Installation Complete!"
echo "--------------------------------------"
echo "Would you like to automatically map a hotkey to your Window Manager?"
echo "1) Hyprland"
echo "2) Sway"
echo "3) Skip (I will map it manually, or I use KDE/GNOME/etc.)"
read -p "Select an option [1-3]: " wm_choice

case $wm_choice in
    1)
        echo ""
        echo "Enter your desired Hyprland keybind (Default: CTRL_ALT, D)"
        echo "(Note: You must literally type out the key names, e.g., 'SUPER, D'. Do NOT physically press the combination.)"
        read -p "> " raw_bind
        
        custom_bind=${raw_bind:-"CTRL_ALT, D"}
        
        # Sanitize input to remove weird terminal control characters if the user hit a macro by mistake
        custom_bind=$(echo "$custom_bind" | tr -cd '[:print:]')
        if [ -z "$custom_bind" ] && [ -n "$raw_bind" ]; then
            echo "⚠️  Invalid input detected (likely a physical keypress instead of typed text)."
            echo "✅ Falling back to default: CTRL_ALT, D"
            custom_bind="CTRL_ALT, D"
        elif [ -n "$raw_bind" ]; then
            echo "✅ Using custom keybind: $custom_bind"
        else
            echo "✅ Using default keybind: CTRL_ALT, D"
        fi
        
        HYPR_CONF="$HOME/.config/hypr/hyprland.conf"
        KEY_CONF="$HOME/.config/hypr/keybindings.conf"
        KEY_CONF_ALT="$HOME/.config/hypr/config/keybindings.conf"
        
        if [ -f "$KEY_CONF_ALT" ]; then
            echo -e "\n# Path of Trading\nbindr = $custom_bind, exec, $HOME/.local/bin/pathoftrading" >> "$KEY_CONF_ALT"
            echo "✅ Added hotkey to $KEY_CONF_ALT"
        elif [ -f "$KEY_CONF" ]; then
            echo -e "\n# Path of Trading\nbindr = $custom_bind, exec, $HOME/.local/bin/pathoftrading" >> "$KEY_CONF"
            echo "✅ Added hotkey to $KEY_CONF"
        elif [ -f "$HYPR_CONF" ]; then
            echo -e "\n# Path of Trading\nbindr = $custom_bind, exec, $HOME/.local/bin/pathoftrading" >> "$HYPR_CONF"
            echo "✅ Added hotkey to $HYPR_CONF"
        else
            echo "⚠️ Could not find Hyprland config files. Please add manually:"
            echo "bindr = $custom_bind, exec, $HOME/.local/bin/pathoftrading"
        fi
        
        if command -v hyprctl &> /dev/null; then
            echo "🔄 Reloading Hyprland configuration..."
            hyprctl reload &> /dev/null
            echo "✅ Hyprland reloaded!"
        fi
        ;;
    2)
        echo ""
        echo "Enter your desired Sway keybind (Default: Mod1+Ctrl+d)"
        echo "(Note: You must literally type out the key names, e.g., 'Mod4+d'. Do NOT physically press the combination.)"
        read -p "> " raw_bind
        
        custom_bind=${raw_bind:-"Mod1+Ctrl+d"}
        
        # Sanitize input to remove weird terminal control characters
        custom_bind=$(echo "$custom_bind" | tr -cd '[:print:]')
        if [ -z "$custom_bind" ] && [ -n "$raw_bind" ]; then
            echo "⚠️  Invalid input detected (likely a physical keypress instead of typed text)."
            echo "✅ Falling back to default: Mod1+Ctrl+d"
            custom_bind="Mod1+Ctrl+d"
        elif [ -n "$raw_bind" ]; then
            echo "✅ Using custom keybind: $custom_bind"
        else
            echo "✅ Using default keybind: Mod1+Ctrl+d"
        fi
        
        SWAY_CONF="$HOME/.config/sway/config"
        if [ -f "$SWAY_CONF" ]; then
            echo -e "\n# Path of Trading\nbindsym --release $custom_bind exec $HOME/.local/bin/pathoftrading" >> "$SWAY_CONF"
            echo "✅ Added hotkey to $SWAY_CONF"
        else
            echo "⚠️ Could not find Sway config. Please add manually:"
            echo "bindsym --release $custom_bind exec $HOME/.local/bin/pathoftrading"
        fi
        
        if command -v swaymsg &> /dev/null; then
            echo "🔄 Reloading Sway configuration..."
            swaymsg reload &> /dev/null
            echo "✅ Sway reloaded!"
        fi
        ;;
    *)
        echo "Skipping automatic hotkey mapping."
        echo "To use Path of Trading, bind the 'pathoftrading' command to a hotkey."
        echo "Example for KDE/GNOME: Set 'pathoftrading' as the action for a Custom Shortcut."
        ;;
esac
echo "--------------------------------------"
