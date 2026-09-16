/** Formats the picker offers and the backend accepts. Anything else — PDF,
 * documents, video — is refused before a session is even created. */
export const ACCEPTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  // iOS reports phone photos as HEIC; Safari can still decode them, and
  // compressImage() re-encodes to JPEG before upload.
  "image/heic",
  "image/heif",
] as const;

/** The `accept` attribute for the file input. Explicit types rather than
 * `image/*` so the picker itself hides PDFs and documents. */
export const ACCEPT_ATTR = ACCEPTED_IMAGE_TYPES.join(",");

/** Hard ceiling for what leaves the device. */
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;

export function isAcceptedImage(file: File): boolean {
  const type = file.type.toLowerCase();
  if (type) return (ACCEPTED_IMAGE_TYPES as readonly string[]).includes(type);
  // Some Android file managers hand over a File with an empty type; fall back
  // to the extension rather than rejecting a perfectly good photo.
  return /\.(jpe?g|png|webp|gif|heic|heif)$/i.test(file.name);
}

export class ImageTooLargeError extends Error {}

/**
 * Shrink a phone photo until it is comfortably under MAX_UPLOAD_BYTES.
 *
 * Starts by capping the longest side (receipts stay readable for OCR well
 * below full sensor resolution), then, if the JPEG still comes out too big,
 * walks quality down and finally dimensions down until it fits. Each step
 * re-encodes rather than guessing, because compressibility depends entirely on
 * the photo — a glossy receipt under harsh light is several times heavier than
 * a flat one at identical dimensions.
 *
 * Throws ImageTooLargeError only if even a small, heavily compressed version
 * won't fit, which in practice means the image couldn't be decoded at all.
 */
export async function compressImage(
  file: File,
  maxBytes = MAX_UPLOAD_BYTES
): Promise<File> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // Undecodable (often HEIC on a browser without support). Let it through if
    // it's small enough for the server to at least return a clear format
    // error, otherwise stop here rather than uploading megabytes for nothing.
    if (file.size <= maxBytes) return file;
    throw new ImageTooLargeError(file.name);
  }

  try {
    // Already a modest JPEG/PNG — don't recompress and lose detail for nothing.
    if (
      file.size <= maxBytes &&
      Math.max(bitmap.width, bitmap.height) <= 1800 &&
      (file.type === "image/jpeg" || file.type === "image/png")
    ) {
      return file;
    }

    for (const maxDim of [1800, 1400, 1100, 900]) {
      const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));

      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) break;
      ctx.drawImage(bitmap, 0, 0, w, h);

      for (const quality of [0.85, 0.7, 0.55, 0.4]) {
        const blob = await new Promise<Blob | null>((resolve) =>
          canvas.toBlob(resolve, "image/jpeg", quality)
        );
        if (!blob) break;
        if (blob.size <= maxBytes) {
          return new File([blob], "receipt.jpg", { type: "image/jpeg" });
        }
      }
    }

    throw new ImageTooLargeError(file.name);
  } finally {
    bitmap.close?.();
  }
}
