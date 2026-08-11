console.log("Plant Violations Dashboard JS Loaded");

frappe.pages["md-dashboard"].on_page_load = function (wrapper) {

    new MDDashboard(wrapper);

};


class MDDashboard {

    constructor(wrapper) {

        this.wrapper = $(wrapper);

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "Plant Compliance Overview",
            single_column: true
        });

        this.make_filters();
        this.make_layout();
        this.load_violations();

    }


    make_filters() {

        const yesterday = frappe.datetime.add_days(frappe.datetime.get_today(), -1);

        this.date_field = this.page.add_field({
            label: "Date",
            fieldtype: "Date",
            fieldname: "date",
            default: yesterday,
            change: () => {
                this.load_violations();
            }
        });

    }


    make_layout() {

        this.$container = $(`
            <div class="md-dashboard">

                <div class="violations-loading text-center"
                     style="display:none;padding:20px;">
                    Loading...
                </div>

                <div class="violations-matrix"></div>

            </div>
        `);

        $(this.page.body).append(this.$container);

    }


    load_violations() {

        const date = this.date_field.get_value();

        if (!date) {
            return;
        }

        this.$container.find(".violations-loading").show();

        frappe.call({

            method:
            "informatics_custom_apps.eth.page.md_dashboard.md_dashboard.get_violations",

            args: { date: date },

            callback: (r) => {

                this.$container.find(".violations-loading").hide();

                if (r.message) {
                    this.data = r.message;
                    this.render_matrix();
                }

            },

            error: () => {

                this.$container.find(".violations-loading").hide();

                frappe.msgprint({
                    title: "Error",
                    message: "Failed to load violations data",
                    indicator: "red"
                });

            }

        });

    }


    render_matrix() {

        const data = this.data;

        if (!data.plants || data.plants.length === 0) {

            this.$container.find(".violations-matrix").html(`
                <div class="text-center text-muted" style="padding:40px;">
                    No plant data found for this date.
                </div>
            `);

            return;

        }

        const headerStyle = "text-align:center;padding:10px 10px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;";
        const headerStyleTotal = "text-align:center;padding:10px 14px;font-weight:500;background:#042C53;color:#ffffff;border:0.5px solid #042C53;";
        const plantCellStyle = "padding:9px 14px;font-weight:500;background:#E6F1FB;color:#042C53;border:0.5px solid #C8C6BD;";
        const totalCellStyle = "text-align:center;padding:9px 14px;font-weight:500;background:#B5D4F4;color:#042C53;border:0.5px solid #C8C6BD;";
        const violationCellStyle = "text-align:center;padding:9px;font-weight:500;color:#501313;background:#F7C1C1;border:0.5px solid #C8C6BD;cursor:pointer;";
        const cleanCellStyle = "text-align:center;padding:9px;font-weight:500;color:#173404;background:#C0DD97;border:0.5px solid #C8C6BD;";
        const noDataCellStyle = "text-align:center;padding:9px;color:#6B6A64;background:#F1EFE8;border:0.5px solid #C8C6BD;font-size:11px;font-style:italic;";

        let headerCells = data.sources.map(src => `<th style="${headerStyle}">${src}</th>`).join("");

        let rows = "";

        data.plants.forEach(p => {

            let cells = data.sources.map(src => {

                const s = p.sources[src];

                // s === undefined/null -> no doc submitted at all for
                // this plant/source/date. s.count === 0 -> a doc WAS
                // submitted and nothing violated.
                if (!s) {
                    return `<td style="${noDataCellStyle}">No Data</td>`;
                }

                if (s.count === 0) {
                    return `<td style="${cleanCellStyle}">-</td>`;
                }

                return `
                    <td data-plant="${p.plant}" data-source="${src}"
                        class="violation-cell" style="${violationCellStyle}">
                        ${s.count}
                    </td>
                `;

            }).join("");

            rows += `
                <tr>
                    <td style="${plantCellStyle}">${p.plant}</td>
                    ${cells}
                    <td style="${totalCellStyle}">${p.total}</td>
                </tr>
            `;

        });

        const html = `
            <table style="width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed;margin-top:10px;">
                <thead>
                    <tr>
                        <th style="text-align:left;padding:10px 14px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;width:20%;">Plant</th>
                        ${headerCells}
                        <th style="${headerStyleTotal}">Total</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;

        this.$container.find(".violations-matrix").html(html);

        this.bind_events();

    }


    bind_events() {

        this.$container.find(".violation-cell").off("click").on("click", (e) => {

            const plant = $(e.currentTarget).attr("data-plant");
            const source = $(e.currentTarget).attr("data-source");

            this.show_drilldown(plant, source);

        });

    }


    show_drilldown(plant, source) {

        const plantData = this.data.plants.find(p => p.plant === plant);

        if (!plantData) return;

        const sourceData = plantData.sources[source];

        let rows = "";

        (sourceData.parameters || []).forEach(param => {

            const valuesText = param.values.join(", ");

            rows += `
                <tr>
                    <td style="padding:9px 12px;font-weight:500;background:#E6F1FB;color:#042C53;border:0.5px solid #C8C6BD;">${param.label}</td>
                    <td style="padding:9px 12px;color:#501313;font-weight:600;background:#F7C1C1;border:0.5px solid #C8C6BD;">${valuesText}</td>
                    <td style="padding:9px 12px;border:0.5px solid #C8C6BD;">${param.unit || "-"}</td>
                    <td style="padding:9px 12px;border:0.5px solid #C8C6BD;">${param.min !== null && param.min !== undefined ? param.min : "-"}</td>
                    <td style="padding:9px 12px;border:0.5px solid #C8C6BD;">${param.max !== null && param.max !== undefined ? param.max : "-"}</td>
                </tr>
            `;

        });

        const d = new frappe.ui.Dialog({
            title: `${plant} - ${source} Violations`,
            size: "large",
            fields: [
                {
                    fieldtype: "HTML",
                    options: `
                        <table style="width:100%;border-collapse:collapse;font-size:13px;">
                            <thead>
                                <tr>
                                    <th style="text-align:left;padding:10px 12px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;">Parameter</th>
                                    <th style="text-align:left;padding:10px 12px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;">Value(s) Out of Range</th>
                                    <th style="text-align:left;padding:10px 12px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;">UOM</th>
                                    <th style="text-align:left;padding:10px 12px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;">Min</th>
                                    <th style="text-align:left;padding:10px 12px;font-weight:500;background:#0C447C;color:#ffffff;border:0.5px solid #042C53;">Max</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    `
                }
            ]
        });

        d.show();

    }

}