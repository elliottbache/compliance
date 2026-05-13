import { ApiError } from "../api/complianceApi";

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return formatApiError(error);
  }

  if (error instanceof TypeError && error.message === "Failed to fetch") {
    return (
      "Network error: could not reach the FastAPI backend. " +
      "Check that FastAPI is running and that CORS allows http://localhost:5173."
    );
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unexpected error.";
}

function formatApiError(error: ApiError): string {
  const detail = error.detail ? ` ${error.detail}` : "";

  switch (error.status) {
    case 404:
      return `404 — Resource not found or not visible.${detail}`;

    case 422:
      return `422 — Invalid request or request could not be processed.${detail}`;

    case 502:
      return `502 — AI/provider/parsing/evidence validation failure.${detail}`;

    case 500:
      return `500 — Unexpected backend bug.${detail}`;

    default:
      return `${error.status} — API error.${detail || ` ${error.message}`}`;
  }
}