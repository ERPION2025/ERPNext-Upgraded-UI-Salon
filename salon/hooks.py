app_name = "salon"
app_title = "Salon Suite"
app_publisher = "Erpion"
app_description = "Salon booking, stylist commission and stock-consumption suite for ERPNext"
app_email = "pranav@erpion.in"
app_license = "MIT"

# Apps that must already be installed on the site before this app.
# HR/Payroll doctypes (Employee, Salary Component, Additional Salary) live
# in the separate Frappe HR app as of ERPNext v14+, not in erpnext core.
required_apps = ["erpnext", "hrms"]

# Includes in <head>
# ------------------
app_include_css = "/assets/salon/css/salon.css"
app_include_js = "/assets/salon/js/salon_common.js"

# Landing page when a user switches into the "Salon Suite" app from the
# app switcher (top-left). Without this, Frappe falls back to the generic
# auto-generated Workspace instead of our custom Dashboard.
app_home = "/app/salon-dashboard"

# Store/branch isolation: non-System Manager users (POS Profile cashiers,
# stylists) only ever see Salon Bookings for their own Cost Center, in the
# native list view/reports as well as our custom Dashboard/Calendar pages.
permission_query_conditions = {
	"Salon Booking": "salon.salon.permissions.get_permission_query_conditions",
}
has_permission = {
	"Salon Booking": "salon.salon.permissions.has_permission",
}

# Fixtures
# --------
# Uncomment and list export fixtures here if you later add custom Salary
# Components, Roles, etc. that should ship with the app instead of being
# created manually per site.
# fixtures = []
