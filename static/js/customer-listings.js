"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const tokenKey = "abbikayga_customer_token";
    const profileKey = "abbikayga_customer_profile";

    const grid = document.querySelector("#customer-listings-grid");
    const count = document.querySelector("#customer-listings-count");
    const message = document.querySelector("#customer-listings-message");
    const empty = document.querySelector("#customer-listings-empty");
    const statusFilter = document.querySelector("#customer-listings-status");
    const refreshButton = document.querySelector("#customer-listings-refresh");

    let allListings = [];

    function makeElement(tag, className = "", text = "") {
        const node = document.createElement(tag);

        if (className) {
            node.className = className;
        }

        if (text !== undefined && text !== null) {
            node.textContent = String(text);
        }

        return node;
    }

    function showError(text) {
        message.textContent = text;
        message.hidden = false;
    }

    function hideError() {
        message.hidden = true;
        message.textContent = "";
    }

    async function loadMyListings() {
        const token = sessionStorage.getItem(tokenKey);

        if (!token) {
            window.location.replace("/customer/login");
            return;
        }

        refreshButton.disabled = true;
        refreshButton.textContent = "Loading...";
        hideError();
        empty.hidden = true;
        grid.replaceChildren();
        count.textContent = "Loading your advertisements...";

        try {
            const response = await fetch("/customers/me/listings", {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Accept": "application/json"
                },
                cache: "no-store"
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 401) {
                sessionStorage.removeItem(tokenKey);
                sessionStorage.removeItem(profileKey);
                window.location.replace("/customer/login");
                return;
            }

            if (response.status === 429) {
                throw new Error("Too many requests. Please wait before refreshing.");
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : `Could not load advertisements (HTTP ${response.status}).`
                );
            }

            if (!Array.isArray(data)) {
                throw new Error("Unexpected response from the advertisements API.");
            }

            allListings = data;
            renderListings();

        } catch (error) {
            count.textContent = "Unable to load advertisements.";
            showError(error.message || "An unexpected error occurred.");
        } finally {
            refreshButton.disabled = false;
            refreshButton.textContent = "Refresh";
        }
    }

    function formatPrice(listing) {
        if (listing.listing_type === "free") {
            return "Free giveaway";
        }

        const price = Number(listing.price);

        if (!Number.isFinite(price)) {
            return "Price not set";
        }

        return new Intl.NumberFormat("en-PK", {
            style: "currency",
            currency: "PKR",
            maximumFractionDigits: 0
        }).format(price);
    }

    function formatDate(value) {
        if (!value) return "Date unavailable";

        const date = new Date(value);

        return Number.isNaN(date.getTime())
            ? "Date unavailable"
            : date.toLocaleDateString();
    }

    function createListingCard(listing) {
        const card = makeElement("article", "customer-listing-card");

        const heading = makeElement("div", "customer-listing-card-heading");

        heading.append(
            makeElement("span", "customer-listing-id", `Ad #${listing.id}`)
        );

        const status = makeElement(
            "span",
            `customer-listing-status status-${listing.status}`,
            listing.status
        );

        heading.append(status);
        card.append(heading);

        card.append(
            makeElement("h2", "customer-listing-title", listing.title)
        );

        card.append(
            makeElement("p", "customer-listing-price", formatPrice(listing))
        );

        card.append(
            makeElement(
                "p",
                "customer-listing-location",
                [listing.location_details, listing.city]
                    .filter(Boolean)
                    .join(", ")
            )
        );

        card.append(
            makeElement(
                "p",
                "customer-listing-date",
                `Submitted: ${formatDate(listing.created_at)}`
            )
        );

        if (listing.status === "rejected" && listing.rejection_reason) {
            const rejection = makeElement("div", "customer-rejection-reason");

            rejection.append(
                makeElement("strong", "", "Reason for rejection")
            );

            rejection.append(
                makeElement("p", "", listing.rejection_reason)
            );

            card.append(rejection);
        }

        const actions = makeElement("div", "customer-listing-actions");

        // Only approved advertisements have a public detail page.
        if (listing.status === "approved") {
            const viewLink = makeElement(
                "a",
                "button button-primary",
                "View advertisement"
            );

            viewLink.href = `/?listing=${encodeURIComponent(listing.id)}`;
            actions.append(viewLink);
        }

        // Hide the delete button once the listing has been removed.
        if (listing.status !== "removed") {
            const deleteButton = makeElement(
                "button",
                "button button-danger",
                "Delete post"
            );

            deleteButton.type = "button";

            deleteButton.addEventListener("click", async () => {
                const confirmed = window.confirm(
                    `Remove "${listing.title}" from the marketplace?`
                );

                if (!confirmed) return;

                const token = sessionStorage.getItem(
                    "abbikayga_customer_token"
                );

                if (!token) {
                    window.location.replace("/customer/login");
                    return;
                }

                deleteButton.disabled = true;
                deleteButton.textContent = "Removing...";

                try {
                    const response = await fetch(
                        `/customers/me/listings/${encodeURIComponent(listing.id)}`,
                        {
                            method: "DELETE",
                            headers: {
                                "Authorization": `Bearer ${token}`,
                                "Accept": "application/json"
                            },
                            cache: "no-store"
                        }
                    );

                    const data = await response.json().catch(() => ({}));

                    if (response.status === 401) {
                        sessionStorage.removeItem("abbikayga_customer_token");
                        sessionStorage.removeItem("abbikayga_customer_profile");
                        window.location.replace("/customer/login");
                        return;
                    }

                    if (!response.ok) {
                        throw new Error(
                            typeof data.detail === "string"
                                ? data.detail
                                : "Could not remove this advertisement."
                        );
                    }

                    await loadMyListings();

                    message.className = "message";
                    message.textContent =
                        data.message || "Advertisement removed successfully.";
                    message.hidden = false;

                } catch (error) {
                    showError(error.message || "Could not remove this advertisement.");
                    deleteButton.disabled = false;
                    deleteButton.textContent = "Delete post";
                }
            });

            actions.append(deleteButton);
        }

        card.append(actions);

        return card;
    }

    function renderListings() {
        const selectedStatus = statusFilter.value;

        const filtered = allListings.filter((listing) => {
            if (selectedStatus) {
                return listing.status === selectedStatus;
            }

            // Hide removed advertisements from the default view.
            return listing.status !== "removed";
        });

        grid.replaceChildren();

        count.textContent =
            `${filtered.length} advertisement${filtered.length === 1 ? "" : "s"}`;

        if (filtered.length === 0) {
            empty.hidden = false;
            return;
        }

        empty.hidden = true;

        const fragment = document.createDocumentFragment();

        filtered.forEach((listing) => {
            fragment.append(createListingCard(listing));
        });

        grid.append(fragment);
    }

    refreshButton.addEventListener("click", loadMyListings);
    statusFilter.addEventListener("change", renderListings);

    document.querySelector("#customer-listings-logout")
        .addEventListener("click", () => {
            sessionStorage.removeItem(tokenKey);
            sessionStorage.removeItem(profileKey);
            window.location.replace("/customer/login");
        });

    loadMyListings();
});