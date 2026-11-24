
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#reset-request-form");
    const emailInput = document.querySelector("#reset-email");
    const message = document.querySelector("#reset-request-message");
    const button = document.querySelector("#reset-request-button");
    function showMessage(text, isError = false) {
        message.textContent = text;
        message.className = isError
            ? "message message-error"
            : "message";
        message.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!form.reportValidity()) {
            return;
        }

        button.disabled = true;
        button.textContent = "Sending...";

        try {
            const response = await fetch("/auth/reset_password", {
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
                throw new Error(
                    "Too many requests. Please wait before trying again."
                );
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "Unable to process your request. Please try again."
                );
            }

            // The response is deliberately generic to avoid revealing
            // whether the email belongs to an administrator.
            showMessage(
                data.message ||
                "If an active administrator account matches that email, " +
                "password-reset instructions will be sent."
            );

            form.reset();
        } catch (error) {
            showMessage(
                error instanceof TypeError
                    ? "Unable to connect to the server. Please try again."
                    : error.message || "Unable to process your request.",
                true
            );
        } finally {
            button.disabled = false;
            button.textContent = "Send reset instructions";
        }
    });
});
