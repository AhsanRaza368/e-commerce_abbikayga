
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#customer-reset-request-form");
    const emailInput = document.querySelector("#customer-reset-email");
    const message = document.querySelector("#customer-reset-request-message");
    const button = document.querySelector("#customer-reset-request-button");
    function showMessage(text, isError = false) {
        message.textContent = text;
        message.className = isError ? "message message-error" : "message";
        message.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;

        button.disabled = true;
        button.textContent = "Sending...";

        try {
            const response = await fetch("/customers/reset_password", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    email: emailInput.value.trim().toLowerCase()
                })
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 429) {
                throw new Error("Too many requests. Please wait before trying again.");
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "Unable to process the request. Please try again."
                );
            }

            showMessage(
                data.message ||
                "If an active customer account matches that email, password-reset instructions will be sent."
            );

            form.reset();
        } catch (error) {
            showMessage(
                error.message || "Unable to process the request.",
                true
            );
        } finally {
            button.disabled = false;
            button.textContent = "Send reset instructions";
        }
    });
});
