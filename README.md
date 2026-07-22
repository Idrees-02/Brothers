# الاخوين لبيع السجاد - نظام إدارة (Brothers for Selling Carpet)

Offline desktop management system for the shop: cash and installation
invoices, tax handling, expense/purchase vouchers, employee attendance and
salary reports - all in Arabic (RTL), storing data locally in SQLite. No
internet connection is required to run the app.

## Running it (development, any OS with Python 3.11+)

```
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m app.main
```

On first run the app creates its SQLite database and seeds a default admin
account:

- **username:** `admin`
- **password:** `admin123`
- **override password:** `0000`

**Change both immediately** from the Settings screen after the first login -
these defaults are documented here for setup convenience only and are not
secure to leave in place.

## Running the tests

```
pytest tests -q
```

The `tests/domain`, `tests/repositories`, and `tests/services` suites cover
tax calculation, deposit/remainder math, salary calculation, and permission/
override gating - all runnable without a display.

## Where the data lives

- Windows (packaged app): `%APPDATA%\Brothers\brothers.db`
- macOS/Linux (development): `./data/brothers.db` (gitignored)

## Building the Windows installer

The project is developed with PySide6 (Qt), which runs and can be fully
tested on macOS/Linux, but producing the final Windows `.exe` requires a
Windows build environment. Two ways to get one:

1. **GitHub Actions** (`.github/workflows/build-windows.yml`) - push a tag
   like `v1.0.0` or trigger it manually from the Actions tab; it runs the
   test suite, builds with PyInstaller, packages with Inno Setup, and
   uploads `BrothersSetup.exe` as a build artifact.
2. **Manually on a Windows PC** - see
   [packaging/windows_manual_build.md](packaging/windows_manual_build.md).

Either way, test the resulting installer on a real Windows machine before
shop rollout - it cannot be verified from a macOS/Linux dev environment.

## Project layout

- `app/db/` - SQLite schema, migrations, first-run seeding.
- `app/domain/` - pure business logic (money, tax, salary, permissions,
  password hashing) with no database or UI dependencies.
- `app/repositories/` - SQL access.
- `app/services/` - orchestrates repositories + domain logic, including the
  one-time permission-override flow.
- `app/ui/` - PySide6 screens.
- `packaging/` - PyInstaller spec and Inno Setup script.
