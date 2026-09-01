window.salon_common = {
	nav_groups: [
		{
			title: 'Salon Operations',
			items: [
				{ key: 'dashboard', label: 'Dashboard', href: '/app/salon-dashboard' },
				{ key: 'calendar', label: 'Calendar', href: '/app/salon-calendar' },
				{ key: 'bookings', label: 'Bookings', href: '/app/salon-booking' },
				{ key: 'clients', label: 'Clients (CRM)', href: '/app/customer' },
			],
		},
		{
			title: 'Programs',
			items: [
				{ key: 'loyalty', label: 'Loyalty', href: '/app/loyalty-program' },
				{ key: 'packages', label: 'Packages', href: '/app/package-subscription' },
				{ key: 'services', label: 'Services', href: '/app/item' },
			],
		},
		{
			title: 'Accounts — ERPNext',
			items: [
				{ key: 'pos', label: 'POS & Invoicing', href: '/app/sales-invoice' },
				{ key: 'gl', label: 'GL Postings', href: '/app/gl-entry' },
			],
		},
		{
			title: 'Inventory — ERPNext',
			items: [{ key: 'stock', label: 'Stock & Consumables', href: '/app/stock-entry' }],
		},
		{
			title: 'HR & Payroll — ERPNext',
			items: [
				{ key: 'stylists', label: 'Stylists / Employees', href: '/app/salon-stylist' },
				{ key: 'payroll', label: 'Payroll & Commissions', href: '/app/salary-slip' },
			],
		},
		{
			title: 'Finance — ERPNext',
			items: [{ key: 'pnl', label: 'P&L by Branch', href: '/app/query-report/Profit and Loss Statement' }],
		},
	],

	render_sidebar_html(active_key) {
		const groups = this.nav_groups
			.map((group) => {
				const links = group.items
					.map((item) => {
						const cls = item.key === active_key ? 'active' : '';
						return `<a class="${cls}" href="${item.href}">${item.label}</a>`;
					})
					.join('');
				return `
					<div class="salon-nav-group">
						<div class="salon-nav-group-title">${group.title}</div>
						<nav>${links}</nav>
					</div>
				`;
			})
			.join('');

		return `
			<aside class="salon-sidebar">
				<div class="salon-brand">
					<span class="salon-brand-dot"></span>
					<span>Salon Suite</span>
				</div>
				${groups}
			</aside>
		`;
	},
};
