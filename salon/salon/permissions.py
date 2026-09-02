import frappe
from frappe import _

NO_ACCESS_COST_CENTER = "__no_store_assigned__"


def get_user_scope(user=None):
	"""Resolve which Cost Center (store/branch) a user is confined to.

	System Managers see everything (cost_center=None, is_admin=True).
	Everyone else is scoped to the Cost Center on their assigned POS
	Profile, falling back to their Salon Stylist record. Users with
	neither get a cost_center that matches no real record, so they see
	nothing rather than everything (fail closed).
	"""
	user = user or frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return {"is_admin": True, "cost_center": None}

	cost_center = None

	pos_profile = frappe.get_all(
		"POS Profile User",
		filters={"user": user},
		fields=["parent as pos_profile", "default"],
		order_by="default desc",
		limit=1,
	)
	if pos_profile:
		cost_center = frappe.db.get_value("POS Profile", pos_profile[0].pos_profile, "cost_center")

	if not cost_center:
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if employee:
			cost_center = frappe.db.get_value("Salon Stylist", employee, "cost_center")

	return {"is_admin": False, "cost_center": cost_center or NO_ACCESS_COST_CENTER}


def resolve_cost_center_filter(requested_cost_center=None, user=None):
	"""For whitelisted methods: a non-admin's scope always wins over
	whatever cost_center the client asked for."""
	scope = get_user_scope(user)
	if scope["is_admin"]:
		return requested_cost_center
	return scope["cost_center"]


def check_cost_center_access(cost_center, user=None):
	"""Raise if a non-admin tries to touch a store outside their scope."""
	scope = get_user_scope(user)
	if scope["is_admin"]:
		return
	if not cost_center or cost_center != scope["cost_center"]:
		frappe.throw(_("You don't have access to this store"), frappe.PermissionError)


def get_permission_query_conditions(user=None):
	"""Hook target: restricts Salon Booking list/report views to the
	user's own store. Returns "" (no restriction) for admins."""
	scope = get_user_scope(user)
	if scope["is_admin"]:
		return ""
	return f"""`tabSalon Booking`.cost_center = {frappe.db.escape(scope["cost_center"])}"""


def has_permission(doc, user=None, **kwargs):
	"""Hook target: doctype-level has_permission for Salon Booking."""
	scope = get_user_scope(user)
	if scope["is_admin"]:
		return True
	return doc.cost_center == scope["cost_center"]


def get_pos_profile_for_cost_center(cost_center):
	"""The POS Profile a branch's bookings get billed through. One
	Cost Center is expected to map to exactly one POS Profile; if
	several exist, the most recently created one wins."""
	if not cost_center:
		return None
	return frappe.db.get_value(
		"POS Profile", {"cost_center": cost_center, "disabled": 0}, "name", order_by="creation desc"
	)
