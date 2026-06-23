frappe.ui.form.on('zzRetaining Salary', {

    refresh: function(frm) {
        toggle_mandatory_fields(frm);
    },

    pay_via_salary_slip: function(frm) {
        toggle_mandatory_fields(frm);
    },

    employee: function(frm) {
        frm.set_value('paid_off_periods', []);
        frm.set_value('employees', []);

        if (!frm.doc.employee) return;

        frappe.db.get_doc('Employee', frm.doc.employee).then(emp => {
            const rows = emp.paid_off_details || [];

            if (!rows.length) {
                frappe.throw({
                    title: __('No Paid Off Periods'),
                    message: __('This employee has no Paid Off Details on record.')
                });
                return;
            }

            rows.forEach(row => {
                frm.add_child('paid_off_periods', {
                    is_selected: 0,
                    paid_off: row.paid_off || '',
                    from_date: row.from_date || '',
                    to_date: row.to_date || '',
                    paid_off_days: row.paid_off_days || 0,
                    recall: row.recall || ''
                });
            });

            frm.refresh_field('paid_off_periods');
        });
    },

    salary_component: function(frm) {
        if (!frm.doc.salary_component || !frm.doc.company) return;

        frappe.db.get_doc('Salary Component', frm.doc.salary_component)
            .then(comp_doc => {
                const match = (comp_doc.accounts || []).find(
                    row => row.company === frm.doc.company
                );

                if (match) {
                    frm.set_value('expense_account', match.account);
                } else {
                    frm.set_value('expense_account', null);

                    frappe.throw({
                        title: __('No Account Found'),
                        message: __('The selected Salary Component has no account row for company {0}.', [frm.doc.company])
                    });
                }
            })
            .catch(() => {
                frappe.throw(
                    __('Unable to read Salary Component {0}', [frm.doc.salary_component])
                );
            });
    }
});


function toggle_mandatory_fields(frm) {

    if (cint(frm.doc.pay_via_salary_slip)) {

        frm.set_df_property('salary_component', 'reqd', 1);
        frm.set_df_property('expense_account', 'reqd', 0);

    } else {

        frm.set_df_property('salary_component', 'reqd', 0);
        frm.set_df_property('expense_account', 'reqd', 1);

    }

    frm.refresh_field('salary_component');
    frm.refresh_field('expense_account');
}