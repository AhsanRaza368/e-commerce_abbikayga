"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const signupForm = document.querySelector("#customer-signup-form");
    const verifyForm = document.querySelector("#customer-verify-form");
    const loginForm = document.querySelector("#customer-login-form");

    const CUSTOMER_TOKEN_KEY = "abbikayga_customer_token";
    const CUSTOMER_PROFILE_KEY = "abbikayga_customer_profile";

    function showMessage(element, text, isError = false) {
        element.textContent = text;
        element.className = isError
            ? "message message-error"
            : "message";
        element.hidden = false;
    }

    function hideMessage(element) {
        element.textContent = "";
        element.hidden = true;
    }

    function getErrorMessage(data, fallback) {
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

    async function postJson(url, payload) {
        let response;

        try {
            response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(payload)
            });
        } catch {
            throw new Error(
                "Cannot connect to AbbiKayGa. Check that the server is running."
            );
        }

        const data = await response.json().catch(() => ({}));

        if (response.status === 429) {
            throw new Error(
                "Too many requests. Please wait before trying again."
            );
        }

        if (!response.ok) {
            throw new Error(
                getErrorMessage(
                    data,
                    `Request failed (${response.status}).`
                )
            );
        }

        return data;
    }

    // Customer signup
    if (signupForm) {
        const nameInput = document.querySelector("#customer-name");
        const emailInput = document.querySelector("#customer-signup-email");
        const passwordInput = document.querySelector(
            "#customer-signup-password"
        );
        const confirmInput = document.querySelector(
            "#customer-confirm-password"
        );
        const message = document.querySelector("#signup-message");
        const submitButton = document.querySelector(
            "#customer-signup-button"
        );

        signupForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            hideMessage(message);

            if (!signupForm.reportValidity()) {
                return;
            }

            if (passwordInput.value !== confirmInput.value) {
                showMessage(message, "The passwords do not match.", true);
                confirmInput.focus();
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = "Sending code...";

            try {
                await postJson("/customers/signup", {
                    name: nameInput.value.trim(),
                    email: emailInput.value.trim().toLowerCase(),
                    password: passwordInput.value
                });

                showMessage(
                    message,
                    "Verification code sent. Opening the email verification page..."
                );
                const email = encodeURIComponent(
                    emailInput.value.trim().toLowerCase()
                );
                window.location.assign(
                    `/customer/verify-email?email=${email}`
                );
            } catch (error) {
                showMessage(
                    message,
                    error.message || "Unable to create your account.",
                    true
                );
                passwordInput.focus();
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = "Send verification code";
            }
        });
    }

    // Customer email verification
    if (verifyForm) {
        const emailInput = document.querySelector("#customer-verify-email");
        const codeInput = document.querySelector("#customer-verify-code");
        const message = document.querySelector("#signup-verify-message");
        const verifyButton = document.querySelector(
            "#customer-verify-button"
        );
        const resendButton = document.querySelector(
            "#customer-verify-resend"
        );
        const emailFromUrl = new URLSearchParams(
            window.location.search
        ).get("email");

        if (emailFromUrl) {
            emailInput.value = emailFromUrl;
        }

        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            hideMessage(message);

            if (!verifyForm.reportValidity()) {
                return;
            }

            verifyButton.disabled = true;
            verifyButton.textContent = "Verifying code...";

            try {
                await postJson("/customers/signup/verify", {
                    email: emailInput.value.trim().toLowerCase(),
                    code: codeInput.value.trim()
                });

                window.location.assign("/customer/login?verified=1");
            } catch (error) {
                showMessage(
                    message,
                    error.message || "Unable to verify your email.",
                    true
                );
                codeInput.focus();
            } finally {
                verifyButton.disabled = false;
                verifyButton.textContent = "Verify code and create account";
            }
        });

        resendButton.addEventListener("click", async () => {
            if (!emailInput.reportValidity()) {
                return;
            }

            resendButton.disabled = true;
            resendButton.textContent = "Sending...";
            hideMessage(message);

            try {
                await postJson("/customers/signup/resend-code", {
                    email: emailInput.value.trim().toLowerCase()
                });
                codeInput.value = "";
                showMessage(
                    message,
                    "A new verification code was sent. Any earlier code is no longer valid."
                );
                codeInput.focus();
            } catch (error) {
                showMessage(
                    message,
                    error.message || "Unable to resend the verification code.",
                    true
                );
            } finally {
                resendButton.disabled = false;
                resendButton.textContent = "Send a new code";
            }
        });
    }

    // Customer login
    if (loginForm) {
        const emailInput = document.querySelector("#customer-login-email");
        const passwordInput = document.querySelector(
            "#customer-login-password"
        );
        const message = document.querySelector("#login-message");
        const submitButton = document.querySelector(
            "#customer-login-button"
        );

        if (new URLSearchParams(window.location.search).get("verified") === "1") {
            showMessage(
                document.querySelector("#login-message"),
                "Email verified and account created. You can now sign in."
            );
        }

        loginForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            hideMessage(message);

            if (!loginForm.reportValidity()) {
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = "Signing in...";

            try {
                const data = await postJson("/customers/login", {
                    email: emailInput.value.trim().toLowerCase(),
                    password: passwordInput.value
                });

                if (
                    typeof data.access_token !== "string" ||
                    data.token_type?.toLowerCase() !== "bearer"
                ) {
                    throw new Error(
                        "The server returned an unexpected login response."
                    );
                }

                sessionStorage.setItem(
                    CUSTOMER_TOKEN_KEY,
                    data.access_token
                );

                if (data.customer) {
                    sessionStorage.setItem(
                        CUSTOMER_PROFILE_KEY,
                        JSON.stringify(data.customer)
                    );
                }

                passwordInput.value = "";
                const next = new URLSearchParams(
                    window.location.search
                ).get("next");
                const redirectPath = next
                    && next.startsWith("/")
                    && !next.startsWith("//")
                    ? next
                    : "/";

                window.location.assign(redirectPath);
            } catch (error) {
                showMessage(
                    message,
                    error.message || "Unable to sign in.",
                    true
                );

                passwordInput.value = "";
                passwordInput.focus();
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = "Sign in";
            }
        });
    }
});