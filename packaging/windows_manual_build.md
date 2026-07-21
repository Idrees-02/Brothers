# Building the Windows installer manually

Use this if you don't want to rely on the GitHub Actions workflow
(`.github/workflows/build-windows.yml`). Do this on an actual Windows PC.

## 1. Install prerequisites
- [Python 3.11+](https://www.python.org/downloads/) (check "Add python.exe to PATH" during install)
- [Inno Setup 6](https://jrsoftware.org/isdl.php)

## 2. Get the project
Copy the whole project folder onto the Windows machine (or `git clone` it).

## 3. Install Python dependencies
Open a terminal (PowerShell or cmd) in the project folder:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

## 4. Build the app with PyInstaller

```
pyinstaller packaging\brothers.spec
```

This produces `dist\Brothers\Brothers.exe` plus its supporting files.

## 5. Build the installer with Inno Setup

Open `packaging\inno\setup.iss` in the Inno Setup Compiler and click **Compile**,
or from the command line (adjust the path if Inno Setup installed elsewhere):

```
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" packaging\inno\setup.iss
```

The finished installer is written to `packaging\inno\Output\BrothersSetup.exe`.

## 6. Test before shop rollout

Run `BrothersSetup.exe` on a clean Windows machine (or a VM), confirm:
- The app launches and shows the Arabic RTL login screen.
- Log in with the seeded admin account (see the main README) and change the
  password and override password immediately from Settings.
- Create one of each invoice type, print/export a PDF, and confirm Arabic
  text renders correctly.
- Confirm the database file is created under `%APPDATA%\Brothers\brothers.db`
  and survives closing/reopening the app.
