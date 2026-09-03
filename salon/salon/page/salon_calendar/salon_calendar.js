frappe.pages['salon-calendar'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: '',
		single_column: true,
	});
	wrapper.classList.add('salon-suite');
	new SalonCalendar(page);
};

class SalonCalendar {
	constructor(page) {
		this.page = page;
		this.body = page.body.get(0);
		this.date = frappe.datetime.get_today();
		this.cost_center = null;
		this.GRID_START_HOUR = 8;
		this.GRID_END_HOUR = 20;
		this.PX_PER_MIN = 1.6;
		this.SNAP_MIN = 15;
		this.LOCKED_STATUSES = ['Completed', 'Cancelled', 'No-Show'];

		this.scope_resolved = false;

		this.render_shell();
		this.wire_toolbar();
		this.load_data();
	}

	grid_height() {
		return (this.GRID_END_HOUR - this.GRID_START_HOUR) * 60 * this.PX_PER_MIN;
	}

	render_shell() {
		this.body.innerHTML = `
			<div class="salon-shell">
				${salon_common.render_sidebar_html('calendar')}
				<main class="salon-main salon-cal-main">
					<header class="salon-cal-toolbar">
						<div class="salon-cal-title">
							<h1>Booking Calendar</h1>
							<p>Drag to reschedule &middot; click an empty slot to create a booking &middot; live conflict checking</p>
						</div>
						<div class="salon-cal-controls">
							<button class="btn btn-default btn-sm" data-nav="prev">&larr;</button>
							<input type="date" class="form-control salon-cal-date" />
							<button class="btn btn-default btn-sm" data-nav="today">Today</button>
							<button class="btn btn-default btn-sm" data-nav="next">&rarr;</button>
							<select class="form-control salon-cal-branch">
								<option value="">All Branches</option>
							</select>
							<button class="btn btn-primary salon-cal-new">+ New Booking</button>
						</div>
					</header>
					<div class="salon-cal-grid-wrap">
						<div class="cal-grid">
							<div class="cal-header-row">
								<div class="cal-time-corner"></div>
								<div class="cal-columns-header"></div>
							</div>
							<div class="cal-body-row">
								<div class="cal-time-labels"></div>
								<div class="cal-columns-body"></div>
								<div class="cal-now-line" style="display:none"></div>
							</div>
						</div>
					</div>
				</main>
			</div>
		`;

		this.$date_input = this.body.querySelector('.salon-cal-date');
		this.$branch_select = this.body.querySelector('.salon-cal-branch');
		this.$time_labels = this.body.querySelector('.cal-time-labels');
		this.$columns_header = this.body.querySelector('.cal-columns-header');
		this.$columns_body = this.body.querySelector('.cal-columns-body');
		this.$now_line = this.body.querySelector('.cal-now-line');

		this.$date_input.value = this.date;
	}

	wire_toolbar() {
		this.$date_input.addEventListener('change', () => {
			this.date = this.$date_input.value;
			this.load_data();
		});

		this.body.querySelectorAll('[data-nav]').forEach((btn) => {
			btn.addEventListener('click', () => {
				const nav = btn.dataset.nav;
				if (nav === 'today') {
					this.date = frappe.datetime.get_today();
				} else {
					const d = new Date(this.date + 'T00:00:00');
					d.setDate(d.getDate() + (nav === 'next' ? 1 : -1));
					this.date = this.format_date(d);
				}
				this.$date_input.value = this.date;
				this.load_data();
			});
		});

		this.$branch_select.addEventListener('change', () => {
			this.cost_center = this.$branch_select.value || null;
			this.load_data();
		});

		this.body.querySelector('.salon-cal-new').addEventListener('click', () => {
			this.open_quick_dialog({});
		});
	}

	load_branches() {
		frappe.call({
			method: 'frappe.client.get_list',
			args: { doctype: 'Cost Center', fields: ['name'], limit_page_length: 0, order_by: 'name asc' },
		}).then((r) => {
			const opts = (r.message || [])
				.map((c) => `<option value="${frappe.utils.escape_html(c.name)}">${frappe.utils.escape_html(c.name)}</option>`)
				.join('');
			this.$branch_select.insertAdjacentHTML('beforeend', opts);
		});
	}

	setup_branch_filter() {
		if (this.is_admin) {
			this.load_branches();
			return;
		}
		// Cashiers / branch staff are locked to their own store — the
		// server already ignores any cost_center they pass, so don't
		// offer a picker that would silently do nothing.
		this.cost_center = this.user_cost_center;
		this.$branch_select.outerHTML = `<span class="salon-branch-locked">${frappe.utils.escape_html(
			this.user_cost_center || __('No store assigned')
		)}</span>`;
	}

