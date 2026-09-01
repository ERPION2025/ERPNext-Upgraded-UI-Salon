import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, flt, nowdate


class SalonBooking(Document):
	def validate(self):
		self.calculate_total()
		self.calculate_schedule()
		self.check_stylist_conflict()

	def calculate_total(self):
		total = 0
		for row in self.services:
			if not row.rate:
				row.rate = frappe.db.get_value(
					"Item Price", {"item_code": row.item, "selling": 1}, "price_list_rate"
				) or 0
			row.amount = flt(row.qty) * flt(row.rate)
			total += row.amount
		self.total_amount = total

	def calculate_schedule(self):
		if not self.booking_datetime:
			return
		total_minutes = sum(flt(row.duration_minutes) or 30 for row in self.services) or 30
		self.end_datetime = add_to_date(self.booking_datetime, minutes=total_minutes)

	def check_stylist_conflict(self):
		if not (self.salon_stylist and self.booking_datetime and self.end_datetime):
			return
		if self.status in ("Cancelled", "No-Show"):
			return

		conflict = frappe.db.sql(
			"""
			select name from `tabSalon Booking`
			where salon_stylist = %(stylist)s
				and name != %(name)s
				and status not in ('Cancelled', 'No-Show')
				and booking_datetime < %(end)s
				and end_datetime > %(start)s
			""",
			{
				"stylist": self.salon_stylist,
				"name": self.name or "New Salon Booking",
				"start": self.booking_datetime,
				"end": self.end_datetime,
			},
		)
		if conflict:
			frappe.throw(
				_("{0} already has a booking ({1}) that overlaps this time slot").format(
					self.salon_stylist, conflict[0][0]
				)
			)

	def on_update(self):
		# Fire the completion automation exactly once, the moment status
		# flips to Completed. Everything downstream — invoice, stock,
		# commission — is native ERPNext from here.
		if self.status == "Completed" and not self.sales_invoice:
			self.complete_booking()

	def complete_booking(self):
		if self.package_subscription:
			self.redeem_package()
		else:
			self.create_invoice()

		self.create_stock_entry()
		self.create_commission_entry()

		# db_set to avoid re-triggering validate/on_update recursively
		self.db_set("sales_invoice", self.sales_invoice)
		self.db_set("stock_entry", self.stock_entry)
		self.db_set("additional_salary", self.additional_salary)

	def create_invoice(self):
		stylist = frappe.get_doc("Salon Stylist", self.salon_stylist)
		cost_center = self.cost_center or stylist.cost_center

		si = frappe.new_doc("Sales Invoice")
		si.customer = self.customer
		si.due_date = nowdate()
		si.cost_center = cost_center
		for row in self.services:
			si.append("items", {
				"item_code": row.item,
				"qty": row.qty,
				"rate": row.rate,
				"cost_center": cost_center,
			})
		si.insert(ignore_permissions=True)
		si.submit()
		self.sales_invoice = si.name

	def redeem_package(self):
		sub = frappe.get_doc("Package Subscription", self.package_subscription)
		if flt(sub.sessions_remaining) <= 0:
			frappe.throw(_("No sessions remaining on {0}").format(sub.name))
		sub.sessions_used = flt(sub.sessions_used) + 1
		sub.save(ignore_permissions=True)
		# No new Sales Invoice: the revenue was already recognised when the
		# package itself was sold. This booking just decrements the balance.

	def create_stock_entry(self):
		rows = []
		for row in self.services:
			if not frappe.db.exists("Salon Service Recipe", row.item):
				continue
			recipe = frappe.get_doc("Salon Service Recipe", row.item)
			for c in recipe.consumables:
				rows.append({
					"item_code": c.raw_material,
					"qty": flt(c.qty) * flt(row.qty),
					"s_warehouse": c.warehouse,
					"cost_center": self.cost_center,
				})

		if not rows:
			return

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		for r in rows:
			se.append("items", r)
		se.insert(ignore_permissions=True)
		se.submit()
		self.stock_entry = se.name

	def create_commission_entry(self):
		stylist = frappe.get_doc("Salon Stylist", self.salon_stylist)
		if not stylist.commission_rate:
			return

		commission = flt(self.total_amount) * flt(stylist.commission_rate) / 100
		if not commission:
			return

		# Requires a Salary Component named "Service Commission" —
		# create it once under Payroll > Salary Component (native, no code).
		asal = frappe.new_doc("Additional Salary")
		asal.employee = stylist.employee
		asal.salary_component = "Service Commission"
		asal.amount = commission
		asal.payroll_date = nowdate()
		asal.company = frappe.defaults.get_user_default("Company")
		asal.insert(ignore_permissions=True)
		asal.submit()
		self.additional_salary = asal.name
