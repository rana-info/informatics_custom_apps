frappe.ui.form.on("Loan Repayment Schedule", {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.status === "Active" && frm.session.user.has_role("HR Manager")) {
      frm.add_custom_button(
        __("Skip Instalments"),
        () => show_skip_dialog(frm),
        __("Actions")
      );
    }
  },
});

function show_skip_dialog(frm) {
  frappe.call({
    method:
      "informatics_custom_apps.ripl_customized_apps.custom_buttons.get_skippable_instalments",
    args: { schedule: frm.doc.name },
    callback(r) {
      const rows = r.message || [];
      if (!rows.length) {
        return frappe.msgprint(__("No unpaid instalments found."));
      }

      const d = new frappe.ui.Dialog({
        title: __("Select instalments to skip"),
        size: "large",
        fields: [
          {
            fieldname: "instalments",
            fieldtype: "Table",
            cannot_add_rows: true,
            cannot_delete_rows: true,
            data: rows,
            get_data: () => rows,
            fields: [
              {
                fieldname: "row_name",
                fieldtype: "Data",
                read_only: 1,
                hidden: 1,
              },
              {
                fieldname: "payment_date",
                fieldtype: "Date",
                label: __("Payment Date"),
                read_only: 1,
                in_list_view: 1,
                columns: 3,
              },
              {
                fieldname: "total_payment",
                fieldtype: "Currency",
                label: __("Amount"),
                read_only: 1,
                in_list_view: 1,
                columns: 3,
              },
            ],
          },
        ],
        primary_action_label: __("Skip Selected"),
        primary_action() {
          const sel = d.fields_dict.instalments.grid.get_selected_children();
          if (!sel.length) {
            return frappe.msgprint(__("Select at least one row."));
          }
          frappe.call({
            method:
              "informatics_custom_apps.ripl_customized_apps.custom_buttons.skip_instalments",
            args: {
              schedule: frm.doc.name,
              row_names: sel.map((s) => s.row_name),
            },
            freeze: true,
            callback() {
              d.hide();
              frm.reload_doc();
            },
          });
        },
      });

      d.show();

      // Fallback: hide delete controls if the Frappe version ignores cannot_delete_rows
      d.$wrapper.find(".grid-remove-rows, .grid-delete-row").hide();
    },
  });
}