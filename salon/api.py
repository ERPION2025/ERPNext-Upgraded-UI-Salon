import frappe
from frappe.utils import get_datetime, today


@frappe.whitelist()
def get_dashboard_kpis(cost_center=None):
	filters = {"booking_datetime": [">=", today()]}
	if cost_center:
		filters["cost_center"] = cost_center

	bookings = frappe.get_all(
		"Salon Booking",
		filters=filters,
		fields=["name", "customer", "salon_stylist", "booking_datetime", "status", "total_amount"],
		order_by="booking_datetime asc",
	)

	conditions = ["b.status = 'Completed'", "date(b.booking_datetime) = %(today)s"]
	values = {"today": today()}
	if cost_center:
		conditions.append("b.cost_center = %(cost_center)s")
		values["cost_center"] = cost_center

	revenue = frappe.db.sql(
		f"""select coalesce(sum(b.total_amount), 0) from `tabSalon Booking` b
		where {' and '.join(conditions)}""",
		values,
	)[0][0]

	commissions = frappe.db.sql(
		"""select coalesce(sum(amount), 0) from `tabAdditional Salary`
		where salary_component = 'Service Commission' and date(payroll_date) = %(today)s""",
		{"today": today()},
	)[0][0]

	return {
		"today_bookings": len(bookings),
		"revenue_today": revenue,
		"commissions_today": commissions,
		"schedule": bookings,
	}


@frappe.whitelist()
def mark_completed(booking):
	doc = frappe.get_doc("Salon Booking", booking)
	doc.status = "Completed"
	doc.save()
	return doc.status


@frappe.whitelist()
def get_calendar_data(start, end, cost_center=None):
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

	return {"stylists": stylists, "bookings": bookings}


@frappe.whitelist()
def reschedule_booking(booking, booking_datetime, salon_stylist=None):
	doc = frappe.get_doc("Salon Booking", booking)
	doc.booking_datetime = get_datetime(booking_datetime)
	if salon_stylist:
		doc.salon_stylist = salon_stylist
	doc.save()
	return {
		"name": doc.name,
		"booking_datetime": doc.booking_datetime,
		"end_datetime": doc.end_datetime,
		"salon_stylist": doc.salon_stylist,
	}


@frappe.whitelist()
def create_quick_booking(customer, salon_stylist, booking_datetime, item, cost_center=None):
	doc = frappe.new_doc("Salon Booking")
	doc.customer = customer
	doc.salon_stylist = salon_stylist
	doc.booking_datetime = get_datetime(booking_datetime)
	if cost_center:
		doc.cost_center = cost_center
	doc.append("services", {"item": item, "qty": 1})
	doc.insert()
	return doc.name
