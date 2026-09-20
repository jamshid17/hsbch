import { describe, expect, it } from "vitest";
import { apiError } from "./apiError";

/**
 * A raw `{"detail":{"code":...}}` once reached a user's screen, under a
 * photo of a bedspread, where it taught them nothing. These are the shapes
 * that turn into a sentence, and the rule that the body itself is only ever
 * the last resort.
 */
function failed(status: number, body: string): Response {
  return { status, statusText: "", text: async () => body } as Response;
}

function detail(value: unknown): Response {
  return failed(422, JSON.stringify({ detail: value }));
}

describe("apiError", () => {
  it("translates a coded failure into the reader's language", async () => {
    const e = await apiError(
      detail({
        code: "scan.not_a_receipt",
        message: "Bu chek emasga o'xshaydi.",
      }),
    );

    expect(e.code).toBe("scan.not_a_receipt");
    expect(e.message).not.toContain("{");
    expect(e.message).toContain("chek");
  });

  it("fills the placeholders from params", async () => {
    const e = await apiError(
      detail({
        code: "upload.too_large",
        message: "unused",
        params: { mb: "7.3", max: 5 },
      }),
    );

    expect(e.message).toContain("7.3");
    expect(e.message).toContain("5");
  });

  it("falls back to the server's sentence for a code it doesn't know", async () => {
    const e = await apiError(
      detail({ code: "scan.invented_later", message: "Server aytgani" }),
    );

    expect(e.message).toBe("Server aytgani");
    expect(e.code).toBe("scan.invented_later");
  });

  it("passes a plain string detail straight through", async () => {
    const e = await apiError(detail("Session not found"));

    expect(e.message).toBe("Session not found");
    expect(e.code).toBeUndefined();
  });

  it("reads an object detail with no code as words", async () => {
    const e = await apiError(detail({ message: "Nimadir noto'g'ri" }));

    expect(e.message).toBe("Nimadir noto'g'ri");
  });

  it("does not put an nginx error page in front of anyone", async () => {
    const e = await apiError(failed(502, "<html>502 Bad Gateway</html>"));

    expect(e.message).not.toContain("<");
    // The status still travels, because it is the one thing worth quoting
    // when someone reports this.
    expect(e.message).toContain("502");
  });

  it("keeps a short plain-text body, which is a sentence already", async () => {
    const e = await apiError(failed(429, "Too many requests"));

    expect(e.message).toBe("Too many requests");
  });

  it("still says something when the body is empty", async () => {
    const e = await apiError(failed(500, ""));

    expect(e.message).toBeTruthy();
    expect(e.message).not.toContain("{");
  });

  it("never shows the payload, whatever the shape", async () => {
    for (const body of [
      JSON.stringify({ detail: { code: 42 } }),
      JSON.stringify({ detail: [] }),
      JSON.stringify({ detail: null }),
      JSON.stringify({ nope: 1 }),
    ]) {
      const e = await apiError(failed(400, body));
      expect(e.message).not.toMatch(/"detail"/);
    }
  });
});
