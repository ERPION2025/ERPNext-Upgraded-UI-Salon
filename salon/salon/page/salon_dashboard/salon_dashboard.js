frappe.pages['salon-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: '',
		single_column: true,
	});
	wrapper.classList.add('salon-suite');
	new SalonDashboard(page);
};

class SalonDashboard {
	constructor(page) {
		this.page = page;
		this.render_shell();
		this.load_data();
	}

	render_shell() {
		this.page.body.innerHTML = `
			<div class="salon-shell">
				${salon_common.render_sidebar_html('dashboard')}
				<main class="salon-main">
					<header class="salon-header">
						<h1>Good morning, ${frappe.utils.escape_html(frappe.session.user_fullname)}</h1>
						<p id="salon-date"></p>
					</header>
					<section class="salon-kpis" id="salon-kpis"></section>
					<section class="salon-schedule">
						<div class="salon-schedule-head">
							<h2>Today's schedule</h2>
							<a href="/app/salon-calendar">Open Calendar &rarr;</a>
						</div>
						<table class="salon-table">
							<thead>
								<tr><th>Time</th><th>Client</th><th>Stylist</th><th>Status</th><th>Total</th></tr>
							</thead>
							<tbody id="salon-schedule-body"></tbody>
						</table>
					</section>
				</main>
			</div>
		`;
		document.getElementById('salon-date').textContent = frappe.datetime.str_to_user(
			frappe.datetime.now_date(),
			true
		);
	}

	load_data() {
		frappe.call('salon.api.get_dashboard_kpis').then((r) => {
			const d = r.message || {};
			this.render_kpis(d);
			this.render_schedule(d.schedule || []);
		});
	}

	render_kpis(d) {
		const cards = [
			{ label: "Today's bookings", value: d.today_bookings || 0 },
			{ label: 'Revenue today', value: format_currency(d.revenue_today || 0) },
			{ label: 'Commissions accrued', value: format_currency(d.commissions_today || 0) },
		];
		document.getElementById('salon-kpis').innerHTML = cards
			.map(
				(c) => `
			<div class="salon-card">
				<div class="salon-card-value">${c.value}</div>
				<div class="salon-card-label">${c.label}</div>
			</div>
		`
			)
			.join('');
	}

	render_schedule(rows) {
		const body = document.getElementById('salon-schedule-body');
		if (!rows.length) {
			body.innerHTML = '<tr><td colspan="5">No bookings yet today.</td></tr>';
			return;
		}
		body.innerHTML = rows
			.map((r) => {
				const status_class = (r.status || '').toLowerCase().replace(/\s+/g, '-');
				return `
				<tr>
					<td>${frappe.datetime.str_to_user(r.booking_datetime, true)}</td>
					<td>${frappe.utils.escape_html(r.customer || '')}</td>
					<td>${frappe.utils.escape_html(r.salon_stylist || '')}</td>
					<td><span class="salon-status salon-status-${status_class}">${r.status}</span></td>
					<td>${format_currency(r.total_amount || 0)}</td>
				</tr>
			`;
			})
			.join('');
	}
}
