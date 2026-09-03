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
	#
	# overwrite_salary_structure_amount MUST stay 0: "overwrite" means
	# "this is the one true value for this component on this date",
	# so Frappe HR blocks a second overwrite entry for the same
	# employee/component/date outright (see
	# Additional Salary.validate_duplicate_additional_salary). A stylist
	# can complete several bookings a day, each billed separately, and
	# each commission needs to stack on top of the others - which is
	# exactly what a plain (non-overwrite) Additional Salary does; Frappe
	# HR sums every submitted one for the employee/component within a
	# payroll period when Payroll Entry runs.
	asal = frappe.new_doc("Additional Salary")
	asal.employee = stylist.employee
	asal.salary_component = "Service Commission"
	asal.amount = commission
	asal.payroll_date = nowdate()
	asal.company = doc.company
	asal.overwrite_salary_structure_amount = 0
	asal.insert(ignore_permissions=True)
	asal.submit()

	booking.db_set("additional_salary", asal.name)
