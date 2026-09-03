import frappe
from frappe import _
from frappe.utils import get_datetime, today

from salon.salon.permissions import (
	check_cost_center_access,
	get_user_scope,
	resolve_cost_center_filter,
)


@frappe.whitelist()
def get_dashboard_kpis(cost_center=None):
	scope = get_user_scope()
	cost_center = resolve_cost_center_filter(cost_center)

	filters = {"booking_datetime": [">=", today()]}
	if cost_center:
		filters["cost_center"] = cost_center

	bookings = frappe.get_all(
		"Salon Booking",
		filters=filters,
		fields=["name", "customer", "salon_stylist", "booking_datetime", "status", "total_amount"],
		order_by="booking_datetime asc",
	)

	# Revenue reflects actual submitted invoices (Sales Invoice, the POS
	# ones our completed bookings hand off to included) - not a booking's
	# status. A Completed booking with nobody billing it yet at the POS
	# contributes nothing here on purpose.
	revenue_conditions = ["docstatus = 1", "posting_date = %(today)s"]
	revenue_values = {"today": today()}
	if cost_center:
		revenue_conditions.append("cost_center = %(cost_center)s")
		revenue_values["cost_center"] = cost_center

	revenue = frappe.db.sql(
		f"""select coalesce(sum(grand_total), 0) from `tabSales Invoice`
		where {' and '.join(revenue_conditions)}""",
		revenue_values,
	)[0][0]

	commission_conditions = ["salary_component = 'Service Commission'", "date(payroll_date) = %(today)s"]
	commission_values = {"today": today()}
	if cost_center:
		# Additional Salary doesn't carry cost_center directly; scope via the stylists in this store.
		commission_conditions.append(
			"employee in (select employee from `tabSalon Stylist` where cost_center = %(cost_center)s)"
		)
		commission_values["cost_center"] = cost_center

	commissions = frappe.db.sql(
		f"""select coalesce(sum(amount), 0) from `tabAdditional Salary`
		where {' and '.join(commission_conditions)}""",
		commission_values,
	)[0][0]

	stylist_conditions = ["b.status not in ('Cancelled', 'No-Show')", "date(b.booking_datetime) = %(today)s"]
	stylist_values = {"today": today()}
	if cost_center:
		stylist_conditions.append("b.cost_center = %(cost_center)s")
		stylist_values["cost_center"] = cost_center

	active_stylists = frappe.db.sql(
		f"""select count(distinct b.salon_stylist) from `tabSalon Booking` b
		where {' and '.join(stylist_conditions)}""",
		stylist_values,
	)[0][0]

	pos_filters = {"status": "Open"}
	if cost_center:
		pos_profiles = frappe.get_all("POS Profile", filters={"cost_center": cost_center}, pluck="name")
		pos_filters["pos_profile"] = ["in", pos_profiles or [""]]
	active_pos = frappe.db.count("POS Opening Entry", filters=pos_filters)

	store_sales = []
	if not cost_center:
		# Only meaningful in the "All Branches" admin view — a single store's
		# figure is already the revenue_today tile above.
		store_sales = frappe.db.sql(
			"""
			select cost_center, coalesce(sum(grand_total), 0) as revenue
			from `tabSales Invoice`
			where docstatus = 1 and posting_date = %(today)s
				and cost_center is not null and cost_center != ''
			group by cost_center
			order by revenue desc
			""",
			{"today": today()},
			as_dict=True,
		)

	return {
		"today_bookings": len(bookings),
		"revenue_today": revenue,
		"commissions_today": commissions,
		"active_stylists": active_stylists,
		"active_pos": active_pos,
		"store_sales": store_sales,
		"schedule": bookings,
		"is_admin": scope["is_admin"],
		"user_cost_center": None if scope["is_admin"] else scope["cost_center"],
	}


@frappe.whitelist()
def mark_completed(booking):
	doc = frappe.get_doc("Salon Booking", booking)
	check_cost_center_access(doc.cost_center)
	doc.status = "Completed"
	doc.save()
	return doc.status


