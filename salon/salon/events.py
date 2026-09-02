import frappe
from frappe.utils import flt, nowdate


def on_sales_invoice_submit(doc, method=None):
	"""Revenue and stylist commission only land once a cashier actually
	submits the POS invoice a completed booking was handed off to -
	not when the booking itself is marked Completed. See
	Salon Booking.create_draft_invoice()."""
	booking_name = frappe.db.get_value("Salon Booking", {"sales_invoice": doc.name}, "name")
	if not booking_name:
		return

	booking = frappe.get_doc("Salon Booking", booking_name)
	if booking.additional_salary:
		return

	stylist = frappe.get_doc("Salon Stylist", booking.salon_stylist)
	if not stylist.commission_rate:
		return

	commission = flt(doc.grand_total) * flt(stylist.commission_rate) / 100
	if not commission:
		return

	# Requires a Salary Component named "Service Commission" - create it
	# once under Payroll > Salary Component (native, no code).
	asal = frappe.new_doc("Additional Salary")
	asal.employee = stylist.employee
	asal.salary_component = "Service Commission"
	asal.amount = commission
	asal.payroll_date = nowdate()
	asal.company = doc.company
	asal.insert(ignore_permissions=True)
	asal.submit()

	booking.db_set("additional_salary", asal.name)
