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
		# flips to Completed. Stock consumption happens right away (the
		# service was physically performed); revenue and commission do
		# NOT happen here anymore — they only land once a cashier actually
		# submits the POS invoice this booking is handed off to. See
		# create_draft_invoice() and salon/salon/events.py.
		if self.status == "Completed" and not self.sales_invoice:
			self.complete_booking()

	def complete_booking(self):
		if self.package_subscription:
			self.redeem_package()
		else:
			self.create_draft_invoice()

		self.create_stock_entry()

		# db_set to avoid re-triggering validate/on_update recursively
		self.db_set("sales_invoice", self.sales_invoice)
		self.db_set("stock_entry", self.stock_entry)

	def create_draft_invoice(self):
		from salon.salon.permissions import get_pos_profile_for_cost_center

		stylist = frappe.get_doc("Salon Stylist", self.salon_stylist)
		cost_center = self.cost_center or stylist.cost_center
		pos_profile_name = get_pos_profile_for_cost_center(cost_center)
		if not pos_profile_name:
			frappe.throw(
				_(
					"No POS Profile is set up for {0}. Create one (POS Profile > Cost Center = "
					"{0}) before completing bookings for this branch."
				).format(cost_center)
			)

		pos_profile = frappe.get_cached_doc("POS Profile", pos_profile_name)

		si = frappe.new_doc("Sales Invoice")
		si.customer = self.customer
		si.due_date = nowdate()
		si.company = pos_profile.company
		si.currency = frappe.get_cached_value("Company", pos_profile.company, "default_currency")
		si.cost_center = cost_center
		si.is_pos = 1
		si.is_created_using_pos = 1
		si.pos_profile = pos_profile_name
		si.set_warehouse = pos_profile.warehouse
		for row in self.services:
			si.append("items", {
				"item_code": row.item,
				"qty": row.qty,
				"rate": row.rate,
				"cost_center": cost_center,
				"warehouse": pos_profile.warehouse,
			})
		for p in pos_profile.payments:
			si.append("payments", {"mode_of_payment": p.mode_of_payment, "amount": 0})
		si.insert(ignore_permissions=True)
		# Left as a draft on purpose. It shows up under the POS register's
		# "Draft" orders for this branch — a cashier picks it up, takes
		# payment, and submits it there. Revenue and commission only fire
		# once that submit happens (salon/salon/events.py), not here.
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
