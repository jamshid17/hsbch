/**
 * Downscale a (possibly huge) phone photo before upload: caps the longest side
 * and re-encodes as JPEG. Keeps receipts readable for OCR while cutting upload
 * size from several MB to a few hundred KB — avoiding 413 errors and speeding
 * up scanning. Falls back to the original file if anything goes wrong.
 */
export async function downscaleImage(
  file: File,
  maxDim = 1800,
  quality = 0.85
): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));

    // Small enough already — don't recompress.
    if (scale === 1 && file.size < 1_500_000) {
      bitmap.close?.();
      return file;
    }

    const w = Math.round(bitmap.width * scale);
    const h = Math.round(bitmap.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close?.();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", quality)
    );
    if (!blob) return file;

    return new File([blob], "receipt.jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}
