frappe.listview_settings["Purchase Management System"] = {
  get_indicator: function (doc) {
    const status_colors = {
      Draft: "red",
      Pending: "orange",
      Approved: "green",
      Rejected: "red",
      Cancelled: "grey",
    };

    if (doc.status) {
      return [
        doc.status,
        status_colors[doc.status] || "grey",
        `status,=,${doc.status}`,
      ];
    }
  },

  formatters: {
    correction_type(value) {
      // Maps each correction type to a custom CSS class (defined in custom.css)
      const correction_classes = {
        "Wrong Accepted Quantity": "pms-ct-qty",
        "Wrong Purchase Order": "pms-ct-po",
        "Wrong Purchase Order and Supplier": "pms-ct-po-supplier",
        "Wrong Vehicle Number": "pms-ct-vehicle-no",
        "Wrong Driver Name": "pms-ct-driver",
        "Wrong Card Number": "pms-ct-card",
        "Wrong Transporter": "pms-ct-transporter",
        "Wrong Vehicle Type": "pms-ct-vehicle-type",
        "Wrong Weight": "pms-ct-weight",
        "Wrong Segment": "pms-ct-segment",
        "Inward/Outward Wrong Entry (Manual)": "pms-ct-inout",
        "Wrong Manual Entry": "pms-ct-manual",
      };

      if (!value) return "";

      const cls = correction_classes[value] || "pms-ct-default";

      return `
        <span class="filterable indicator-pill ellipsis pms-correction-tag ${cls}"
            data-filter="correction_type,=,${value}">
            <span class="indicator-dot"></span>
            ${value}
        </span>
      `;
    },
  },
};
