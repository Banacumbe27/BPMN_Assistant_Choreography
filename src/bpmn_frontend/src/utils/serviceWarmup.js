import { isHostedVersion } from "../config";

export const REMOTE_SERVICES = [
  {
    id: "assistant",
    label: "BPMN Assistant API",
    url: "https://bpmn-assistant-api.onrender.com",
    path: "/",
  },
  {
    id: "layout",
    label: "BPMN Layout Server",
    url: "https://bpmn-layout-server.onrender.com",
    path: "/",
  },
];

const DEFAULT_TIMEOUT_MS = 90_000;
const REQUEST_TIMEOUT_MS = 12_000;
const RETRY_DELAY_MS = 3_000;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const buildServiceUrl = (service) => {
  const base = service.url.endsWith("/") ? service.url : `${service.url}/`;
  const path = service.path ? service.path.replace(/^\//, "") : "";
  return `${base}${path}`;
};

const initialStatus = (service) => ({
  id: service.id,
  label: service.label,
  url: buildServiceUrl(service),
  attempts: 0,
  hasResponded: false,
  ok: false,
  statusCode: null,
  error: null,
  completed: false,
  timedOut: false,
});

const updateAndNotify = (status, onStatus) => {
  if (onStatus) {
    onStatus({ ...status });
  }
};

const logInfo = (...args) => {
  // eslint-disable-next-line no-console
  console.info("[service-warmup]", ...args);
};

const fetchWithTimeout = async (url, timeoutMs, serviceId) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  logInfo("Requesting service", { serviceId, url, timeoutMs });
  try {
    const response = await fetch(url, {
      method: "GET",
      signal: controller.signal,
    });
    logInfo("Received response", {
      serviceId,
      url,
      status: response.status,
      ok: response.ok,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
};

const pingService = async (service, deadline, onStatus) => {
  const status = initialStatus(service);
  while (Date.now() < deadline && !status.completed) {
    status.attempts += 1;
    const remaining = deadline - Date.now();
    const attemptTimeout = Math.min(REQUEST_TIMEOUT_MS, Math.max(remaining, 0));
    try {
      const response = await fetchWithTimeout(status.url, attemptTimeout, service.id);
      status.hasResponded = true;
      status.statusCode = response.status;
      status.ok = response.ok;
      status.completed = response.ok;
      status.error = response.ok ? null : `Unexpected status: ${response.status}`;
    } catch (error) {
      logInfo("Request failed", {
        serviceId: service.id,
        url: status.url,
        attempts: status.attempts,
        error: error?.message,
      });
      status.error =
        error?.name === "AbortError"
          ? "Request timed out"
          : error?.message || "Request failed";
    }

    updateAndNotify(status, onStatus);

    if (!status.completed && Date.now() < deadline) {
      await sleep(RETRY_DELAY_MS);
    }
  }

  status.timedOut = !status.completed && Date.now() >= deadline;
  if (!status.hasResponded && !status.error) {
    status.error = "No response received";
  }
  updateAndNotify(status, onStatus);

  return status;
};

export const warmupServices = async ({ timeoutMs = DEFAULT_TIMEOUT_MS, onStatus } = {}) => {
  if (!isHostedVersion) {
    const statuses = REMOTE_SERVICES.map((service) => {
      const status = initialStatus(service);
      status.hasResponded = true;
      status.ok = true;
      status.completed = true;
      status.statusCode = 200;
      updateAndNotify(status, onStatus);
      return status;
    });
    return { statuses, timedOut: false };
  }

  const deadline = Date.now() + timeoutMs;
  const statuses = await Promise.all(
    REMOTE_SERVICES.map((service) => pingService(service, deadline, onStatus)),
  );
  const timedOut = statuses.some((status) => status.timedOut);
  return { statuses, timedOut };
};
