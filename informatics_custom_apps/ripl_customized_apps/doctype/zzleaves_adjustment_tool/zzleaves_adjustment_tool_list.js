frappe.listview_settings['zzLeaves Adjustment Tool'] = {
    add_fields: ["status", "docstatus"],

    get_indicator(doc) {
        if (doc.status === "Partially Updated")
            return ["Partially Updated", "orange"];

        if (doc.status === "Updated")
            return ["Updated", "green"];

        if (doc.status === "Draft")
            return ["Draft", "red"];

        if (doc.docstatus === 1)
            return ["Submitted", "blue"];

        if (doc.docstatus === 2)
            return ["Cancelled", "gray"];

        return ["Draft", "red"];
    }
};