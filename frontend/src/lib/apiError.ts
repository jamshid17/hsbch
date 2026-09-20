import i18n from "../i18n";

export class ApiError extends Error {
  status: number;
  /** Machine-readable name for the failure, when the server sent one.
   * `message` is already translated; this is for branching on. */
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/**
 * Turn a failed response into an error a person can read.
 *
 * Done in stages that each narrow the message, so a later one falling over
 * leaves the earlier, worse-but-readable answer standing. The raw body is
 * only ever the last resort: a user who is shown `{"detail":{"code":...}}`
 * learns nothing, and that is what happened when an object `detail` met a
 * client that only understood strings.
 */
export /**
 * Whatever came back, said in words.
 *
 * A body is only worth showing when it reads like a sentence. Markup and
 * payloads are for machines, and a person shown one learns nothing they can
 * act on — the status code carries what little there is to know.
 */
function readable(text: string, status: number): string {
  const trimmed = text.trim();
  const isForMachines =
    !trimmed || trimmed.includes("{") || trimmed.includes("<") || trimmed.length > 300;
  if (isForMachines) {
    return String(
      i18n.t("errors.generic", { status, defaultValue: `Xatolik (${status})` }),
    );
  }
  return trimmed;
}

export async function apiError(res: Response): Promise<ApiError> {
  const text = await res.text().catch(() => "");
  let message = readable(text, res.status);
  let code: string | undefined;

  let detail: unknown;
  try {
    detail = JSON.parse(text)?.detail;
  } catch {
    // Not JSON — an nginx error page, a proxy timeout.
    return new ApiError(message, res.status);
  }

  if (typeof detail === "string") {
    // A developer-facing failure — "Session not found" and the like.
    return new ApiError(detail, res.status);
  }

  if (detail && typeof detail === "object") {
    const { code: c, message: m, params } = detail as {
      code?: unknown;
      message?: unknown;
      params?: Record<string, unknown>;
    };
    // The server's own sentence first, so whatever happens below the reader
    // gets words rather than a payload.
    if (typeof m === "string" && m) message = m;
    if (typeof c === "string" && c) {
      code = c;
      try {
        // Said in the reader's language when this build knows the code.
        // String(): t() is typed to allow an object for a key naming a
        // group rather than a leaf, which these never do.
        message = String(
          i18n.t(`errors.${c}`, { ...(params ?? {}), defaultValue: message }),
        );
      } catch {
        // i18n not ready — the server's sentence already stands.
      }
    }
  }

  return new ApiError(message, res.status, code);
}

