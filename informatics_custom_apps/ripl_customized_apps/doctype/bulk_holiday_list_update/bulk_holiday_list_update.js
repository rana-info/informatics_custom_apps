// Copyright (c) 2026, Yash and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Holiday List Update", {


    setup(frm) {
        frm.set_query("branch", function () {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    },


  refresh(frm) {
    frm.disable_save();

    if (!frm.custom_update_button_added) {
      frm
        .add_custom_button(__("Update"), () => {
          frm.trigger("update_holiday_list");
        })
        .addClass("btn-primary");

      frm.custom_update_button_added = true;
    }

    if (!frm.__islocal && !frm.__initialized) {
      frm.trigger("reset_form");
      frm.__initialized = true;
    }
  },

  reset_form(frm) {
    frm.set_value("old_holiday_list", "");
    frm.set_value("new_holiday_list", "");
    frm.set_value("selected_employees", "[]");

    frm.fields_dict.employee_html.$wrapper.empty();

    frm.refresh_fields();
  },

  update_holiday_list(frm) {
    if (!frm.doc.old_holiday_list) {
      frappe.throw(__("Please select Old Holiday List"));
    }

    if (!frm.doc.new_holiday_list) {
      frappe.throw(__("Please select New Holiday List"));
    }

    if (frm.doc.old_holiday_list === frm.doc.new_holiday_list) {
      frappe.throw(__("Old Holiday List and New Holiday List cannot be same"));
    }

    if (!frm.doc.selected_employees || frm.doc.selected_employees === "[]") {
      frappe.throw(__("Please select at least one employee"));
    }

    frappe
      .call({
        method: "update_holiday_list",
        doc: frm.doc,
        freeze: true,
        freeze_message: __("Updating Holiday List..."),
      })
      .then(() => {
        frappe.show_alert({
          message: __("Holiday List Updated Successfully"),
          indicator: "green",
        });

        frm.trigger("reset_form");
      });
  },

old_holiday_list(frm) {
    frm.set_value("selected_employees", "[]");
    frm.fields_dict.employee_html.$wrapper.empty();

    if (!frm.doc.old_holiday_list) {
        return;
    }

    if (!frm.doc.company) {
        frappe.throw(__("Please select Company first"));
    }

    if (!frm.doc.branch) {
        frappe.throw(__("Please select Plant first"));
    }

    frm.trigger("get_employee_data");
},

//   new_holiday_list(frm) {
//     frm.set_value("selected_employees", "[]");
//   },

new_holiday_list(frm) {
    if (
        frm.doc.old_holiday_list &&
        frm.doc.new_holiday_list &&
        frm.doc.old_holiday_list === frm.doc.new_holiday_list
    ) {
        frappe.throw(
            __("Old Holiday List and New Holiday List cannot be same")
        );
    }
},

company(frm) {
    frm.set_value("branch", "");
    frm.set_value("selected_employees", "[]");
    frm.fields_dict.employee_html.$wrapper.empty();

    if (frm.doc.old_holiday_list) {
        frm.trigger("get_employee_data");
    }
},

branch(frm) {
    frm.set_value("selected_employees", "[]");
    frm.fields_dict.employee_html.$wrapper.empty();

    if (frm.doc.old_holiday_list) {
        frm.trigger("get_employee_data");
    }
},

  get_employee_data(frm) {
    frappe
      .call({
        method: "get_employee_data",
        doc: frm.doc,
      })
      .then((r) => {
        frm.events.render_table(frm, r.message || []);
      });
  },

  render_table(frm, data) {
    let wrapper = frm.fields_dict.employee_html.$wrapper;
    wrapper.empty();

    if (!data.length) {
      wrapper.html(
        `<div class="text-muted">
					No active employees found for the selected Holiday List.
				</div>`,
      );
      return;
    }

    let html = `
			<table class="table table-bordered" id="emp-table">
				<thead>
					<tr>
						<th style="width:50px">
							<input type="checkbox" id="select-all">
						</th>
						<th>Employee</th>
						<th>Employee Name</th>
						<th>Holiday List</th>
					</tr>
					<tr>
						<th></th>
						<th>
							<input type="text"
								   class="form-control col-filter"
								   data-col="1"
								   placeholder="Search Employee">
						</th>
						<th>
							<input type="text"
								   class="form-control col-filter"
								   data-col="2"
								   placeholder="Search Name">
						</th>
						<th>
							<input type="text"
								   class="form-control col-filter"
								   data-col="3"
								   placeholder="Search Holiday List">
						</th>
					</tr>
				</thead>
				<tbody>
		`;

    data.forEach((row) => {
      html += `
				<tr>
					<td>
						<input
							type="checkbox"
							class="emp-check"
							data-emp="${row.employee}">
					</td>
					<td>${row.employee}</td>
					<td>${row.employee_name || ""}</td>
					<td>${row.holiday_list || ""}</td>
				</tr>
			`;
    });

    html += `
				</tbody>
			</table>
		`;

    wrapper.html(html);

    $("#select-all").on("change", function () {
      $(".emp-check").prop("checked", this.checked).trigger("change");
    });

    $(".emp-check").on("change", function () {
      let selected = [];

      $(".emp-check:checked").each(function () {
        selected.push($(this).data("emp"));
      });

      frm.set_value("selected_employees", JSON.stringify(selected));
    });

    $(".col-filter").on("keyup", function () {
      let col = $(this).data("col");
      let val = $(this).val().toLowerCase();

      $("#emp-table tbody tr").each(function () {
        let cell = $(this).find("td").eq(col).text().toLowerCase();
        text().toLowerCase();

        $(this).toggle(cell.includes(val));
      });
    });
  },
});
