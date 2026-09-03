import pdfParse from 'pdf-parse';

/**
 * Extracts embedded text from a PDF buffer. This works for text-layer PDFs
 * (most direct county-clerk / TexasFile exports); it returns an empty string
 * for scanned image-only instruments, which need real OCR (e.g. Tesseract or
 * a cloud OCR API) — wire that in here as a fallback when `text.trim()` comes
 * back empty, once you've picked an OCR provider.
 */
export async function extractPdfText(buffer: Buffer): Promise<string> {
  try {
    const result = await pdfParse(buffer);
    return result.text ?? '';
  } catch {
    return '';
  }
}
