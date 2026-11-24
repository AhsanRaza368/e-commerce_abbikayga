
"use strict";

document.addEventListener("DOMContentLoaded", async () => {
    const tokenKey = "abbikayga_customer_token";
    const profileKey = "abbikayga_customer_profile";

    const form = document.querySelector("#customer-profile-form");
    const nameInput = document.querySelector("#profile-name");
    const emailInput = document.querySelector("#profile-email");
    const phoneInput = document.querySelector("#profile-phone");
    const message = document.querySelector("#profile-message");
    const loading = document.querySelector("#profile-loading");
    const profileCard = document.querySelector(".customer-profile-card");
    const saveButton = document.querySelector("#profile-save-button");
    const displayName = document.querySelector("#profile-display-name");
    const displayEmail = document.querySelector("#profile-display-email");
    const avatar = document.querySelector("#profile-avatar");
    const avatarInitials = document.querySelector(
        "#profile-avatar-initials"
    );
    const avatarImage = document.querySelector("#profile-avatar-image");
    const pictureInput = document.querySelector("#profile-picture-input");
    const pictureUploadButton = document.querySelector(
        "#profile-picture-upload-button"
    );
    const pictureMessage = document.querySelector(
        "#profile-picture-message"
    );

    const token = sessionStorage.getItem(tokenKey);
    let profilePictureObjectUrl = null;
    let previewObjectUrl = null;
    let currentProfilePictureUrl = null;

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.className = isError
            ? "message message-error"
            : "message";
        message.hidden = false;
    }

    function showPictureMessage(text, isError = false) {
        pictureMessage.textContent = text;
        pictureMessage.className = isError
            ? "message message-error"
            : "message";
        pictureMessage.hidden = false;
    }

    function updateProfileSummary(customer) {
        const name = customer.name || "Customer";
        const initials = name
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part.charAt(0))
            .join("")
            .toUpperCase();

        displayName.textContent = name;
        displayEmail.textContent = customer.email || "";
        avatarInitials.textContent = initials || "A";
        avatar.setAttribute("aria-label", `${name}'s profile picture`);
    }

    async function loadProfilePicture(profilePictureUrl) {
        if (!profilePictureUrl) {
            avatarImage.hidden = true;
            avatarInitials.hidden = false;
            return;
        }

        const response = await fetch("/customers/me/profile-picture", {
            headers: {
                "Authorization": `Bearer ${token}`,
                "Accept": "image/webp"
            },
            cache: "no-store"
        });

        if (response.status === 401) {
            redirectToLogin();
            throw new Error("Your session expired. Please sign in again.");
        }

        if (!response.ok) {
            throw new Error("Unable to load your profile picture.");
        }

        const imageBlob = await response.blob();
        const nextObjectUrl = URL.createObjectURL(imageBlob);

        if (profilePictureObjectUrl) {
            URL.revokeObjectURL(profilePictureObjectUrl);
        }

        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = null;
        }

        profilePictureObjectUrl = nextObjectUrl;
        avatarImage.src = profilePictureObjectUrl;
        avatarImage.hidden = false;
        avatarInitials.hidden = true;
    }

    function redirectToLogin() {
        sessionStorage.removeItem(tokenKey);
        sessionStorage.removeItem(profileKey);
        window.location.replace("/customer/login");
    }

    if (!token) {
        redirectToLogin();
        return;
    }

    async function sendRequest(url, options = {}) {
        let response;

        try {
            response = await fetch(url, {
                ...options,
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Accept": "application/json",
                    ...(options.body !== undefined
                        && !(options.body instanceof FormData)
                        ? { "Content-Type": "application/json" }
                        : {}),
                    ...options.headers
                },
                cache: "no-store"
            });
        } catch {
            throw new Error(
                "Unable to connect to the server. Please try again."
            );
        }

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
            redirectToLogin();
            throw new Error("Your session expired. Please sign in again.");
        }

        if (response.status === 429) {
            throw new Error(
                "Too many requests. Please wait before trying again."
            );
        }

        if (!response.ok) {
            if (Array.isArray(data.detail)) {
                throw new Error(
                    data.detail.map((item) => item.msg).join("; ")
                );
            }

            throw new Error(
                typeof data.detail === "string"
                    ? data.detail
                    : `Request failed (${response.status}).`
            );
        }

        return data;
    }

    // Load the customer's current profile.
    try {
        const customer = await sendRequest("/customers/me");
        currentProfilePictureUrl = customer.profile_picture_url;

        nameInput.value = customer.name || "";
        emailInput.value = customer.email || "";
        phoneInput.value = customer.phone || "";
        updateProfileSummary(customer);

        try {
            await loadProfilePicture(customer.profile_picture_url);
        } catch (error) {
            showPictureMessage(error.message, true);
        }

        sessionStorage.setItem(
            profileKey,
            JSON.stringify(customer)
        );

        form.hidden = false;
        loading.hidden = true;
        profileCard.setAttribute("aria-busy", "false");
    } catch (error) {
        loading.hidden = true;
        profileCard.setAttribute("aria-busy", "false");
        showMessage(error.message, true);
        return;
    }

    pictureInput.addEventListener("change", async () => {
        const file = pictureInput.files[0];
        pictureUploadButton.disabled = !file;

        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = null;
        }

        if (!file) {
            try {
                await loadProfilePicture(currentProfilePictureUrl);
            } catch (error) {
                showPictureMessage(error.message, true);
            }
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            showPictureMessage("The image must be 5 MB or smaller.", true);
            pictureInput.value = "";
            pictureUploadButton.disabled = true;
            return;
        }

        previewObjectUrl = URL.createObjectURL(file);
        avatarImage.src = previewObjectUrl;
        avatarImage.hidden = false;
        avatarInitials.hidden = true;
        pictureMessage.hidden = true;
    });

    pictureUploadButton.addEventListener("click", async () => {
        const picture = pictureInput.files[0];

        if (!picture) {
            return;
        }

        const formData = new FormData();
        formData.append("picture", picture);
        pictureUploadButton.disabled = true;
        pictureUploadButton.textContent = "Uploading...";

        try {
            const updatedCustomer = await sendRequest(
                "/customers/me/profile-picture",
                {
                    method: "PUT",
                    body: formData
                }
            );

            currentProfilePictureUrl = updatedCustomer.profile_picture_url;
            sessionStorage.setItem(
                profileKey,
                JSON.stringify(updatedCustomer)
            );
            pictureInput.value = "";
            await loadProfilePicture(currentProfilePictureUrl);
            showPictureMessage("Your profile picture has been updated.");
        } catch (error) {
            showPictureMessage(error.message, true);
        } finally {
            pictureUploadButton.disabled = !pictureInput.files.length;
            pictureUploadButton.textContent = "Upload picture";
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!form.reportValidity()) {
            return;
        }

        saveButton.disabled = true;
        saveButton.textContent = "Saving...";

        try {
            const updatedCustomer = await sendRequest("/customers/me", {
                method: "PATCH",
                body: JSON.stringify({
                    name: nameInput.value.trim(),
                    email: emailInput.value.trim().toLowerCase(),
                    phone: phoneInput.value.trim() || null
                })
            });

            nameInput.value = updatedCustomer.name;
            emailInput.value = updatedCustomer.email;
            phoneInput.value = updatedCustomer.phone || "";
            updateProfileSummary(updatedCustomer);

            sessionStorage.setItem(
                profileKey,
                JSON.stringify(updatedCustomer)
            );

            showMessage("Your profile has been updated successfully.");
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = "Save changes";
        }
    });
});
