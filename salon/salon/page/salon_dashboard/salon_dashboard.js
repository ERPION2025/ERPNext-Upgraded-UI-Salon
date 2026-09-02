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
		this.body = page.body.get(0);
		this.cost_center = null;
		this.filter_rendered = false;
		this.render_shell();
		this.load_data();
	}

	render_shell() {
		this.body.innerHTML = `
			<div class="salon-shell">
				${salon_common.render_sidebar_html('dashboard')}
				<main class="salon-main">
					<header class="salon-header">
						<div>
							<h1>Good morning, ${frappe.utils.escape_html(frappe.session.user_fullname)}</h1>
							<p id="salon-date"></p>
						</div>
						<div class="salon-branch-filter" id="salon-branch-filter"></div>
					</header>
					<section class="salon-kpis" id="salon-kpis"></section>
					<section class="salon-store-sales" id="salon-store-sales" hidden></section>
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
		this.body.querySelector('#salon-date').textContent = frappe.datetime.str_to_user(
			frappe.datetime.now_date(),
			true
		);
		this.$filter = this.body.querySelector('#salon-branch-filter');
	}

	load_data() {
		frappe.call({
			method: 'salon.api.get_dashboard_kpis',
			args: { cost_center: this.cost_center },
		}).then((r) => {
			const d = r.message || {};
			this.is_admin = d.is_admin;
			this.user_cost_center = d.user_cost_center;

			if (!this.filter_rendered) {
				this.render_filter();
				this.filter_rendered = true;
			}

			this.render_kpis(d);
			this.render_store_sales(d.store_sales || []);
			this.render_schedule(d.schedule || []);
		});
	}

	render_filter() {
		if (!this.is_admin) {
			// Cashiers / branch staff are locked to their own store — no
			// picker, just show which store this data is scoped to.
			this.$filter.innerHTML = `<span class="salon-branch-locked">${frappe.utils.escape_html(
				this.user_cost_center || __('No store assigned')
			)}</span>`;
			return;
		}

		frappe.call({
			method: 'frappe.client.get_list',
			args: { doctype: 'Cost Center', fields: ['name'], limit_page_length: 0, order_by: 'name asc' },
		}).then((r) => {
			const opts = (r.message || [])
				.map((c) => `<option value="${frappe.utils.escape_html(c.name)}">${frappe.utils.escape_html(c.name)}</option>`)
				.join('');
			this.$filter.innerHTML = `
				<select class="form-control salon-branch-select">
					<option value="">${__('All Branches')}</option>
					${opts}
				</select>
			`;
			this.$filter.querySelector('select').addEventListener('change', (e) => {
				this.cost_center = e.target.value || null;
				this.load_data();
			});
		});
	}

	render_kpis(d) {
		const cards = [
			{ label: "Today's bookings", value: d.today_bookings || 0 },
			{ label: 'Revenue today', value: format_currency(d.revenue_today || 0) },
			{ label: 'Commissions accrued', value: format_currency(d.commissions_today || 0) },
			{ label: 'Active stylists', value: d.active_stylists || 0 },
			{ label: 'Active POS sessions', value: d.active_pos || 0 },
		];
		this.body.querySelector('#salon-kpis').innerHTML = cards
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

	render_store_sales(rows) {
		const section = this.body.querySelector('#salon-store-sales');
		if (!rows.length) {
			section.hidden = true;
			section.innerHTML = '';
			return;
		}
		section.hidden = false;
		section.innerHTML = `
			<h2>Store-wise sales today</h2>
			<table class="salon-table">
				<thead><tr><th>Branch</th><th>Sales</th></tr></thead>
				<tbody>
					${rows
						.map(
							(r) => `
						<tr>
							<td>${frappe.utils.escape_html(r.cost_center)}</td>
							<td>${format_currency(r.revenue || 0)}</td>
						</tr>
					`
						)
						.join('')}
				</tbody>
			</table>
		`;
	}

	render_schedule(rows) {
		const body = this.body.querySelector('#salon-schedule-body');
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
