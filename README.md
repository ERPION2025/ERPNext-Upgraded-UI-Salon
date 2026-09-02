# Salon Suite

A booking, stylist-commission and stock-consumption suite for ERPNext,
built as an installable Frappe app (module `Salon`, app name `salon`).

Covers:

- **Salon Booking** — client + stylist + services, auto totals. On
  completion (status → Completed) it hands off to POS rather than
  billing anything itself: it creates a *draft* POS-flagged Sales
  Invoice (or redeems a Package Subscription) for the branch's POS
  Profile, and a Stock Entry for any consumables from a matching Salon
  Service Recipe. Revenue and the stylist's commission (Additional
  Salary, `Service Commission` component) only get created once a
  cashier actually submits that invoice in POS — see
  `salon/salon/events.py`.
- **Salon Stylist** — one per Employee, with commission % and branch
  (Cost Center).
- **Salon Service Recipe** / **Recipe Consumable** — raw materials a
  service consumes, for automatic stock deduction.
- **Package Subscription** — prepaid session packages redeemed by bookings.
- **Salon Dashboard** (`/app/salon-dashboard`) and **Salon Calendar**
  (`/app/salon-calendar`) — custom pages with live KPIs (including a
  store-wise sales breakdown) and a drag-to-reschedule time grid. Every
  other sidebar link (Bookings, Clients, Packages, Services, Stylists,
  Stock) points at the native Desk list view for that doctype; POS &
  Invoicing routes System Managers to the Sales Invoice list and
  everyone else straight into the POS register.
- **Store-scoped permissions** (`salon/salon/permissions.py`) — System
  Managers see every branch; everyone else (cashiers, stylists) only
  ever sees their own branch's bookings, both in the custom
  Dashboard/Calendar and in the native Salon Booking list/reports. A
  user's branch is resolved from their assigned POS Profile, falling
  back to their Salon Stylist record.

## Requirements

- **Frappe / ERPNext v16** (bench branch `version-16`).
- **Frappe HR (`hrms`)** — required. Since ERPNext v14, HR/Payroll
  doctypes (`Employee`, `Salary Component`, `Additional Salary`) live in
  the separate [frappe/hrms](https://github.com/frappe/hrms) app, not in
  ERPNext core. This app declares `required_apps = ["erpnext", "hrms"]`
  in `hooks.py`, so both must be on the bench/site before installing.

## Deploying on Frappe Cloud

1. Push this repo to GitHub (already at
   `ERPION2025/ERPNext-Upgraded-UI-Salon`) with a branch matching your
   bench's Frappe version, e.g. `main` or `version-16`.
2. In the Frappe Cloud dashboard, open your bench group → **Apps** →
   **Add App** → **GitHub**, and point it at this repo/branch. Frappe
   Cloud will detect the `salon` app from `pyproject.toml` at the repo
   root and build it into the bench along with `erpnext` and `hrms`
   (add `hrms` to the bench group first if it isn't already there).
3. Deploy the bench, then on your site: **Install App** → `Salon`.
4. Run one-time master data setup (below), then visit
   `/app/salon-dashboard`.

### Local bench (alternative)

```bash
bench get-app salon https://github.com/ERPION2025/ERPNext-Upgraded-UI-Salon --branch main
bench --site your-site.com install-app hrms   # if not already installed
bench --site your-site.com install-app salon
bench --site your-site.com migrate
bench build --app salon
bench restart
```

## One-time master data (no code, just Desk records)

- A **Salary Component** named exactly `Service Commission`
  (Payroll > Salary Component) — the commission automation posts to this.
- A **Salary Structure** that includes `Service Commission`, with a
  **Salary Structure Assignment** for every stylist Employee — required
  by Frappe HR before any Additional Salary can be created for them.
- A **Salon Stylist** record per Employee, with `commission_rate` and
  `cost_center` set.
- A **Cost Center** per branch, and a **Warehouse** per branch if you
  want stock deduction working.
- A **POS Profile** per branch, with its `Cost Center` set to that
  branch's Cost Center and at least one payment method configured.
  This is what a completed booking's draft invoice is billed through,
  and what a non-admin user's branch access is resolved from (via
  *POS Profile → Applicable for Users*).
- Before any booking can be completed for a branch, that branch's POS
  Profile needs an **open POS Opening Entry** (POS > New, the normal
  daily "open the till" step a cashier does) — Frappe itself requires
  this before it will accept a POS-flagged invoice.
- Optional: a **Salon Service Recipe** per service Item, listing the raw
  materials it consumes — only services with a recipe generate a Stock
  Entry on completion.

## Branding

`salon/public/css/salon.css` uses placeholder hex values (`#e4002b` red,
white surfaces). Swap these for your actual theme tokens so the salon
suite matches the rest of your ERPNext instance.

## Extending

Only the Dashboard is a fully custom page today. Building out another
section into its own custom page (e.g. a Booking Calendar with
drag-to-reschedule, or a Client 360 view) follows the same pattern as
`salon/salon/page/salon_dashboard/salon_dashboard.js` — a Page record +
a JS file rendering into `page.body` + a whitelisted method in
`salon/api.py` feeding it data.
