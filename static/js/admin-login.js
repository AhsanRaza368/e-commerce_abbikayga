
"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#admin-login-form");
    const emailInput = document.querySelector("#admin-email");
    const passwordInput = document.querySelector("#admin-password");
    const message = document.querySelector("#login-message");
    const loginButton = document.querySelector("#login-button");
    function showError(text) {
        message.textContent = text;
        message.hidden = false;
        message.classList.add("message-error");
    }

    function hideError() {
        message.textContent = "";
        message.hidden = true;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        hideError();

        if (!form.reportValidity()) {
            return;
        }

        const email = emailInput.value.trim().toLowerCase();
        const password = passwordInput.value;

        loginButton.disabled = true;
        loginButton.textContent = "Signing in...";

        try {
            const response = await fetch("/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 429) {
                throw new Error(
                    "Too many login attempts. Please wait before trying again."
                );
            }

            if (response.status === 401) {
                throw new Error("Invalid email or password.");
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "Login failed. Please try again."
                );
            }

            if (
                typeof data.access_token !== "string" ||
                data.token_type?.toLowerCase() !== "bearer"
            ) {
                throw new Error(
                    "The server returned an unexpected login response."
                );
            }

            // Keep the JWT for this browser tab/session only.
            // Do not store passwords or tokens in URLs.
            sessionStorage.setItem(
                "abbikayga_admin_token",
                data.access_token
            );

            if (data.admin) {
                sessionStorage.setItem(
                    "abbikayga_admin_profile",
                    JSON.stringify(data.admin)
                );
            }

            // This page will be created in the next dashboard step.
            window.location.assign("/admin/dashboard");
        } catch (error) {
            showError(
                error instanceof TypeError
                    ? "Cannot reach the server. Check that AbbiKayGa is running."
                    : error.message || "Login failed. Please try again."
            );

            passwordInput.value = "";
            passwordInput.focus();
        } finally {
            loginButton.disabled = false;
            loginButton.textContent = "Sign in securely";
        }
    });
});
