
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const $ = (selector) => document.querySelector(selector);

    const searchForm = $("#search-form");
    const listingGrid = $("#listing-grid");
    const resultsCount = $("#results-count");
    const emptyState = $("#empty-state");
    const listingError = $("#listing-error");

    const categoryFilter = $("#category-filter");
    const categoryChips = $("#category-chips");
    const adCategory = $("#ad-category");

    const createListingForm = $("#create-listing-form");
    const createListingMessage = $("#create-listing-message");
    const submitListingButton = $("#submit-listing-button");

    const adType = $("#ad-type");
    const priceField = $("#price-field");
    const adPrice = $("#ad-price");
    const imageInput = $("#ad-images");
    const selectedImages = $("#selected-images");

    const dialog = $("#listing-dialog");
    const dialogContent = $("#dialog-content");
    const closeDialog = $("#close-dialog");
    const reportSection = $("#report-section");
    const reportForm = $("#report-form");
    const reportMessage = $("#report-message");

    let activeCategories = [];
    let currentListingId = null;
    let previewUrls = [];
    let isAuthenticatedCustomer = false;

    function showMessage(element, message, isError = false) {
        element.textContent = message;
        element.className = isError
            ? "message message-error"
            : "message";
        element.hidden = false;
    }

    function hideMessage(element) {
        element.hidden = true;
        element.textContent = "";
    }

    function errorMessage(data, fallback) {
        if (typeof data?.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data?.detail)) {
            return data.detail
                .map((item) => item.msg || "Invalid input")
                .join("; ");
        }

        return fallback;
    }

    async function apiFetch(url, options = {}) {
        const response = await fetch(url, options);
        const contentType = response.headers.get("content-type") || "";

        let data = null;

        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            data = await response.text();
        }

        if (!response.ok) {
            const message = typeof data === "string"
                ? data
                : errorMessage(data, `Request failed (${response.status})`);

            const error = new Error(message);
            error.status = response.status;
            throw error;
        }

        return data;
    }

    function makeElement(tag, className, text) {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        if (text !== undefined && text !== null) {
            element.textContent = String(text);
        }

        return element;
    }

    function formatPrice(price) {
        if (price === null || price === undefined || price === "") {
            return "Free";
        }

        const number = Number(price);

        if (!Number.isFinite(number)) {
            return "Price on request";
        }

        return new Intl.NumberFormat("en-PK", {
            style: "currency",
            currency: "PKR",
            maximumFractionDigits: 0
        }).format(number);
    }

    function categoryName(categoryId) {
        const category = activeCategories.find(
            (item) => Number(item.id) === Number(categoryId)
        );

        return category ? category.name : "Other";
    }

    function releasePreviews() {
        previewUrls.forEach((url) => URL.revokeObjectURL(url));
        previewUrls = [];
        selectedImages.replaceChildren();
    }

    function imageUrl(path) {
        if (!path) {
            return null;
        }

        try {
            const url = new URL(path, window.location.origin);

            // Images must be served by this application.
            if (url.origin !== window.location.origin) {
                return null;
            }

            return url.href;
        } catch {
            return null;
        }
    }

    function createPlaceholder() {
        return makeElement(
            "div",
            "listing-image-placeholder",
            "◇"
        );
    }

    function createListingCard(listing) {
        const card = makeElement("article", "listing-card");
        const imageWrap = makeElement("div", "listing-image-wrap");

        const firstImage = Array.isArray(listing.images)
            ? listing.images[0]
            : null;

        const pictureUrl = imageUrl(firstImage?.image_url);

        if (pictureUrl) {
            const image = makeElement("img", "listing-image");
            image.src = pictureUrl;
            image.alt = listing.title || "Advertisement image";
            image.loading = "lazy";

            image.addEventListener("error", () => {
                image.replaceWith(createPlaceholder());
            }, { once: true });

            imageWrap.append(image);
        } else {
            imageWrap.append(createPlaceholder());
        }

        const isFree = listing.listing_type === "free";

        const badge = makeElement(
            "span",
            isFree ? "listing-badge listing-badge-free" : "listing-badge",
            isFree ? "FREE" : "FOR SALE"
        );

        imageWrap.append(badge);

        const body = makeElement("div", "listing-card-body");
        body.append(
            makeElement(
                "span",
                "listing-category",
                categoryName(listing.category_id)
            )
        );

        body.append(
            makeElement("h3", "listing-title", listing.title || "Untitled")
        );

        body.append(
            makeElement(
                "div",
                "listing-price",
                isFree ? "Free giveaway" : formatPrice(listing.price)
            )
        );

        body.append(
            makeElement(
                "div",
                "listing-location",
                [listing.location_details, listing.city]
                    .filter(Boolean)
                    .join(", ")
            )
        );

        const openButton = makeElement(
            "button",
            "button button-secondary listing-open",
            "View advertisement"
        );

        openButton.type = "button";
        openButton.addEventListener("click", () => {
            openListing(listing.id);
        });

        body.append(openButton);
        card.append(imageWrap, body);

        return card;
    }

    async function loadListings() {
        listingGrid.replaceChildren();
        emptyState.hidden = true;
        listingError.hidden = true;
        listingGrid.hidden = false;
        resultsCount.textContent = "Loading advertisements...";

        const params = new URLSearchParams();
        const keyword = $("#keyword").value.trim();
        const city = $("#city").value.trim();
        const selectedCategory = categoryFilter.value;
        const listingType = $("#type-filter").value;

        if (keyword) {
            params.set("keyword", keyword);
        }

        if (city) {
            params.set("city", city);
        }

        if (selectedCategory) {
            params.set("category_id", selectedCategory);
        }

        if (listingType) {
            params.set("listing_type", listingType);
        }

        params.set("page", "1");
        params.set("page_size", "12");

        try {
            const query = params.toString();
            const data = await apiFetch(
                `/listings/${query ? `?${query}` : ""}`
            );

            // The current API returns an array. The fallback supports
            // a future paginated response with an items array.
            const listings = Array.isArray(data)
                ? data
                : Array.isArray(data?.items)
                    ? data.items
                    : [];

            resultsCount.textContent =
                `${listings.length} advertisement${listings.length === 1 ? "" : "s"}`;

            if (listings.length === 0) {
                listingGrid.hidden = true;
                emptyState.hidden = false;
                return;
            }

            const fragment = document.createDocumentFragment();

            listings.forEach((listing) => {
                fragment.append(createListingCard(listing));
            });

            listingGrid.append(fragment);
        } catch (error) {
            listingGrid.hidden = true;
            resultsCount.textContent = "Unable to load advertisements";

            showMessage(
                listingError,
                error.message || "Could not load the marketplace.",
                true
            );
        }
    }

    function populateCategorySelect(select, placeholder) {
        select.replaceChildren();

        const first = makeElement("option", "", placeholder);
        first.value = "";
        select.append(first);

        activeCategories.forEach((category) => {
            const option = makeElement(
                "option",
                "",
                category.name
            );

            option.value = String(category.id);
            select.append(option);
        });
    }

    async function loadCategories() {
        try {
            const data = await apiFetch("/listings/categories/active");

            activeCategories = Array.isArray(data) ? data : [];

            populateCategorySelect(
                categoryFilter,
                "All categories"
            );

            populateCategorySelect(
                adCategory,
                "Choose a category"
            );

            categoryChips.replaceChildren();

            const allButton = makeElement(
                "button",
                "category-chip active",
                "All categories"
            );

            allButton.type = "button";
            allButton.addEventListener("click", () => {
                categoryFilter.value = "";
                categoryChips.querySelectorAll(".category-chip")
                    .forEach((chip) => chip.classList.remove("active"));

                allButton.classList.add("active");
                loadListings();
            });

            categoryChips.append(allButton);

            activeCategories.forEach((category) => {
                const button = makeElement(
                    "button",
                    "category-chip",
                    category.name
                );

                button.type = "button";

                button.addEventListener("click", () => {
                    categoryFilter.value = String(category.id);

                    categoryChips.querySelectorAll(".category-chip")
                        .forEach((chip) => chip.classList.remove("active"));

                    button.classList.add("active");
                    loadListings();
                });

                categoryChips.append(button);
            });
        } catch (error) {
            console.error("Category loading failed:", error);

            showMessage(
                listingError,
                "Categories could not be loaded. Check the API and try refreshing.",
                true
            );
        }
    }

    function updatePriceField() {
        const isFree = adType.value === "free";

        priceField.hidden = isFree;
        adPrice.disabled = isFree;
        adPrice.required = !isFree;

        if (isFree) {
            adPrice.value = "";
        }
    }

    function clearFormPreviews() {
        releasePreviews();
    }

    function showImagePreviews() {
        releasePreviews();

        const files = Array.from(imageInput.files || []);

        if (files.length > 3) {
            showMessage(
                createListingMessage,
                "Choose no more than 3 images.",
                true
            );
            imageInput.value = "";
            return;
        }

        for (const file of files) {
            if (!file.type.startsWith("image/")) {
                showMessage(
                    createListingMessage,
                    "Please select valid image files.",
                    true
                );
                imageInput.value = "";
                releasePreviews();
                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                showMessage(
                    createListingMessage,
                    "Each image must be 5 MB or smaller.",
                    true
                );
                imageInput.value = "";
                releasePreviews();
                return;
            }

            if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
                showMessage(
                    createListingMessage,
                    "Only JPEG, PNG, and WebP images are supported.",
                    true
                );
                imageInput.value = "";
                releasePreviews();
                return;
            }
        }

        for (const file of files) {
            const url = URL.createObjectURL(file);
            previewUrls.push(url);

            const wrapper = makeElement("div", "selected-image-item");
            const image = makeElement("img");

            image.src = url;
            image.alt = file.name;

            wrapper.append(image);
            selectedImages.append(wrapper);
        }

        hideMessage(createListingMessage);
    }


    async function updateCustomerNavigation() {
        const authArea = document.querySelector("#customer-auth-area");
        const postAdLink = document.querySelector(".nav-post-button");
        const postAdSection = document.querySelector("#post-ad");

        // Never show advertisement posting until the customer is verified.
        isAuthenticatedCustomer = false;

        if (postAdLink) postAdLink.hidden = true;
        if (postAdSection) postAdSection.hidden = true;

        if (!authArea) return;

        const token = sessionStorage.getItem("abbikayga_customer_token");

        // Keep Sign in and Create account visible when logged out.
        if (!token) return;

        try {
            const response = await fetch("/customers/me", {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Accept": "application/json"
                },
                cache: "no-store"
            });

            if (response.status === 401) {
                sessionStorage.removeItem("abbikayga_customer_token");
                sessionStorage.removeItem("abbikayga_customer_profile");
                return;
            }

            if (!response.ok) {
                console.error(
                    "Customer session verification failed:",
                    response.status
                );
                return;
            }

            const customer = await response.json();

            // Reveal posting only after the API validates the customer.
            isAuthenticatedCustomer = true;

            if (postAdLink) postAdLink.hidden = false;
            if (postAdSection) postAdSection.hidden = false;

            authArea.replaceChildren();

            const greeting = document.createElement("span");
            greeting.className = "customer-nav-name";
            greeting.textContent = `Hi, ${customer.name}`;

            const logoutButton = document.createElement("button");
            logoutButton.type = "button";
            logoutButton.className =
                "customer-nav-button customer-logout-button";
            logoutButton.textContent = "Log out";

            logoutButton.addEventListener("click", () => {
                sessionStorage.removeItem("abbikayga_customer_token");
                sessionStorage.removeItem("abbikayga_customer_profile");

                isAuthenticatedCustomer = false;

                window.location.replace("/customer/login");
            }); const myAdsLink = document.createElement("a");
            myAdsLink.href = "/customer/my-listings";
            myAdsLink.className = "customer-nav-link";
            myAdsLink.textContent = "My Ads";

            const profileLink = document.createElement("a");
            profileLink.href = "/customer/profile";
            profileLink.className = "customer-nav-link";
            profileLink.textContent = "My Profile";

            authArea.append(greeting, myAdsLink, profileLink, logoutButton);

        } catch (error) {
            isAuthenticatedCustomer = false;

            console.error(
                "Unable to verify customer session:",
                error.message
            );
        }
    }

    async function openListing(listingId) {
        currentListingId = Number(listingId);

        dialogContent.replaceChildren();
        reportSection.hidden = true;
        reportForm.reset();
        hideMessage(reportMessage);

        dialogContent.append(
            makeElement("p", "", "Loading advertisement details...")
        );

        if (!dialog.open) {
            dialog.showModal();
        }

        document.body.classList.add("dialog-open");

        try {
            const listing = await apiFetch(
                `/listings/${encodeURIComponent(currentListingId)}`
            );

            renderListingDetails(listing);
        } catch (error) {
            dialogContent.replaceChildren(
                makeElement(
                    "p",
                    "message message-error",
                    error.message || "Could not load this advertisement."
                )
            );
        }
    }

    function renderListingDetails(listing) {
        dialogContent.replaceChildren();

        const images = makeElement("div", "detail-gallery");

        (Array.isArray(listing.images) ? listing.images : [])
            .slice(0, 3)
            .forEach((item, index) => {
                const url = imageUrl(item.image_url);

                if (!url) {
                    return;
                }

                const image = makeElement("img");
                image.src = url;
                image.alt = `${listing.title || "Advertisement"} photo ${index + 1}`;
                image.loading = "lazy";

                image.addEventListener("error", () => {
                    image.remove();
                }, { once: true });

                images.append(image);
            });

        if (images.childElementCount > 0) {
            dialogContent.append(images);
        }

        dialogContent.append(
            makeElement(
                "span",
                "listing-category",
                categoryName(listing.category_id)
            )
        );

        dialogContent.append(
            makeElement("h2", "", listing.title || "Advertisement")
        );

        dialogContent.append(
            makeElement(
                "div",
                "detail-price",
                listing.listing_type === "free"
                    ? "Free giveaway"
                    : formatPrice(listing.price)
            )
        );

        dialogContent.append(
            makeElement("p", "", listing.description || "")
        );

        const meta = makeElement("div", "detail-meta");

        const details = [
            ["City", listing.city],
            ["Area", listing.location_details],
            ["Condition", listing.condition],
            ["Seller", listing.seller_name]
        ];

        details.forEach(([label, value]) => {
            const item = makeElement("div");
            item.append(makeElement("strong", "", label));
            item.append(makeElement("span", "", value || "Not provided"));
            meta.append(item);
        });

        dialogContent.append(meta);

        const actions = makeElement("div", "detail-actions");

        if (listing.seller_phone) {
            const phone = String(listing.seller_phone);
            const safePhone = phone.replace(/[^\d+]/g, "");

            const callLink = makeElement(
                "a",
                "button button-primary",
                `Contact seller: ${phone}`
            );

            callLink.href = `tel:${safePhone}`;
            actions.append(callLink);
        }

        let reportButton;

        if (isAuthenticatedCustomer) {
            reportButton = makeElement(
                "button",
                "button button-secondary",
                "Report advertisement"
            );
            reportButton.type = "button";
            reportButton.addEventListener("click", () => {
                reportSection.hidden = false;
                reportSection.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            });
        } else {
            reportButton = makeElement(
                "a",
                "button button-secondary",
                "Sign in to report"
            );
            const next = `/?listing=${encodeURIComponent(listing.id)}`;
            reportButton.href = `/customer/login?${new URLSearchParams({
                next
            })}`;
        }

        actions.append(reportButton);
        dialogContent.append(actions);
    }

    searchForm.addEventListener("submit", (event) => {
        event.preventDefault();

        categoryChips.querySelectorAll(".category-chip")
            .forEach((chip) => chip.classList.remove("active"));

        const selected = categoryFilter.value;

        const chips = Array.from(
            categoryChips.querySelectorAll(".category-chip")
        );

        const matching = chips.find(
            (chip) => activeCategories.some(
                (category) =>
                    category.name === chip.textContent &&
                    String(category.id) === selected
            )
        );

        if (matching) {
            matching.classList.add("active");
        } else if (chips[0]) {
            chips[0].classList.add("active");
        }

        loadListings();
    });

    searchForm.addEventListener("reset", () => {
        window.setTimeout(() => {
            categoryChips.querySelectorAll(".category-chip")
                .forEach((chip) => chip.classList.remove("active"));

            if (categoryChips.firstElementChild) {
                categoryChips.firstElementChild.classList.add("active");
            }

            loadListings();
        }, 0);
    });

    $("#empty-reset").addEventListener("click", () => {
        searchForm.reset();
    });

    createListingForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        hideMessage(createListingMessage);

        const customerToken = sessionStorage.getItem(
            "abbikayga_customer_token"
        );

        if (!isAuthenticatedCustomer || !customerToken) {
            window.location.assign("/customer/login");
            return;
        }

        if (!createListingForm.reportValidity()) {
            return;
        }

        const files = Array.from(imageInput.files || []);

        if (files.length > 3) {
            showMessage(
                createListingMessage,
                "A listing can have at most 3 images.",
                true
            );
            return;
        }

        if (activeCategories.length === 0) {
            showMessage(
                createListingMessage,
                "There are no active categories available. Please try again later.",
                true
            );
            return;
        }

        submitListingButton.disabled = true;
        submitListingButton.textContent = "Submitting...";

        try {
            const formData = new FormData(createListingForm);

            if (adType.value === "free") {
                formData.delete("price");
            }

            const createdListing = await apiFetch(
                "/listings/with-images",
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${customerToken}`
                    },
                    body: formData
                }
            );

            createListingForm.reset();
            updatePriceField();
            clearFormPreviews();

            showMessage(
                createListingMessage,
                `Advertisement submitted successfully (ID ${createdListing.id}). It will appear publicly after administrator approval.`
            );

            createListingMessage.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        } catch (error) {
            showMessage(
                createListingMessage,
                error.status === 429
                    ? "Too many submissions. Please try again later."
                    : error.message || "The advertisement could not be submitted.",
                true
            );
        } finally {
            submitListingButton.disabled = false;
            submitListingButton.textContent = "Submit advertisement";
        }
    });

    reportForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        hideMessage(reportMessage);

        if (!currentListingId) {
            showMessage(
                reportMessage,
                "Please open an advertisement first.",
                true
            );
            return;
        }

        if (!reportForm.reportValidity()) {
            return;
        }

        const submitButton = reportForm.querySelector(
            'button[type="submit"]'
        );

        submitButton.disabled = true;
        submitButton.textContent = "Submitting...";

        try {
            const customerToken = sessionStorage.getItem(
                "abbikayga_customer_token"
            );

            if (!customerToken) {
                window.location.assign("/customer/login");
                return;
            }

            const body = {
                reason: $("#report-reason").value,
                details: $("#report-details").value.trim(),
                reporter_contact: $("#report-contact").value.trim() || null
            };

            const result = await apiFetch(
                `/listings/${encodeURIComponent(currentListingId)}/reports`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${customerToken}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(body)
                }
            );

            reportForm.reset();

            showMessage(
                reportMessage,
                `Report submitted successfully. Reference number: ${result.id}.`
            );
        } catch (error) {
            showMessage(
                reportMessage,
                error.status === 429
                    ? "Too many reports have been submitted. Please try again later."
                    : error.message || "Your report could not be submitted.",
                true
            );
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Submit report";
        }
    });

    adType.addEventListener("change", updatePriceField);
    imageInput.addEventListener("change", showImagePreviews);

    closeDialog.addEventListener("click", () => dialog.close());

    dialog.addEventListener("close", () => {
        document.body.classList.remove("dialog-open");
        reportSection.hidden = true;
        currentListingId = null;
    });

    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });



    const postAdLink = document.querySelector(".nav-post-button");

    if (postAdLink) {
        postAdLink.addEventListener("click", (event) => {
            event.preventDefault();

            if (!isAuthenticatedCustomer) {
                window.location.assign("/customer/login");
                return;
            }

            const section = document.getElementById("post-ad");

            if (!section) {
                console.error("Post Ad section was not found.");
                return;
            }

            section.hidden = false;

            history.replaceState(null, "", "#post-ad");

            section.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        });
    }


    if (postAdLink) {
        postAdLink.addEventListener("click", (event) => {
            event.preventDefault();

            const section = document.getElementById("post-ad");

            if (!section) {
                console.error("Post Ad section is missing.");
                return;
            }

            section.hidden = false;
            section.scrollIntoView({
                behavior: "auto",
                block: "start"
            });

            window.location.hash = "post-ad";
        });
    }


    updatePriceField();

    Promise.all([
        updateCustomerNavigation(),
        loadCategories()
    ]).then(async () => {
        await loadListings();
        const params = new URLSearchParams(window.location.search);
        const listingId = params.get("listing");

        if (listingId && /^\d+$/.test(listingId)) {
            await openListing(Number(listingId));

            // Remove the query parameter after opening the modal.
            history.replaceState(null, "", window.location.pathname);
        }
    });



});
