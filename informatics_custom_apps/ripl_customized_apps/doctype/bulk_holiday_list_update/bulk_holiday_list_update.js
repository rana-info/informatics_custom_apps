// Copyright (c) 2026, Yash and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Holiday List Update", {
	refresh(frm) {

        if(frm.doc.old_holiday_list && frm.doc.new_holiday_list && frm.doc.old_holiday_list === frm.doc.new_holiday_list){
            frappe.throw("New Holiday List and Old Holiday List cant be same");
        }

        frm.set_value("old_holiday_list", null);
        frm.set_value("new_holiday_list", null);
        frm.set_value("old_holiday_list_from_date", null);
        frm.set_value("old_holiday_list_to_date", null);
        frm.set_value("new_holiday_list_from_date", null);
        frm.set_value("new_holiday_list_to_date", null);
        frm.set_value("selected_employees","[]")

        frm.refresh_fields();
	},
    before_save(frm){
        if (!frm.doc.selected_employees || frm.doc.selected_employees === "[]") {
            frappe.throw("Please select at least one employee");
        }
    },
    after_save(frm){
        frm.set_value("old_holiday_list", null);
        frm.set_value("new_holiday_list", null);

        frm.refresh_fields();
    },

    old_holiday_list(frm) {
        frm.set_value("selected_employees", "[]"); 
        frm.fields_dict.employee_html.$wrapper.empty();
        if (!frm.doc.old_holiday_list) {
            return;
        }
        frm.trigger("get_employee_data");
    },
    new_holiday_list(){
        frm.set_value("selected_employees", "[]");  
    },

    get_employee_data(frm) {
        frappe.call({
            method: "get_employee_data",
            doc: frm.doc
        }).then(r => {
            frm.events.render_table(frm, r.message || []);
        });
    },

    render_table(frm, data) {
    let wrapper = frm.fields_dict.employee_html.$wrapper;
    wrapper.empty();

    if (!data.length) {
        wrapper.html("<p>No employees found.</p>");
        return;
    }

    let html = `
        <table class="table table-bordered" id="emp-table">
            <thead>
                <tr>
                    <th><input type="checkbox" id="select-all"></th>
                    <th>Employee</th>
                    <th>Name</th>
                    <th>Holiday List</th>
                </tr>
                <tr>
                    <th></th>
                    <th><input type="text" class="col-filter" data-col="1"></th>
                    <th><input type="text" class="col-filter" data-col="2"></th>
                    <th><input type="text" class="col-filter" data-col="3"></th>
                </tr>
            </thead>
            <tbody>
    `;

    data.forEach(row => {
        html += `
            <tr>
                <td><input type="checkbox" class="emp-check" data-emp="${row.employee}"></td>
                <td>${row.employee}</td>
                <td>${row.employee_name}</td>
                <td>${row.holiday_list}</td>
            </tr>
        `;
    });

    html += "</tbody></table>";
    wrapper.html(html);

    $("#select-all").on("change", function () {
        $(".emp-check").prop("checked", this.checked).trigger("change");
    });

    $(".emp-check").on("change", function () {
        let selected = [];
        $(".emp-check:checked").each(function () {
            selected.push($(this).attr("data-emp"));
        });
        frm.set_value("selected_employees", JSON.stringify(selected));
    });

    $(".col-filter").on("keyup", function () {
        let col = $(this).data("col");
        let val = $(this).val().toLowerCase();

        $("#emp-table tbody tr").each(function () {
            let cell = $(this).find("td").eq(col).text().toLowerCase();
            $(this).toggle(cell.includes(val));
        });
    });
}

});
