const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export const MAX_TTS_LENGTH = 1000;

export function calculateAudioLevelFromFrequencyData(data: Uint8Array): number {
  if (data.length === 0) {
    return 0;
  }

  let sum = 0;

  for (let index = 0; index < data.length; index += 1) {
    const sample = data[index] / 255;
    sum += sample * sample;
  }

  return clamp(Math.sqrt(sum / data.length) * 1.75, 0, 1);
}

export function estimateListeningLevel(text: string): number {
  if (!text.trim()) {
    return 0;
  }

  const normalizedLength = clamp(text.trim().length / 48, 0, 1);
  const cadenceSeed = Array.from(text).reduce((total, character) => total + character.charCodeAt(0), 0);
  const cadence = (cadenceSeed % 9) / 30;

  return clamp(0.18 + normalizedLength * 0.36 + cadence, 0.16, 0.78);
}

export function truncateForTts(text: string, maxLength = MAX_TTS_LENGTH): string {
  const normalized = text.replace(/\s+/g, ' ').trim();

  if (normalized.length <= maxLength) {
    return normalized;
  }

  const sliced = normalized.slice(0, maxLength);
  const sentenceBoundary = Math.max(
    sliced.lastIndexOf('. '),
    sliced.lastIndexOf('? '),
    sliced.lastIndexOf('! '),
  );
  const clauseBoundary = Math.max(sliced.lastIndexOf('; '), sliced.lastIndexOf(', '));
  const boundary = sentenceBoundary > maxLength * 0.55 ? sentenceBoundary + 1 : clauseBoundary;
  const truncated = boundary > maxLength * 0.45 ? sliced.slice(0, boundary).trim() : sliced.trim();

  return `${truncated}…`;
}
