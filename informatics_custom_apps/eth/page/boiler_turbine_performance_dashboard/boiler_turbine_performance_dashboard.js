console.log("Boiler Turbine Dashboard JS Loaded");

frappe.pages["boiler-turbine-performance-dashboard"].on_page_load = function (wrapper) {

    new BoilerTurbinePerformanceDashboard(wrapper);

};


class BoilerTurbinePerformanceDashboard {

    constructor(wrapper) {

        this.wrapper = $(wrapper);

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

                    this.render_dashboard(r.message);

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


    render_dashboard(data) {

        let html = "";

        if (!data.plants || data.plants.length === 0) {

            html = `
                <div class="text-center text-muted"
                     style="padding:40px;">
                    No data available for selected date
                </div>
            `;

            this.$container.find(".plants-container").html(html);
            return;

        }

        data.plants.forEach(plant => {

            html += `

                <div class="card"
                     style="
                        margin-bottom:20px;
                        border-radius:10px;
                     ">


                    <div class="card-header"
                         style="
                            text-align:center;
                            background-color:#0e7c86;
                            color:#ffffff;
                            border-radius:10px 10px 0 0;
                         ">
                        <h4 style="margin:0;">
                            ${plant.plant}
                        </h4>
                    </div>


                    <div class="card-body">

                        ${this.render_dmr(plant.dmr)}

                        ${this.render_section("Feed Water", plant.feed_water)}

                        ${this.render_section("Boiler Water", plant.boiler_water)}

                        ${this.render_section("Steam", plant.steam)}

                    </div>

                </div>

            `;

        });


        this.$container
            .find(".plants-container")
            .html(html);

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


    render_section(title, section) {

        if (!section) return "";

        let rows = "";

        Object.keys(section).forEach(param => {

            const d = section[param];
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