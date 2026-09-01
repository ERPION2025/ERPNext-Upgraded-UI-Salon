# Salon Suite

A booking, stylist-commission and stock-consumption suite for ERPNext,
built as an installable Frappe app (module `Salon`, app name `salon`).

Covers:

- **Salon Booking** — client + stylist + services, auto totals, and on
  completion: creates a Sales Invoice (or redeems a Package Subscription),
  a Stock Entry for any consumables from a matching Salon Service Recipe,
  and an Additional Salary commission entry for the stylist.
- **Salon Stylist** — one per Employee, with commission % and branch
  (Cost Center).
- **Salon Service Recipe** / **Recipe Consumable** — raw materials a
  service consumes, for automatic stock deduction.
- **Package Subscription** — prepaid session packages redeemed by bookings.
- **Salon Dashboard** (`/app/salon-dashboard`) — a custom KPI + live
  schedule page. Every other sidebar link (Bookings, Clients, Packages,
  Services, Stylists, Stock, Invoicing) points at the native Desk list
  view for that doctype.

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
- A **Salon Stylist** record per Employee, with `commission_rate` and
  `cost_center` set.
- A **Cost Center** per branch, and a **Warehouse** per branch if you
  want stock deduction working.
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
