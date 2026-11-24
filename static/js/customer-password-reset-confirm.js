
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#customer-reset-confirm-form");
    const passwordInput = document.querySelector("#customer-new-password");
    const confirmInput = document.querySelector("#customer-confirm-new-password");
    const message = document.querySelector("#customer-reset-confirm-message");
    const button = document.querySelector("#customer-reset-confirm-button");
    // Read the token, then remove it from the visible URL and browser history.
    const currentUrl = new URL(window.location.href);
    const token = currentUrl.searchParams.get("token");
    currentUrl.searchParams.delete("token");
    window.history.replaceState({}, document.title, currentUrl.pathname);

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.className = isError ? "message message-error" : "message";
        message.hidden = false;
    }

    if (!token || token.length < 32 || token.length > 200) {
        form.hidden = true;
        showMessage(
            "This reset link is missing or invalid. Please request a new one.",
            true
        );
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;

        if (passwordInput.value !== confirmInput.value) {
            showMessage("The passwords do not match.", true);
            confirmInput.focus();
            return;
        }

        button.disabled = true;
        button.textContent = "Updating password...";

        try {
            const response = await fetch("/customers/reset_password/confirm", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    token: token,
                    new_password: passwordInput.value
                })
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 429) {
                throw new Error("Too many attempts. Please wait before trying again.");
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
                "Password reset successfully. You can now sign in with your new password."
            );

            const loginLink = document.createElement("a");
            loginLink.href = "/customer/login";
            loginLink.className = "button button-primary button-full";
            loginLink.style.marginTop = "16px";
            loginLink.textContent = "Go to customer login";
            message.insertAdjacentElement("afterend", loginLink);
        } catch (error) {
            showMessage(error.message || "Password reset failed.", true);
        } finally {
            button.disabled = false;
            button.textContent = "Reset password";
        }
    });
});
