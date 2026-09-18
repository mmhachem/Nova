# HouseSplit

A professional household expense-splitting web application built with **Python, HTML, CSS and JavaScript**.

## Run

```bash
python server.py
```

Open: `http://127.0.0.1:8000`

No external web framework is required. The Python backend uses the standard library HTTP server + SQLite. Bank details are encrypted at rest using `cryptography.Fernet`.

## Main features
- Dashboard with monthly spending, balances, upcoming/overdue payments
- Add / delete expenses and equal splitting
- Search and filters
- Visual monthly calendar
- Recurring expenses
- Multiple households
- Members
- Expense and settlement history
- Optimized settlement plan with the minimum number of transfers for the current net balances
- Mark transfers as paid
- Encrypted bank settings
- Responsive iOS-inspired interface

## Security note
This is a strong prototype. For a production financial application, deploy behind HTTPS, add authenticated accounts, CSRF protection, rate limiting, server-side sessions, audit logs, database access controls, a managed secret store, and a regulated payment provider. Do not store online-banking passwords or card CVVs.
