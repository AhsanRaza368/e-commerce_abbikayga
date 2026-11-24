
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#reset-confirm-form");
    const passwordInput = document.querySelector("#new-password");
    const confirmInput = document.querySelector("#confirm-password");
    const message = document.querySelector("#reset-confirm-message");
    const submitButton = document.querySelector("#reset-confirm-button");
    // Capture the token, then remove it from the visible browser URL/history.
    const currentUrl = new URL(window.location.href);
    const token = currentUrl.searchParams.get("token");

    currentUrl.searchParams.delete("token");
    window.history.replaceState({}, document.title, currentUrl.pathname);

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.className = isError
            ? "message message-error"
            : "message";
        message.hidden = false;
    }

    if (!token || token.length < 32 || token.length > 200) {
        form.hidden = true;
        showMessage(
            "This password-reset link is missing or invalid. Request a new link.",
            true
        );
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!form.reportValidity()) {
            return;
        }

        if (passwordInput.value !== confirmInput.value) {
            showMessage("The passwords do not match.", true);
            confirmInput.focus();
            return;
        }

        submitButton.disabled = true;
        submitButton.textContent = "Updating password...";

        try {
            const response = await fetch("/auth/reset_password/confirm", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    token,
                    new_password: passwordInput.value
                })
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 429) {
                throw new Error(
                    "Too many attempts. Please wait before trying again."
                );
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "Unable to reset the password. Request a new link."
                );
            }

            form.reset();
            form.hidden = true;

            showMessage(
                "Your password has been reset successfully. You can now sign in."
            );

            const loginLink = document.createElement("a");
            loginLink.href = "/admin/login";
            loginLink.className = "button button-primary button-full";
            loginLink.textContent = "Go to administrator login";
            loginLink.style.marginTop = "16px";
            message.insertAdjacentElement("afterend", loginLink);
        } catch (error) {
            showMessage(
                error instanceof TypeError
                    ? "Cannot connect to the server. Please try again."
                    : error.message || "Password reset failed.",
                true
            );
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Reset password";
        }
    });
});
