# ES Launcher

Windows Minecraft launcher UI for Forge 1.21.11 and Fabric 1.21.11.

## Start

Double-click `ES Launcher.exe`.

## Images

Put the background image into `photos`:

- `photos/background.png`

## Nickname rule

The launcher blocks play when the nickname is empty or still set to `player`.

## Game folder

Minecraft is installed into `game\.minecraft` inside this launcher folder.
If the selected version is missing, the main button shows `СКАЧАТЬ`.
After installation it shows `ИГРАТЬ`.

## Mods

Put `.jar` mods into `mods`. They are copied to `game\.minecraft\mods` during install/start.

Version-specific mod links:

- `mods\forge-urls.txt`
- `mods\fabric-urls.txt`

Local mod folders:

- `mods\common` - for both versions
- `mods\forge` - Forge only
- `mods\fabric` - Fabric only

Some sites block automatic downloads. If a link fails, download the `.jar` manually and put it into `mods`.

## Setup EXE

Run `Build-Installer.ps1` after changing photos or mods.
It builds `ES Launcher Setup.exe`.
The setup unpacks the launcher and can prepare both Forge/Fabric versions during installation.

## RAM

Click the gear button, set RAM in MB, then save.

## Version requirement

Forge 1.21.11 and Fabric 1.21.11 can be copied from an existing `%APPDATA%\.minecraft` or downloaded into `game\.minecraft`.