	load_data() {
		const start = `${this.date} 00:00:00`;
		const next_day = new Date(this.date + 'T00:00:00');
		next_day.setDate(next_day.getDate() + 1);
		const end = `${this.format_date(next_day)} 00:00:00`;

		frappe.call({
			method: 'salon.api.get_calendar_data',
			args: { start, end, cost_center: this.cost_center },
		}).then((r) => {
			const msg = r.message || {};
			this.stylists = msg.stylists || [];
			this.bookings = msg.bookings || [];

			if (!this.scope_resolved) {
				this.scope_resolved = true;
				this.is_admin = msg.is_admin;
				this.user_cost_center = msg.user_cost_center;
				this.setup_branch_filter();
			}

			this.render_time_labels();
			this.render_columns();
			this.render_bookings();
			this.render_now_line();
		});
	}

	render_time_labels() {
		let html = '';
		for (let h = this.GRID_START_HOUR; h <= this.GRID_END_HOUR; h++) {
			const top = (h - this.GRID_START_HOUR) * 60 * this.PX_PER_MIN;
			html += `<div class="cal-time-label" style="top:${top}px">${String(h).padStart(2, '0')}:00</div>`;
		}
		this.$time_labels.innerHTML = html;
		this.$time_labels.style.height = this.grid_height() + 'px';
	}

	render_columns() {
		if (!this.stylists.length) {
			this.$columns_header.innerHTML = '';
			this.$columns_body.innerHTML = `<div class="cal-empty-msg">No stylists found${
				this.cost_center ? ' for this branch' : ''
			}. Add one under Stylists.</div>`;
			return;
		}

		this.$columns_header.innerHTML = this.stylists
			.map(
				(s) => `
			<div class="cal-col-header">
				<div class="cal-col-avatar">${this.initials(s.stylist_name || s.name)}</div>
				<div class="cal-col-name">${frappe.utils.escape_html(s.stylist_name || s.name)}</div>
			</div>
		`
			)
			.join('');

		const row_height = 30 * this.PX_PER_MIN;
		this.$columns_body.innerHTML = this.stylists
			.map(
				(s) => `
			<div class="cal-column-body" data-stylist="${frappe.utils.escape_html(s.name)}"
				style="height:${this.grid_height()}px; background-size: 100% ${row_height}px;"></div>
		`
			)
			.join('');

		this.$columns_body.querySelectorAll('.cal-column-body').forEach((col) => {
			col.addEventListener('click', (e) => {
				if (e.target !== col) return;
				const rect = col.getBoundingClientRect();
				const offset_y = e.clientY - rect.top;
				const minutes = this.snap(offset_y / this.PX_PER_MIN);
				const dt = this.minutes_to_datetime(minutes);
				this.open_quick_dialog({ salon_stylist: col.dataset.stylist, booking_datetime: dt });
			});
		});
	}

	render_bookings() {
		this.$columns_body.querySelectorAll('.cal-booking').forEach((el) => el.remove());

		this.bookings.forEach((b) => {
			const col = this.$columns_body.querySelector(
				`.cal-column-body[data-stylist="${CSS.escape(b.salon_stylist)}"]`
			);
			if (!col) return;

			const start_min = this.datetime_to_minutes(b.booking_datetime);
			const end_min = b.end_datetime ? this.datetime_to_minutes(b.end_datetime) : start_min + 30;
			const top = Math.max(0, start_min) * this.PX_PER_MIN;
			const height = Math.max(44, (end_min - start_min) * this.PX_PER_MIN - 2);
			const status_class = (b.status || '').toLowerCase().replace(/\s+/g, '-');
			const locked = this.LOCKED_STATUSES.includes(b.status);
			const services = b.services || [];

			const service_html = services
				.map(
					(s) =>
						`<span class="cal-booking-item" title="${frappe.utils.escape_html(
							s.item_name || s.item
						)}">${frappe.utils.escape_html(s.item)}</span>`
				)
				.join(', ');
			const card_title = `${this.format_time(b.booking_datetime)}–${this.format_time(
				b.end_datetime || b.booking_datetime
			)} · ${b.customer || ''} · ${services.map((s) => s.item_name || s.item).join(', ')}`;

			const el = document.createElement('div');
			el.className = `cal-booking status-${status_class}${locked ? ' locked' : ''}`;
			el.style.top = top + 'px';
			el.style.height = height + 'px';
			el.title = card_title;
			el.innerHTML = `
				<div class="cal-booking-time">${this.format_time(b.booking_datetime)}</div>
				<div class="cal-booking-client">${frappe.utils.escape_html(b.customer || '')}</div>
				<div class="cal-booking-service">${service_html}</div>
			`;
			this.bind_drag(el, b, locked);
			col.appendChild(el);
		});
	}

