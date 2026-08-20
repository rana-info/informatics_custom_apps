console.log("hide_delete_permission.js loaded");
frappe.router.on("change", () => {
    if (frappe.get_route()[0] !== "permission-manager") {
        return;
    }

    if (frappe.user.has_role("Master Admin")) {
        return;
    }

    const hide_delete_permissions = () => {

        $("label").filter(function () {
            return $(this).text().trim() === "Delete";
        }).each(function () {
            $(this).closest(".form-check").hide();
        });

        $(".perm-item").each(function () {
            const label = $(this).find("label").text().trim();

            if (label === "Delete") {
                $(this).hide();
            }
        });
    };

    hide_delete_permissions();

    const observer = new MutationObserver(() => {
        hide_delete_permissions();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});