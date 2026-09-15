// Draws the logo once and renders every icon the app needs into static/.
// Run from frontend/: node scripts/icons.mjs
import { mkdir, writeFile } from 'node:fs/promises';
import sharp from 'sharp';

const TERRACOTTA = '#b4442b';
const CREAM = '#fbf3e6';
const SPARK = '#ffc94d';

/** A four-pointed spark centred on (cx, cy). */
function spark(cx, cy, r) {
	const s = r * 0.3;
	return `M${cx} ${cy - r} L${cx + s} ${cy - s} L${cx + r} ${cy} L${cx + s} ${cy + s} L${cx} ${cy + r} L${cx - s} ${cy + s} L${cx - r} ${cy} L${cx - s} ${cy - s} Z`;
}

// A pot that has blown its lid off: steam rising, the lid flying askew, two sparks.
// Drawn on a 512 grid; the drawing's centre is roughly (256, 246).
const drawing = `
  <g stroke="${CREAM}" stroke-width="16" stroke-linecap="round" fill="none">
    <path d="M204 244 C190 228 218 214 204 196"/>
    <path d="M256 244 C242 224 270 208 256 188"/>
    <path d="M308 244 C294 228 322 214 308 196"/>
  </g>
  <g fill="${CREAM}" transform="rotate(-20 256 150) translate(26 -14)">
    <rect x="140" y="140" width="232" height="26" rx="13"/>
    <rect x="232" y="114" width="48" height="32" rx="12"/>
  </g>
  <path fill="${SPARK}" d="${spark(404, 112, 34)}"/>
  <path fill="${SPARK}" d="${spark(122, 176, 20)}"/>
  <g fill="${CREAM}">
    <rect x="116" y="262" width="280" height="32" rx="16"/>
    <rect x="88" y="312" width="64" height="24" rx="12"/>
    <rect x="360" y="312" width="64" height="24" rx="12"/>
    <path d="M140 286 H372 V370 Q372 414 328 414 H184 Q140 414 140 370 Z"/>
  </g>
  <rect x="140" y="340" width="232" height="12" fill="${TERRACOTTA}" opacity="0.35"/>`;

function logo({ corner, scale }) {
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="${corner}" fill="${TERRACOTTA}"/>
  <g transform="translate(256 256) scale(${scale}) translate(-256 -246)">${drawing}</g>
</svg>
`;
}

// Browsers and Android launchers show this with its own rounded corners.
const rounded = logo({ corner: 112, scale: 1 });
// iOS rounds home screen icons itself and turns transparent corners black.
const square = logo({ corner: 0, scale: 1 });
// Android crops maskable icons to shapes as small as a circle 80% of the width,
// so the drawing shrinks to keep the sparks and handles inside it.
const maskable = logo({ corner: 0, scale: 0.8 });

const out = new URL('../static/', import.meta.url);
await mkdir(new URL('icons/', out), { recursive: true });
await writeFile(new URL('favicon.svg', out), rounded);

const png = (svg, size, file) =>
	sharp(Buffer.from(svg)).resize(size, size).png().toFile(new URL(file, out).pathname);

await Promise.all([
	png(rounded, 32, 'favicon-32.png'),
	png(rounded, 192, 'icons/icon-192.png'),
	png(rounded, 512, 'icons/icon-512.png'),
	png(maskable, 512, 'icons/maskable-512.png'),
	png(square, 180, 'apple-touch-icon.png')
]);
console.log('icons written to static/');
