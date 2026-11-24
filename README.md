# run
python -m uvicorn main:app --reload

# AbbiKayGa

AbbiKayGa is a local marketplace for browsing, creating, and moderating
classified listings. It is built with FastAPI, Jinja2 templates, SQLAlchemy,
Alembic, and PostgreSQL.

## Features

- Browse approved listings and filter by keyword, category, city, and listing
  type.
- Create customer accounts, sign in, manage a profile, and manage your
  listings.
- Submit listings with images for administrator review.
- Report a listing and manage reports as an administrator.
- Require customer sign-in to submit reports; administrators can inspect
  reported listings and permanently delete listings with their reports and
  images.
- Reset administrator and customer passwords by email.
- Manage categories and listing moderation as an administrator.

## Requirements

- Python with support for the versions pinned in `requirements.txt`
- PostgreSQL
- PowerShell on Windows (commands below use PowerShell syntax)

## Local setup

Run these commands from the repository root (`E:\python1\abbikayga`):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents virtual-environment activation, either allow it for the
current terminal according to your organization's policy, or run the venv's
Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a PostgreSQL database, then create a `.env` file in the repository root.
Use the following as a template and replace every example value:

Keep `.env` private; do not commit real passwords, tokens, or SMTP credentials.
The application reads configuration from this file. Passwords containing
special characters may need URL-encoding if they cause PostgreSQL connection
URL parsing errors.

Apply the database migrations:

```powershell
python -m alembic upgrade head
```

Configure working `SMTP_*` settings in `.env`; SMTP is required for customer
signup verification and password-reset emails.

Create the initial administrator account. The bootstrap script creates an
account only when no administrator account exists. It sends a six-digit code
to `BOOTSTRAP_ADMIN_EMAIL` and creates the admin only after you enter the
verified code:

```powershell
python create_admin.py
```

## Run the application

From the repository root, start the development server with:

```powershell
python -m uvicorn main:app --reload
```

The ASGI application is `app` in the root-level `main.py` module. Therefore,
use `main:app` here—not `app.main:app`; this repository does not contain an
`app` Python package.

Open these URLs after the server starts:

- Marketplace: <http://127.0.0.1:8000/>
- API documentation: <http://127.0.0.1:8000/docs>
- Customer signup: <http://127.0.0.1:8000/customer/signup>
- Email verification: <http://127.0.0.1:8000/customer/verify-email>
- Customer sign-in: <http://127.0.0.1:8000/customer/login>
- Administrator sign-in: <http://127.0.0.1:8000/admin/login>

Stop the development server with `Ctrl+C`.

## API overview

FastAPI's interactive API documentation at `/docs` lists the request and
response schemas. Main API areas include:

- `/listings/` and `/listings/with-images` for public browsing and customer
  listing creation.
- `/customers/` for customer signup, sign-in, profile, password reset, and
  listing management.
- `/auth/` for administrator sign-in, profile, and password reset.
- `/admin/listings/` and `/admin/categories/` for listing moderation and
  category management.
- `/listings/{listing_id}/reports` and `/admin/reports/` for listing reports.
- Customers must sign in to submit a listing report. In the admin dashboard,
  each report links to its advertisement; deleting the advertisement
  permanently removes its reports and uploaded listing images as well.

Protected routes require a bearer access token. Sign in through the relevant
customer or administrator endpoint and use the returned token as
`Authorization: Bearer YOUR_ACCESS_TOKEN`.

## Database migrations

Apply all pending migrations:

```powershell
python -m alembic upgrade head
```

Show the current migration revision:

```powershell
python -m alembic current
```

Migration scripts are in `migrations/versions/`. Back up the database before
applying migrations to any database containing important data.

## Uploaded files

Listing images are saved under the local `media/listings/` directory. New
customer profile pictures are stored in the PostgreSQL `customers` table;
existing file-based profile pictures continue to load from
`media/customer-profiles/`. Back up both the database and listing-image
directory if the data needs to be retained. In production, configure persistent
storage for listing images and serve the application behind an appropriately
configured web server.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`**: Run the server from the
  repository root with `python -m uvicorn main:app --reload`. `app.main:app`
  refers to a package layout that this project does not use.
- **Database connection errors**: Confirm PostgreSQL is running, the database
  exists, and the `DATABASE_*` values in `.env` are correct.
- **Missing settings at startup**: Check that `.env` is in the repository root
  and that all required database and secret-key variables are set.
- **Password-reset email is not delivered**: Verify the `SMTP_*` settings and
  ensure the email provider permits SMTP authentication. For Gmail, use an
  App Password rather than the account's normal password.
- **A migration fails**: Check the database connection and migration error,
  then inspect the migration history before retrying. Do not delete or
  recreate a database containing data you need.

## Development notes

- Install dependencies from `requirements.txt`.
- Run application and Alembic commands from the repository root so Python can
  import modules such as `main`, `config`, and `routes`.
- Tests belong in the `tests/` directory. No test files or test-runner
  configuration are currently included in this repository.
- Customer signup sends a six-digit code to the supplied email. The account
  is created only after the code is verified. Codes expire after 10 minutes
  and allow up to five attempts; request a new code if it expires.
- After requesting a signup code, the browser opens `/customer/verify-email`.
  Enter the emailed code on that page to create the account, then sign in.
- Administrator accounts remain restricted to `python create_admin.py`;
  there is no public admin signup. The script sends a six-digit code to the
  configured bootstrap administrator email before creating the account.