@frappe.whitelist()
def complete_and_bill(booking):
	"""Mark a booking Completed and hand it off to the branch's POS
	register. Returns the draft invoice + POS profile so the caller can
	route the cashier straight into POS to take payment."""
	from salon.salon.permissions import get_pos_profile_for_cost_center

	doc = frappe.get_doc("Salon Booking", booking)
	check_cost_center_access(doc.cost_center)
	doc.status = "Completed"
	doc.save()

	return {
		"status": doc.status,
		"sales_invoice": doc.sales_invoice,
		"pos_profile": get_pos_profile_for_cost_center(doc.cost_center),
	}


@frappe.whitelist()
def update_booking_status(booking, status):
	"""Generic status setter for the Calendar's board view (dragging a
	card between the Tentative/Confirmed/Checked In columns). Completed
	specifically goes through complete_and_bill instead, since that also
	resolves the POS Profile for the caller - but even called directly,
	Salon Booking.on_update() would still create the draft invoice the
	same way, since that's keyed off the status value, not the caller."""
	doc = frappe.get_doc("Salon Booking", booking)
	check_cost_center_access(doc.cost_center)
	doc.status = status
	doc.save()
	return {"status": doc.status, "sales_invoice": doc.sales_invoice}


@frappe.whitelist()
def get_calendar_data(start, end, cost_center=None):
	scope = get_user_scope()
	cost_center = resolve_cost_center_filter(cost_center)

	stylist_filters = {}
	if cost_center:
		stylist_filters["cost_center"] = cost_center

	stylists = frappe.get_all(
		"Salon Stylist",
		filters=stylist_filters,
		fields=["name", "stylist_name", "employee", "cost_center"],
		order_by="stylist_name asc",
	)

	conditions = ["b.booking_datetime < %(end)s", "b.end_datetime > %(start)s"]
	values = {"start": get_datetime(start), "end": get_datetime(end)}
	if cost_center:
		conditions.append("b.cost_center = %(cost_center)s")
		values["cost_center"] = cost_center

	bookings = frappe.db.sql(
		f"""
		select b.name, b.customer, b.salon_stylist, b.booking_datetime, b.end_datetime,
			b.status, b.total_amount
		from `tabSalon Booking` b
		where {' and '.join(conditions)}
		order by b.booking_datetime asc
		""",
		values,
		as_dict=True,
	)

	for b in bookings:
		b["services"] = frappe.get_all(
			"Booking Service",
			filters={"parent": b.name},
			fields=["item", "qty"],
			order_by="idx asc",
		)

	item_codes = {s.item for b in bookings for s in b["services"]}
	item_names = {}
	if item_codes:
		item_names = dict(
			frappe.get_all(
				"Item", filters={"name": ["in", list(item_codes)]}, fields=["name", "item_name"], as_list=True
			)
		)
	for b in bookings:
		for s in b["services"]:
			s["item_name"] = item_names.get(s.item, s.item)

	return {
		"stylists": stylists,
		"bookings": bookings,
		"is_admin": scope["is_admin"],
		"user_cost_center": None if scope["is_admin"] else scope["cost_center"],
	}


@frappe.whitelist()
def reschedule_booking(booking, booking_datetime, salon_stylist=None):
	doc = frappe.get_doc("Salon Booking", booking)
	check_cost_center_access(doc.cost_center)

	if salon_stylist and salon_stylist != doc.salon_stylist:
		new_stylist_cc = frappe.db.get_value("Salon Stylist", salon_stylist, "cost_center")
		check_cost_center_access(new_stylist_cc)
		doc.salon_stylist = salon_stylist

	doc.booking_datetime = get_datetime(booking_datetime)
	doc.save()
	return {
		"name": doc.name,
		"booking_datetime": doc.booking_datetime,
		"end_datetime": doc.end_datetime,
		"salon_stylist": doc.salon_stylist,
	}


@frappe.whitelist()
def create_quick_booking(customer, salon_stylist, booking_datetime, item, cost_center=None):
	scope = get_user_scope()
	stylist_cc = frappe.db.get_value("Salon Stylist", salon_stylist, "cost_center")

	if scope["is_admin"]:
		cost_center = cost_center or stylist_cc
	else:
		check_cost_center_access(stylist_cc)
		cost_center = scope["cost_center"]

	doc = frappe.new_doc("Salon Booking")
	doc.customer = customer
	doc.salon_stylist = salon_stylist
	doc.booking_datetime = get_datetime(booking_datetime)
	if cost_center:
		doc.cost_center = cost_center
	doc.append("services", {"item": item, "qty": 1})
	doc.insert()
	return doc.name
