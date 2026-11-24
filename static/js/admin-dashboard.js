
"use strict";

document.addEventListener("DOMContentLoaded", async () => {
    const $ = (selector) => document.querySelector(selector);

    const tokenKey = "abbikayga_admin_token";
    const profileKey = "abbikayga_admin_profile";
    const token = sessionStorage.getItem(tokenKey);

    const dashboardMessage = $("#dashboard-message");
    const pendingContainer = $("#pending-listings");
    const categoriesContainer = $("#admin-categories");
    const reportsContainer = $("#admin-reports");
    const pendingImageObjectUrls = new Set();

    function clearPendingImageObjectUrls() {
        for (const url of pendingImageObjectUrls) {
            URL.revokeObjectURL(url);
        }
        pendingImageObjectUrls.clear();
    }

    async function loadPendingImagePreview(wrapper, imageRecord) {
        try {
            if (
                typeof imageRecord?.image_url !== "string"
            ) {
                throw new Error("Invalid image record.");
            }

            const storedUrl = new URL(
                imageRecord.image_url,
                window.location.origin
            );

            if (
                storedUrl.origin !== window.location.origin ||
                !storedUrl.pathname.startsWith("/listing-images/")
            ) {
                throw new Error("Invalid image URL.");
            }

            const filename = storedUrl.pathname.split("/").pop();

            if (!/^[0-9a-f]{32}\.webp$/.test(filename)) {
                throw new Error("Invalid image filename.");
            }

            const response = await fetch(
                `/admin/listing-images/${encodeURIComponent(filename)}`,
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        Accept: "image/webp"
                    },
                    cache: "no-store"
                }
            );

            if (response.status === 401) {
                sessionStorage.removeItem(tokenKey);
                sessionStorage.removeItem(profileKey);
                window.location.replace("/admin/login");
                return;
            }

            if (!response.ok) {
                throw new Error("Image preview unavailable.");
            }

            const contentType = response.headers.get("content-type") || "";

            if (!contentType.includes("image/webp")) {
                throw new Error("Unexpected image format.");
            }

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);

            // Avoid retaining URLs for cards that were removed by a refresh.
            if (!document.contains(wrapper)) {
                URL.revokeObjectURL(objectUrl);
                return;
            }

            pendingImageObjectUrls.add(objectUrl);

            const image = element("img", "admin-image-preview");
            image.alt = "Pending advertisement photo";
            image.loading = "lazy";
            image.src = objectUrl;

            wrapper.replaceChildren(image);
        } catch {
            if (document.contains(wrapper)) {
                wrapper.replaceChildren(
                    element("span", "admin-image-fallback", "Preview unavailable")
                );
            }
        }
    }

    if (!token) {
        window.location.replace("/admin/login");
        return;
    }

    function element(tag, className = "", text = "") {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) {
            node.textContent = String(text);
        }
        return node;
    }

    function button(text, className, onClick) {
        const node = element("button", `button ${className}`, text);
        node.type = "button";
        node.addEventListener("click", onClick);
        return node;
    }

    function showMessage(text, isError = false) {
        dashboardMessage.textContent = text;
        dashboardMessage.className = isError
            ? "message message-error"
            : "message";
        dashboardMessage.hidden = false;
    }

    function showLocalMessage(target, text, isError = false) {
        target.textContent = text;
        target.className = isError
            ? "message message-error"
            : "message";
        target.hidden = false;
    }

    function clearLocalMessage(target) {
        target.hidden = true;
        target.textContent = "";
    }

    async function apiFetch(path, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("Authorization", `Bearer ${token}`);
        headers.set("Accept", "application/json");

        if (options.body !== undefined &&
            !(options.body instanceof FormData) &&
            !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }

        let response;

        try {
            response = await fetch(path, {
                ...options,
                headers,
                cache: "no-store"
            });
        } catch {
            throw new Error("Cannot connect to the API. Check that the server is running.");
        }

        const contentType = response.headers.get("content-type") || "";
        const data = contentType.includes("application/json")
            ? await response.json().catch(() => ({}))
            : await response.text();

        if (response.status === 401) {
            sessionStorage.removeItem(tokenKey);
            sessionStorage.removeItem(profileKey);
            window.location.replace("/admin/login");
            throw new Error("Your administrator session expired. Please sign in again.");
        }

        if (response.status === 429) {
            throw new Error("Too many requests. Please wait before trying again.");
        }

        if (!response.ok) {
            const detail = typeof data?.detail === "string"
                ? data.detail
                : `Request failed (HTTP ${response.status}).`;
            throw new Error(detail);
        }

        return data;
    }

    function clearContainer(container, message) {
        container.replaceChildren(element("p", "admin-empty", message));
    }

    function statusBadge(status) {
        return element("span", `admin-status status-${status}`, status);
    }

    function formattedDate(value) {
        if (!value) return "Unknown date";

        const date = new Date(value);
        return Number.isNaN(date.getTime())
            ? String(value)
            : date.toLocaleString();
    }

    function formatPrice(listing) {
        if (listing.listing_type === "free") return "Free giveaway";

        const price = Number(listing.price);
        if (!Number.isFinite(price)) return "Price not set";

        return new Intl.NumberFormat("en-PK", {
            style: "currency",
            currency: "PKR",
            maximumFractionDigits: 0
        }).format(price);
    }

    function makeField(labelText, value) {
        const wrapper = element("div", "admin-detail");
        wrapper.append(element("strong", "", labelText));
        wrapper.append(element("span", "", value || "Not provided"));
        return wrapper;
    }

    function createListingCard(listing) {
        const card = element("article", "admin-record-card");
        const heading = element("div", "admin-record-heading");

        const titleBlock = element("div");
        titleBlock.append(
            element("h3", "", `${listing.title} (#${listing.id})`)
        );
        titleBlock.append(
            element("p", "admin-muted", `Submitted ${formattedDate(listing.created_at)}`)
        );

        heading.append(titleBlock, statusBadge(listing.status));
        card.append(heading);

        card.append(element("p", "admin-record-description", listing.description));

        const details = element("div", "admin-detail-grid");
        details.append(
            makeField("Price", formatPrice(listing)),
            makeField("Category ID", listing.category_id),
            makeField("Location", [listing.location_details, listing.city]
                .filter(Boolean).join(", ")),
            makeField("Condition", listing.condition),
            makeField("Seller", listing.seller_name),
            makeField("Phone", listing.seller_phone),
            makeField("Photos attached", Array.isArray(listing.images)
                ? listing.images.length
                : 0)
        );
        card.append(details);

        if (Array.isArray(listing.images) && listing.images.length) {
            const gallery = element("div", "admin-image-gallery");

            listing.images.slice(0, 3).forEach((imageRecord, index) => {
                const wrapper = element("div", "admin-image-frame");

                wrapper.append(
                    element("span", "admin-image-loading", `Photo ${index + 1}`)
                );

                gallery.append(wrapper);
                loadPendingImagePreview(wrapper, imageRecord);
            });

            card.append(gallery);
        }

        const actions = element("div", "admin-record-actions");

        actions.append(button("Approve", "button-primary", async () => {
            await moderateListing(listing.id, "approved", null);
        }));

        actions.append(button("Reject", "button-secondary", async () => {
            const reason = window.prompt(
                "Enter the reason for rejecting this advertisement:"
            );

            if (reason === null) return;

            if (!reason.trim()) {
                showMessage("A rejection reason is required.", true);
                return;
            }

            await moderateListing(listing.id, "rejected", reason.trim());
        }));

        actions.append(button("Remove", "button-danger", async () => {
            if (!window.confirm(`Remove listing #${listing.id}?`)) return;
            await moderateListing(listing.id, "removed", null);
        }));

        card.append(actions);
        return card;
    }

    async function moderateListing(id, status, rejectionReason) {
        try {
            const payload = { status };

            if (status === "rejected") {
                payload.rejection_reason = rejectionReason;
            }

            await apiFetch(`/admin/listings/${id}/moderation`, {
                method: "PATCH",
                body: JSON.stringify(payload)
            });

            showMessage(`Listing #${id} updated to "${status}".`);
            await loadPendingListings();
        } catch (error) {
            showMessage(error.message, true);
        }
    }

    async function loadPendingListings() {
        clearPendingImageObjectUrls();
        clearContainer(pendingContainer, "Loading pending advertisements...");

        try {
            const data = await apiFetch("/admin/listings/pending");
            const listings = Array.isArray(data) ? data : [];

            if (!listings.length) {
                clearContainer(pendingContainer, "There are no pending advertisements.");
                return;
            }

            pendingContainer.replaceChildren();

            listings.forEach((listing) => {
                pendingContainer.append(createListingCard(listing));
            });
        } catch (error) {
            clearContainer(pendingContainer, error.message);
        }
    }

    function slugify(value) {
        return value
            .normalize("NFKD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .trim()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
    }



    async function loadCategories() {
        clearContainer(categoriesContainer, "Loading categories...");

        try {
            const categories = await apiFetch("/admin/categories/");

            if (!Array.isArray(categories) || !categories.length) {
                clearContainer(categoriesContainer, "No categories found.");
                return;
            }

            const table = element("table", "admin-table");
            const thead = element("thead");
            const headerRow = element("tr");

            ["Name", "Slug", "Status", "Action"].forEach((label) => {
                headerRow.append(element("th", "", label));
            });

            thead.append(headerRow);
            table.append(thead);

            const tbody = element("tbody");

            categories.forEach((category) => {
                const row = element("tr");

                row.append(element("td", "", category.name));
                row.append(element("td", "", category.slug));
                row.append(element(
                    "td",
                    "",
                    category.is_active ? "Active" : "Inactive"
                ));

                const actionCell = element("td");
                const nextState = !category.is_active;

                actionCell.append(button(
                    nextState ? "Activate" : "Deactivate",
                    nextState ? "button-primary" : "button-secondary",
                    async () => {
                        try {
                            const params = new URLSearchParams({
                                is_active: String(nextState)
                            });

                            await apiFetch(
                                `/admin/categories/${category.id}/status?${params}`,
                                { method: "PATCH" }
                            );

                            showMessage(`Category "${category.name}" updated.`);
                            await loadCategories();
                        } catch (error) {
                            showMessage(error.message, true);
                        }
                    }
                ));

                row.append(actionCell);
                tbody.append(row);
            });

            table.append(tbody);
            categoriesContainer.replaceChildren(table);
        } catch (error) {
            clearContainer(categoriesContainer, error.message);
        }
    }

    const categoryNameInput = $("#category-name");
    const categorySlugInput = $("#category-slug");
    const categoryForm = $("#category-create-form");
    const categoryCreateMessage = $("#category-create-message");

    if (categoryNameInput && categorySlugInput && categoryForm) {
        categoryNameInput.addEventListener("input", () => {
            if (!categorySlugInput.dataset.edited) {
                categorySlugInput.value = slugify(categoryNameInput.value);
            }
        });

        categorySlugInput.addEventListener("input", () => {
            categorySlugInput.dataset.edited = "true";
            categorySlugInput.value = slugify(categorySlugInput.value);
        });

        categoryForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            clearLocalMessage(categoryCreateMessage);

            if (!categoryForm.reportValidity()) return;

            const payload = {
                name: categoryNameInput.value.trim(),
                slug: categorySlugInput.value.trim()
            };

            try {
                await apiFetch("/admin/categories/", {
                    method: "POST",
                    body: JSON.stringify(payload)
                });

                categoryForm.reset();
                delete categorySlugInput.dataset.edited;

                showLocalMessage(
                    categoryCreateMessage,
                    "Category created successfully."
                );

                showMessage("Category created successfully.");
                await loadCategories();
            } catch (error) {
                showLocalMessage(categoryCreateMessage, error.message, true);
            }
        });
    }

    function createReportCard(report) {
        const card = element("article", "admin-record-card");
        const heading = element("div", "admin-record-heading");

        const titleBlock = element("div");
        titleBlock.append(element(
            "h3",
            "",
            `Report #${report.id}: ${report.listing_title}`
        ));
        titleBlock.append(element(
            "p",
            "admin-muted",
            `Listing #${report.listing_id} · ${formattedDate(report.created_at)}`
        ));

        heading.append(titleBlock, statusBadge(report.status));
        card.append(heading);

        const details = element("div", "admin-detail-grid");
        details.append(
            makeField("Reason", report.reason),
            makeField("Reporter contact", report.reporter_contact),
            makeField("Details", report.details)
        );
        card.append(details);

        const actions = element("div", "admin-record-actions");
        const viewListing = element(
            "a",
            "button button-secondary",
            "View advertisement"
        );
        viewListing.href = `/?listing=${encodeURIComponent(report.listing_id)}`;
        viewListing.target = "_blank";
        viewListing.rel = "noopener";
        actions.append(viewListing);

        const selector = element("select", "admin-status-select");

        ["open", "reviewed", "resolved", "dismissed"].forEach((value) => {
            const option = element("option", "", value);
            option.value = value;
            option.selected = value === report.status;
            selector.append(option);
        });

        selector.setAttribute("aria-label", `Status for report ${report.id}`);
        actions.append(selector);

        actions.append(button("Update status", "button-primary", async () => {
            try {
                await apiFetch(`/admin/reports/${report.id}/status`, {
                    method: "PATCH",
                    body: JSON.stringify({ status: selector.value })
                });

                showMessage(`Report #${report.id} updated.`);
                await loadReports();
            } catch (error) {
                showMessage(error.message, true);
            }
        }));

        actions.append(button(
            "Delete advertisement",
            "button-danger",
            async () => {
                const confirmed = window.confirm(
                    `Permanently delete "${report.listing_title}" and all ` +
                    "of its reports and images? This cannot be undone."
                );

                if (!confirmed) return;

                try {
                    await apiFetch(
                        `/admin/listings/${encodeURIComponent(report.listing_id)}`,
                        { method: "DELETE" }
                    );

                    showMessage(
                        `Advertisement "${report.listing_title}" and its reports were deleted.`
                    );
                    await Promise.all([
                        loadReports(),
                        loadPendingListings()
                    ]);
                } catch (error) {
                    showMessage(error.message, true);
                }
            }
        ));

        card.append(actions);
        return card;
    }

    async function loadReports() {
        clearContainer(reportsContainer, "Loading reports...");

        try {
            const params = new URLSearchParams({
                page: "1",
                page_size: "100"
            });

            const selectedStatus = $("#report-status-filter")?.value;
            if (selectedStatus) params.set("status", selectedStatus);

            const data = await apiFetch(`/admin/reports/?${params}`);
            const reports = Array.isArray(data) ? data : [];

            if (!reports.length) {
                clearContainer(reportsContainer, "No reports match this filter.");
                return;
            }

            reportsContainer.replaceChildren();

            reports.forEach((report) => {
                reportsContainer.append(createReportCard(report));
            });
        } catch (error) {
            clearContainer(reportsContainer, error.message);
        }
    }





    function setupTabs() {
        const tabs = Array.from(document.querySelectorAll(".admin-tab"));

        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                tabs.forEach((item) => item.classList.remove("active"));
                tab.classList.add("active");

                ["listings", "categories", "reports"].forEach((panelName) => {
                    const panel = $(`#panel-${panelName}`);
                    panel.hidden = panelName !== tab.dataset.panel;
                });
            });
        });
    }

    $("#admin-logout").addEventListener("click", () => {
        sessionStorage.removeItem(tokenKey);
        sessionStorage.removeItem(profileKey);
        window.location.replace("/admin/login");
    });

    $("#refresh-listings").addEventListener("click", loadPendingListings);
    $("#refresh-categories").addEventListener("click", loadCategories);
    $("#refresh-reports").addEventListener("click", loadReports);
    $("#report-status-filter").addEventListener("change", loadReports);

    setupTabs();

    try {
        const admin = await apiFetch("/auth/me");
        $("#admin-identity").textContent =
            `Signed in as ${admin.username || admin.email || "Administrator"}`;
    } catch (error) {
        if (sessionStorage.getItem(tokenKey)) {
            showMessage(error.message, true);
        }
        return;
    }

    await Promise.all([
        loadPendingListings(),
        loadCategories(),
        loadReports()
    ]);
});
