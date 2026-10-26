// One request, one result. Never automatically retry account or session writes.
const messages = {
  invalid_credentials: "invalidCredentials",
  email_registered: "emailRegistered",
  invalid_input: "invalidInput",
  origin_rejected: "originMismatch",
  service_unavailable: "serviceUnavailable",
  invalid_reset_code: "resetInvalid",
  rate_limited: "tooManyRequests",
  verify_email_required: "verificationNeeded",
  delivery_not_configured: "providerUnavailable",
  email_not_configured: "emailUnavailable",
  alert_cooldown: "cooldown",
  invalid_invitation: "inviteInvalid",
  admin_required: "adminOnly",
  language_unavailable: "planned",
  sign_in_required: "authNeeded",
  consent_required: "consentCheck",
  not_found: "notFound",
  session_not_found: "notFound",
};

export class ApiError extends Error {
  constructor(message, { code = "", status = 0 } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export function createApiClient({
  fetchImpl = (...args) => globalThis.fetch(...args),
  isOnline = () => globalThis.navigator?.onLine !== false,
  onConnection = () => {},
  timeoutMs = 12000,
} = {}) {
  return async function request(path, method = "GET", body, { validate } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(path, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          "X-Catchy-Request": "1",
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let result;
      try {
        result = await response.json();
      } catch {
        // Body reads can time out too; keep that distinct from invalid JSON.
        if (controller.signal.aborted) throw new ApiError("requestTimeout");
        throw new ApiError(
          response.status >= 500 ? "serviceUnavailable" : "unexpectedResponse",
          { status: response.status },
        );
      }
      if (!result || typeof result !== "object" || Array.isArray(result))
        throw new ApiError("unexpectedResponse", { status: response.status });
      if (!response.ok) {
        const code = typeof result.error === "string" ? result.error : "";
        const fallback =
          response.status >= 500
            ? "serviceUnavailable"
            : response.status === 429
              ? "tooManyRequests"
              : "unexpectedResponse";
        throw new ApiError(messages[code] || (code ? "error" : fallback), {
          code,
          status: response.status,
        });
      }
      if (validate && !validate(result))
        throw new ApiError("unexpectedResponse", { status: response.status });
      onConnection("connected");
      return result;
    } catch (cause) {
      const error =
        cause instanceof ApiError
          ? cause
          : new ApiError(
              !isOnline()
                ? "offline"
                : controller.signal.aborted
                  ? "requestTimeout"
                  : "connectionLost",
            );
      if (
        !error.status ||
        error.status >= 500 ||
        error.message === "unexpectedResponse"
      ) {
        onConnection("disconnected", error.message);
      } else {
        // An authentication/validation rejection still proves the API is reachable.
        onConnection("connected");
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  };
}
