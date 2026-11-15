import jsQR from 'jsqr';

const EQUIPMENT_ID = /^[a-z0-9][a-z0-9._-]{1,80}$/i;

export function parseEquipmentId(text: string): string | null {
  const value = text.trim();
  if (EQUIPMENT_ID.test(value)) return value;

  try {
    const url = new URL(value);
    const fromQuery = url.searchParams.get('id') ?? url.searchParams.get('equipment_id');
    const last = url.pathname.split('/').filter(Boolean).pop() ?? '';
    const candidate = fromQuery ?? last;
    return EQUIPMENT_ID.test(candidate) ? candidate : null;
  } catch {
    return null;
  }
}

export function decodeQrFromVideo(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement = document.createElement('canvas'),
): string | null {
  if (video.readyState < 2 || !video.videoWidth) return null;

  const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) return null;

  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const data = context.getImageData(0, 0, canvas.width, canvas.height);
  const code = jsQR(data.data, data.width, data.height, {
    inversionAttempts: 'dontInvert',
  });

  return code ? parseEquipmentId(code.data) : null;
}
