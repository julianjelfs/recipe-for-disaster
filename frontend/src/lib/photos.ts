/**
 * Shrink a page photo before it is sent. A phone camera's photo is several megabytes, more than
 * Claude accepts, and Claude scales anything past 1568 pixels on the long edge down to that anyway.
 * At that size a full printed page still reads cleanly, and the upload is a few hundred kilobytes.
 */

export const LONG_EDGE = 1568;
const JPEG_QUALITY = 0.85;

export interface PhotoUpload {
	media_type: 'image/jpeg';
	/** Base64, no data: prefix. */
	data: string;
}

/** The size to draw a width x height image at so its long edge is at most `max`. Never enlarges. */
export function fitWithin(width: number, height: number, max = LONG_EDGE): { width: number; height: number } {
	const scale = Math.min(1, max / Math.max(width, height));
	return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** A JPEG of the photo, no bigger than LONG_EDGE on its long edge, ready for POST /api/photo. */
export async function prepare(file: Blob): Promise<PhotoUpload> {
	// imageOrientation: a phone photo taken sideways is stored sideways with a note to turn it.
	const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
	const { width, height } = fitWithin(bitmap.width, bitmap.height);
	const canvas = document.createElement('canvas');
	canvas.width = width;
	canvas.height = height;
	canvas.getContext('2d')!.drawImage(bitmap, 0, 0, width, height);
	bitmap.close();
	const blob = await new Promise<Blob>((resolve, reject) =>
		canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not encode the photo.'))), 'image/jpeg', JPEG_QUALITY)
	);
	return { media_type: 'image/jpeg', data: await base64(blob) };
}

function base64(blob: Blob): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result).split(',', 2)[1]);
		reader.onerror = () => reject(reader.error);
		reader.readAsDataURL(blob);
	});
}