	bind_drag(el, booking, locked) {
		el.addEventListener('mousedown', (e) => {
			e.preventDefault();
			const start_x = e.clientX;
			const start_y = e.clientY;
			const orig_top = parseFloat(el.style.top);
			let moved = false;

			const on_move = (ev) => {
				if (locked) return;
				const dx = ev.clientX - start_x;
				const dy = ev.clientY - start_y;
				if (!moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
					moved = true;
					el.classList.add('dragging');
					document.body.classList.add('salon-cal-dragging');
				}
				if (!moved) return;

				let new_top = orig_top + dy;
				new_top = Math.max(0, Math.min(this.grid_height() - el.offsetHeight, new_top));
				el.style.top = new_top + 'px';

				const target_col = this.column_at_x(ev.clientX);
				if (target_col && target_col !== el.parentElement) {
					target_col.appendChild(el);
				}
			};

			const on_up = () => {
				document.removeEventListener('mousemove', on_move);
				document.removeEventListener('mouseup', on_up);
				el.classList.remove('dragging');
				document.body.classList.remove('salon-cal-dragging');

				if (!moved) {
					frappe.set_route('Form', 'Salon Booking', booking.name);
					return;
				}

				const final_col = el.parentElement;
				const final_minutes = this.snap(parseFloat(el.style.top) / this.PX_PER_MIN);
				el.style.top = final_minutes * this.PX_PER_MIN + 'px';
				const new_dt = this.minutes_to_datetime(final_minutes);
				const new_stylist = final_col.dataset.stylist;

				frappe
					.call({
						method: 'salon.api.reschedule_booking',
						args: { booking: booking.name, booking_datetime: new_dt, salon_stylist: new_stylist },
						freeze: true,
					})
					.then(() => {
						frappe.show_alert({ message: __('Booking rescheduled'), indicator: 'green' });
						this.load_data();
					})
					.catch(() => {
						this.load_data();
					});
			};

			document.addEventListener('mousemove', on_move);
			document.addEventListener('mouseup', on_up);
		});
	}

	column_at_x(client_x) {
		const cols = Array.from(this.$columns_body.querySelectorAll('.cal-column-body'));
		return cols.find((c) => {
			const r = c.getBoundingClientRect();
			return client_x >= r.left && client_x < r.right;
		});
	}


	render_now_line() {
		const today = frappe.datetime.get_today();
		if (this.date !== today) {
			this.$now_line.style.display = 'none';
			return;
		}
		const now = new Date();
		const minutes = now.getHours() * 60 + now.getMinutes() - this.GRID_START_HOUR * 60;
		const max_minutes = (this.GRID_END_HOUR - this.GRID_START_HOUR) * 60;
		if (minutes < 0 || minutes > max_minutes) {
			this.$now_line.style.display = 'none';
			return;
		}
		this.$now_line.style.display = 'block';
		this.$now_line.style.top = minutes * this.PX_PER_MIN + 'px';
	}

	open_quick_dialog(prefill) {
		const d = new frappe.ui.Dialog({
			title: __('New Booking'),
			fields: [
				{ fieldname: 'customer', label: __('Client'), fieldtype: 'Link', options: 'Customer', reqd: 1 },
				{
					fieldname: 'salon_stylist',
					label: __('Stylist'),
					fieldtype: 'Link',
					options: 'Salon Stylist',
					reqd: 1,
					default: prefill.salon_stylist,
				},
				{
					fieldname: 'booking_datetime',
					label: __('Date & Time'),
					fieldtype: 'Datetime',
					reqd: 1,
					default: prefill.booking_datetime,
				},
				{ fieldname: 'item', label: __('Service'), fieldtype: 'Link', options: 'Item', reqd: 1 },
			],
			primary_action_label: __('Create'),
			primary_action: (values) => {
				frappe
					.call({
						method: 'salon.api.create_quick_booking',
						args: Object.assign({}, values, { cost_center: this.cost_center }),
						freeze: true,
					})
					.then(() => {
						d.hide();
						frappe.show_alert({ message: __('Booking created'), indicator: 'green' });
						this.load_data();
					});
			},
		});
		d.show();
	}

	// -- helpers --

	parse_dt(str) {
		return new Date(str.replace(' ', 'T'));
	}

	datetime_to_minutes(str) {
		const d = this.parse_dt(str);
		return d.getHours() * 60 + d.getMinutes() - this.GRID_START_HOUR * 60;
	}

	minutes_to_datetime(minutes) {
		const base = new Date(this.date + 'T00:00:00');
		base.setHours(this.GRID_START_HOUR, 0, 0, 0);
		base.setMinutes(base.getMinutes() + minutes);
		const pad = (n) => String(n).padStart(2, '0');
		return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())} ${pad(
			base.getHours()
		)}:${pad(base.getMinutes())}:00`;
	}

	format_date(d) {
		const pad = (n) => String(n).padStart(2, '0');
		return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
	}

	format_time(str) {
		const d = this.parse_dt(str);
		const pad = (n) => String(n).padStart(2, '0');
		return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
	}

	snap(minutes) {
		return Math.max(0, Math.round(minutes / this.SNAP_MIN) * this.SNAP_MIN);
	}

	initials(name) {
		return (name || '')
			.split(' ')
			.map((p) => p[0])
			.filter(Boolean)
			.slice(0, 2)
			.join('')
			.toUpperCase();
	}
}
