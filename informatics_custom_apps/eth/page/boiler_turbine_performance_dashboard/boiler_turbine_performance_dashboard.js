console.log("Boiler Turbine Dashboard JS Loaded");

frappe.pages["boiler-turbine-performance-dashboard"].on_page_load = function (wrapper) {

    new BoilerTurbinePerformanceDashboard(wrapper);

};


class BoilerTurbinePerformanceDashboard {

    constructor(wrapper) {

        this.wrapper = $(wrapper);
        this.expanded = {};         // plant -> bool
        this.view_mode = "normal";  // "normal" | "error" - applies to ALL plants

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "Boiler & Turbine Performance Dashboard",
            single_column: true
        });

        this.make_filters();
        this.make_layout();
        this.load_dashboard();

    }


    make_filters() {

        this.date_field = this.page.add_field({
            label: "Date",
            fieldtype: "Date",
            fieldname: "date",
            default: frappe.datetime.get_today(),
            change: () => {
                this.load_dashboard();
            }
        });

        this.view_field = this.page.add_field({
            label: "View",
            fieldtype: "Select",
            fieldname: "view_mode",
            options: ["Normal", "Error"],
            default: "Normal",
            change: () => {

                const val = this.view_field.get_value();
                this.view_mode = val === "Error" ? "error" : "normal";

                if (this.dashboard_data) {
                    this.render_dashboard(this.dashboard_data);
                }

            }
        });

    }


    make_layout() {

        this.$container = $(`
            <div class="boiler-turbine-dashboard">

                <div class="dashboard-loading text-center"
                     style="display:none;padding:20px;">
                    Loading Dashboard...
                </div>


                <div class="plants-container"></div>

            </div>
        `);


        $(this.page.body).append(this.$container);

    }


    load_dashboard() {

        let date = this.date_field.get_value();

        console.log("Loading dashboard for date:", date);

        if (!date) {
            return;
        }

        this.$container.find(".dashboard-loading").show();

        frappe.call({

            method:
            "informatics_custom_apps.eth.page.boiler_turbine_performance_dashboard.boiler_turbine_performance_dashboard.get_dashboard",

            args: {
                date: date
            },

            callback: (r) => {

                this.$container.find(".dashboard-loading").hide();

                console.log("API Response:", r);

                if (r.message) {

                    console.log("Dashboard Data:", r.message);

                    this.dashboard_data = r.message;
                    this.expanded = {};
                    this.render_dashboard(this.dashboard_data);

                }

            },

            error: () => {

                this.$container.find(".dashboard-loading").hide();

                frappe.msgprint({
                    title: "Error",
                    message: "Failed to load dashboard data",
                    indicator: "red"
                });

            }

        });

    }


    bind_events() {

        // Click a plant row: expand/collapse only - mode is global now
        this.$container.find(".plant-row").off("click").on("click", (e) => {

            const plant = $(e.currentTarget).attr("data-plant");

            this.expanded[plant] = !this.expanded[plant];

            this.render_dashboard(this.dashboard_data);

        });

    }


    render_dashboard(data) {

        if (!data.plants || data.plants.length === 0) {

            this.$container.find(".plants-container").html(`
                <div class="text-center text-muted"
                     style="padding:40px;">
                    No data available for selected date
                </div>
            `);

            return;

        }

        const mode = this.view_mode;

        let html = `
            <div class="plant-accordion"
                 style="
                    border:1px solid #e0e0e0;
                    border-radius:8px;
                    overflow:hidden;
                 ">

                <div style="
                        padding:10px 16px;
                        background:#f8f9fa;
                        font-weight:600;
                        color:#555;
                        border-bottom:1px solid #e0e0e0;
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                    ">
                    <span>Plant</span>
                    <span style="
                        font-size:12px;
                        padding:3px 10px;
                        border-radius:12px;
                        color:#fff;
                        background:${mode === "error" ? "#dc3545" : "#0e7c86"};
                    ">
                        ${mode === "error" ? "Error View" : "Normal View"}
                    </span>
                </div>
        `;

        data.plants.forEach(plant => {

            const isExpanded = !!this.expanded[plant.plant];

            html += `
                <div class="plant-item" style="border-bottom:1px solid #eee;">

                    <div class="plant-row"
                         data-plant="${plant.plant}"
                         style="
                            display:flex;
                            align-items:center;
                            padding:12px 16px;
                            cursor:pointer;
                            user-select:none;
                            background:${isExpanded ? "#f1f8f9" : "#ffffff"};
                         ">

                        <span style="
                            display:inline-block;
                            width:16px;
                            margin-right:10px;
                            transition:transform .15s;
                            transform:rotate(${isExpanded ? "90deg" : "0deg"});
                        ">▶</span>

                        <span style="font-weight:600;color:#2c3e50;">
                            ${plant.plant}
                        </span>

                    </div>

                    <div class="plant-content"
                         style="
                            display:${isExpanded ? "block" : "none"};
                            padding:16px;
                            background:#fbfbfb;
                         ">

                        ${isExpanded ? `
                            ${this.render_dmr(plant.dmr)}
                            ${this.render_section("Feed Water", plant.feed_water, mode)}
                            ${this.render_section("Boiler Water", plant.boiler_water, mode)}
                            ${this.render_section("Steam", plant.steam, mode)}
                            ${this.render_fuel(plant.fuel)}
                        ` : ""}

                    </div>

                </div>
            `;

        });

        html += `</div>`;

        this.$container
            .find(".plants-container")
            .html(html);

        this.bind_events();

    }


    render_dmr(dmr) {

        let rows = "";

        if (!dmr || dmr.length === 0) {

            rows = `
                <tr>
                    <td colspan="8" class="text-center text-muted">-</td>
                </tr>
            `;

        } else {

            dmr.forEach(d => {

                rows += `
                    <tr>
                        <td>${d.parameter_name || "-"}</td>
                        <td>${d.engg_units || "-"}</td>
                        <td>${d.max_value !== null && d.max_value !== undefined ? d.max_value : "-"}</td>
                        <td>${d.max_value_time || "-"}</td>
                        <td>${d.min_value !== null && d.min_value !== undefined ? d.min_value : "-"}</td>
                        <td>${d.min_value_time || "-"}</td>
                        <td>${d.average_value !== null && d.average_value !== undefined ? d.average_value : "-"}</td>
                        <td>${d.total !== null && d.total !== undefined ? d.total : "-"}</td>
                    </tr>
                `;
            });

        }

        return `
            <h5 style="${this.section_label_style()}">Key Operational Parameters of Boiler & Turbine</h5>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Engg Units</th>
                        <th>Max Value</th>
                        <th>Time</th>
                        <th>Min Value</th>
                        <th>Time</th>
                        <th>Avg Value</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }


    render_fuel(fuel) {

        if (!fuel) return "";

        let rows = "";

        if (!fuel.fuel_rows || fuel.fuel_rows.length === 0) {

            rows = `
                <tr>
                    <td colspan="6" class="text-center text-muted">-</td>
                </tr>
            `;

        } else {

            fuel.fuel_rows.forEach(f => {

                rows += `
                    <tr>
                        <td>${f.item_name || "-"}</td>
                        <td>${f.consumption_ton !== null && f.consumption_ton !== undefined ? f.consumption_ton : "-"}</td>
                        <td>${f.pct_total_fuel !== null && f.pct_total_fuel !== undefined ? f.pct_total_fuel + "%" : "-"}</td>
                        <td>${f.pct_moisture !== null && f.pct_moisture !== undefined ? f.pct_moisture + "%" : "-"}</td>
                        <td>${f.pct_dust !== null && f.pct_dust !== undefined ? f.pct_dust + "%" : "-"}</td>
                        <td>${f.last_price !== null && f.last_price !== undefined ? f.last_price : "-"}</td>
                    </tr>
                `;
            });

        }

        const rupeesPerDay = fuel.rupees_per_day !== null && fuel.rupees_per_day !== undefined
            ? fuel.rupees_per_day
            : "-";

        const perTonSteam = fuel.per_ton_steam !== null && fuel.per_ton_steam !== undefined
            ? fuel.per_ton_steam
            : "-";

        return `
            <h5 style="${this.section_label_style()}">Boiler Fuel Parameters</h5>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Item Name</th>
                        <th>Consumption (TPD)</th>
                        <th>% of Total Fuel</th>
                        <th>% Moisture</th>
                        <th>% Dust</th>
                        <th>Last Price</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>

            <h5 style="${this.section_label_style()}">Fuel Cost</h5>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Rupees Per Day</th>
                        <th>Per Ton Steam</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>${rupeesPerDay}</td>
                        <td>${perTonSteam}</td>
                    </tr>
                </tbody>
            </table>
        `;
    }


    render_section(title, section, mode = "normal") {

        if (!section) return "";

        let rows = "";

        Object.keys(section).forEach(param => {

            const d = section[param];

            if (
                mode === "error" &&
                !["High", "Low"].includes(d.status)
            ) {
                return;
            }

            const avgStyle = this.status_cell_style(d.status);
            const badge = this.status_badge(d.status);
            const unit = this.format_unit(param);

            const avgDisplay = d.average !== null
                ? `${d.average}${unit ? " " + unit : ""}`
                : "-";

            rows += `
                <tr>
                    <td>${this.format_label(param)}</td>
                    <td style="${avgStyle}">${avgDisplay}</td>
                    <td>${d.norm_min !== null && d.norm_min !== undefined ? d.norm_min : "-"}</td>
                    <td>${d.norm_max !== null && d.norm_max !== undefined ? d.norm_max : "-"}</td>
                    <td>${badge}</td>
                </tr>
            `;

        });

        if (!rows) {
            rows = `
                <tr>
                    <td colspan="5" class="text-center text-success">
                        No abnormal parameters
                    </td>
                </tr>
            `;
        }

        return `
            <h5 style="${this.section_label_style()}">${title}</h5>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Value (Avg)</th>
                        <th>Min</th>
                        <th>Max</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }


    section_label_style() {

        return `
            display:inline-block;
            background-color:#e8f0fe;
            color:#1a3c6e;
            padding:4px 12px;
            border-radius:4px;
            border-left:4px solid #0e7c86;
            margin-bottom:10px;
            font-weight:600;
        `.replace(/\s+/g, " ");

    }


    format_label(param) {

        const labels = {
            ph: "pH",
            conductivity: "Conductivity",
            silica: "Silica"
        };

        return labels[param] || param;

    }


    format_unit(param) {

        // Fixed units per parameter so display is consistent
        // regardless of what (if anything) was typed into the
        // norms table's Unit field.
        const units = {
            ph: "",
            conductivity: "µS/cm",
            silica: "ppm"
        };

        return units[param] !== undefined ? units[param] : "";

    }


    status_cell_style(status) {

        // Only flag deviations - Normal stays uncolored
        const bg = {
            "High": "#f8d7da",     // red
            "Low": "#cce5f6"       // light blue
        };

        const color = bg[status];

        return color ? `background-color:${color};font-weight:600;` : "";

    }


    status_badge(status) {

        const colors = {
            "High": "red",
            "Normal": "green",
            "Low": "blue",
            "No Data": "grey",
            "No Norm": "grey"
        };

        const color = colors[status] || "grey";

        return `<span class="indicator-pill ${color}">${status}</span>`;
    }

}