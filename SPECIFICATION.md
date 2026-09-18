# HouseSplit — Final Product Specification

## 1. Product objective
HouseSplit is a web application for people who share a home and repeatedly split rent, groceries, utilities and subscriptions. It reduces the monthly hassle of manually calculating who owes whom by recording household expenses, calculating each member’s net balance and generating an optimized settlement plan.

### Input
Shared household expenses and repayments.

### Output
Each member’s net balance plus the smallest settlement plan found for the current household balances.

## 2. Example use case
Four roommates share an apartment. Marwan pays €1,800 rent, Sofia buys €142.60 of groceries, Alex pays €49.99 for internet, and Leo pays €96.40 for electricity. Every expense is shared among the relevant members. Instead of creating many person-to-person repayments, HouseSplit calculates every member’s net position across all expenses. A member who paid more than their share becomes a creditor; a member who paid less becomes a debtor. The app then produces a compact set of transfers that settles the entire group and lets the users mark each transfer as paid.

This turns a repeated monthly process — checking receipts, calculating shares, messaging roommates and tracking repayments — into one shared source of truth.

## 3. Core users
- Roommates
- Couples sharing expenses
- Families
- Students in shared housing
- People managing more than one household/group

## 4. Functional requirements

### 4.1 Dashboard
Show:
- total expenses for current month
- number of optimized transfers still required
- upcoming payments
- overdue payments
- each member’s current net balance
- quick settlement preview
- spending by category

### 4.2 Expense management
Create an expense with:
- title
- amount
- category
- transaction date
- optional due date
- person who paid
- participating members
- split amount
- note

Users can delete expenses. The data model supports later extension to exact, percentage, weighted and unequal splits.

### 4.3 Expense categories
Default categories:
- Rent
- Groceries
- Utilities
- Internet
- Entertainment
- Other

### 4.4 Calendar
A visual monthly calendar shows bill due dates. Overdue and soon-due expenses use distinct visual statuses.

### 4.5 Recurring expenses
Users can record predictable monthly items such as rent, electricity, internet and subscriptions with:
- amount
- payer
- category
- day of month
- note

### 4.6 Settlement engine
For each expense:
- payer receives a credit equal to the amount paid
- each participating member receives a debit equal to their allocated share

For each completed settlement:
- sender balance increases by the transferred amount
- receiver balance decreases by the transferred amount

The resulting net balances are reduced into an optimized person-to-person payment plan. The prototype uses an exact recursive search suitable for normal household sizes rather than simply showing every pairwise debt.

### 4.7 Mark as paid
A recommended transfer can be marked paid. This records a settlement transaction and immediately recalculates household balances.

### 4.8 Members
Users can add household members with name, email and profile color. Removing a member deactivates them for future splitting while preserving historical records.

### 4.9 History
One chronological activity stream combines expenses and completed settlements.

### 4.10 Search and filtering
Expenses can be filtered by:
- keyword
- category
- status (all / overdue / upcoming)

### 4.11 Account settings
Settings include:
- name
- email
- preferred currency
- bank name
- IBAN
- account holder
- notifications toggle

### 4.12 Multiple households
A user can create separate households such as “Madrid Flat”, “Family Home” or “Summer Apartment”. Every household has independent members, expenses, settings and balances.

## 5. User experience / interface
The UI is designed as a professional responsive web application inspired by native iOS patterns:
- light neutral background
- rounded white cards
- restrained purple accent
- soft shadows and borders
- compact status pills
- sidebar navigation on desktop
- bottom navigation on mobile
- responsive layouts
- modal forms
- visual balances and calendar

## 6. Data model
SQLite tables:
- `households`
- `members`
- `expenses`
- `expense_splits`
- `recurring_expenses`
- `settlements`
- `settings`

Foreign keys preserve relationships and expense splits remain attached to original historical expenses.

## 7. Security design
Implemented in this prototype:
- bank fields encrypted at rest with Fernet symmetric encryption
- encryption key stored separately from the SQLite database
- no bank passwords, PINs or card CVVs requested
- HTML output escaping in the client
- parameterized SQLite queries

Production requirements:
- HTTPS/TLS only
- user authentication and verified email
- password hashing with Argon2id or bcrypt
- secure server-side sessions
- CSRF protection
- rate limiting and login throttling
- role/household authorization checks on every API request
- secrets in a managed secrets vault, never beside application code
- encrypted production database and backups
- audit log for sensitive changes
- automatic session expiration
- optional 2FA
- privacy controls and account deletion/export
- payment processing through a regulated provider/open-banking partner rather than direct credential collection
- tokenized bank/payment information where possible
- GDPR-compliant consent and retention policies for EU deployment

## 8. Notifications
Prototype supports the preference. Production can send:
- “Rent due tomorrow.”
- “You owe €35.”
- “Electricity is overdue.”
- “Sofia marked your €18 payment as received.”

Recommended channels: in-app, email, and optional push notification.

## 9. Suggested next features
Simple, useful additions that stay within the product’s purpose:
- receipt attachment/photo
- custom split (exact amount or percentage)
- recurring expense auto-generation
- payment request link
- CSV/PDF monthly export
- comments under an expense
- household invite link
- archived households
- spending budget by category
- monthly comparison vs previous month
- “review before delete” confirmation
- undo recent action
- lightweight activity notifications
- dark mode

## 10. Non-goals for the first version
To keep the app simple and credible, the first version does not need:
- AI recommendations
- facial recognition
- complicated investment/budgeting tools
- social-media features
- storing online-banking passwords

## 11. Technical architecture
Frontend:
- HTML5
- CSS3
- vanilla JavaScript

Backend:
- Python 3
- standard-library HTTP server
- REST-style JSON endpoints

Database:
- SQLite

Encryption:
- `cryptography.Fernet`

This architecture is intentionally easy to understand for a university or prototype project and can later migrate to Flask/FastAPI/Django + PostgreSQL without changing the core product logic.

## 12. API summary
- `GET /api/bootstrap?household_id=...`
- `POST /api/expenses`
- `DELETE /api/expenses/{id}`
- `POST /api/members`
- `DELETE /api/members/{id}`
- `POST /api/households`
- `POST /api/settlements`
- `POST /api/recurring`
- `GET /api/settings`
- `POST /api/settings`

## 13. Success criteria
The MVP succeeds when a household can:
1. create or select a household,
2. add its members,
3. record a month of expenses,
4. instantly see every member’s balance,
5. see overdue/upcoming items,
6. receive a reduced settlement plan,
7. mark repayments as complete,
8. review history and monthly spending without manual calculations.
