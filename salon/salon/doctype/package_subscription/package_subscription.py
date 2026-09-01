from frappe.model.document import Document
from frappe.utils import flt


class PackageSubscription(Document):
	def validate(self):
		self.sessions_remaining = flt(self.sessions_total) - flt(self.sessions_used)
		if self.sessions_remaining <= 0 and self.status == "Active":
			self.status = "Completed"
