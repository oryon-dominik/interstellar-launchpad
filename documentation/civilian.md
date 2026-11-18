# A fresh Windows 11, ready to use

This page takes a new Windows 11 computer from its first setup screen to a working machine:
Chrome, VLC, Okular, Flameshot, GIMP and a few helpers, installed by [Scoop](https://scoop.sh),
which also updates them later. It takes about half an hour, most of it waiting.

You need the computer, an internet connection, and this page open on a second device — your
phone is fine.

## 1. Set up Windows without a Microsoft account

Windows 11 wants you to sign in with a Microsoft account during setup. You do not have to: a
local account (name and password on this computer only) works just as well.

Microsoft keeps closing the ways around that screen. Try the routes below in order; A and B take a
minute each. If none works, sign in with a Microsoft account and go on with step 2; the
launchpad works the same either way.

Whichever route you take, choose a short account name without umlauts or spaces — `hans`, not
`Hans-Jürgen`. Windows names your home folder after it, and some tools stumble over anything else.

### Route A — the "Learn more" link

1. Connect to the internet and go through setup until it asks you to sign in with a Microsoft
   account.
2. Under *Sign-in options*, look for the small **Learn more** link in the text — not the big
   buttons.
3. If it offers to create a local account, enter a name and a password. Done — go to step 2.

### Route B — the command window

1. On any setup screen, press **Shift + F10**. On many laptops it is **Fn + Shift + F10**.
   A black window opens.
2. Click into it and type exactly this, then press Enter:

   ```bat
   reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE /v BypassNRO /t REG_DWORD /d 1 /f
   ```

   It answers *The operation completed successfully.*
3. Unplug the network cable, if there is one. Then type this and press Enter — the computer
   restarts and setup begins again:

   ```bat
   shutdown /r /t 0
   ```

4. When setup asks for a network, do not pick a Wi-Fi. Choose **I don't have internet**, then
   **Continue with limited setup**. Enter a name and a password. Done — go to step 2.

If *I don't have internet* does not show up, this route is closed on your Windows: go on with
route C.

### Route C — a new installation stick

The most reliable route, but it installs Windows again from scratch. You need a second computer
and a USB stick of at least 8 GB; everything on the stick is erased.

1. On the second computer, download the Windows 11 disk image (ISO) from
   [microsoft.com/software-download/windows11](https://www.microsoft.com/software-download/windows11)
   and [Rufus](https://rufus.ie).
2. Start Rufus, choose the stick and the ISO, click **Start**.
3. Rufus asks how to customise the installation. Tick
   **Remove requirement for an online Microsoft account** and
   **Create a local account using username**, and type the name you want.
4. Start the new computer from the stick (often **F12** or **Esc** at power-on opens the boot
   menu) and install Windows. Keep the network off until you see the desktop.

## 2. Run the launchpad

1. Connect to the internet.
2. Open the start menu, type `powershell` and open **Windows PowerShell** with a normal click.
   **Not** *Run as administrator* — the launchpad stops if you do.
3. Copy this line into the blue window and press Enter:

   ```powershell
   irm https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.ps1 | iex
   ```

4. It asks who the machine is for. Choose **civilian**.
5. It shows its plan and asks *Launch? [Y/n]*. Press Enter.
6. Wait until it says **All systems go**. Close the window.

Your programs are now in the start menu.

## When something goes wrong

- **A step fails:** the launchpad names the command that failed. Run the line from step 2 again
  — everything already done is skipped, and it carries on where it stopped.
- **"Run this as your normal user, not as Administrator":** close the window and open PowerShell
  again with a normal click, as in step 2.
- **Still stuck:** take a photo of the screen and send it to whoever sent you this page.

## Later

To update every program installed here, open PowerShell and type:

```powershell
scoop update --all
```
