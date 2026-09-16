// Draws the logo and the course illustrations, and renders every icon the app needs into static/.
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

// One drawing per course, for recipes with no photo: invented ones never have a picture, and
// plenty of imported pages don't either. Flat shapes on a 512 grid, cream on a tinted ground,
// in the same language as the logo. The card tints the background itself, so these draw on none.
const courses = {
	breakfast: `
    <g fill="${CREAM}">
      <ellipse cx="256" cy="300" rx="150" ry="96"/>
    </g>
    <ellipse cx="256" cy="288" rx="66" ry="52" fill="${SPARK}"/>
    <g stroke="${CREAM}" stroke-width="16" stroke-linecap="round" fill="none">
      <path d="M150 168 C134 150 166 136 150 116"/>
      <path d="M256 158 C240 138 272 124 256 104"/>
      <path d="M362 168 C346 150 378 136 362 116"/>
    </g>`,
	starter: `
    <g fill="${CREAM}">
      <path d="M136 268 H376 Q376 356 256 356 Q136 356 136 268 Z"/>
      <rect x="196" y="368" width="120" height="18" rx="9"/>
      <rect x="146" y="238" width="220" height="20" rx="10"/>
    </g>
    <g stroke="${SPARK}" stroke-width="16" stroke-linecap="round" fill="none">
      <path d="M200 196 C186 176 214 162 200 142"/>
      <path d="M256 196 C242 172 270 156 256 132"/>
      <path d="M312 196 C298 176 326 162 312 142"/>
    </g>`,
	main: `
    <g fill="${CREAM}">
      <path d="M116 300 H396 Q396 392 256 392 Q116 392 116 300 Z"/>
      <rect x="106" y="278" width="300" height="24" rx="12"/>
    </g>
    <g fill="${SPARK}">
      <ellipse cx="256" cy="228" rx="104" ry="52"/>
    </g>
    <g fill="${TERRACOTTA}" opacity="0.35">
      <ellipse cx="256" cy="228" rx="104" ry="52"/>
    </g>
    <g stroke="${CREAM}" stroke-width="18" stroke-linecap="round" fill="none">
      <path d="M186 214 C172 194 200 180 186 160"/>
      <path d="M256 206 C242 182 270 166 256 142"/>
      <path d="M326 214 C312 194 340 180 326 160"/>
    </g>`,
	side: `
    <g fill="${CREAM}">
      <path d="M150 250 H362 Q362 344 256 344 Q150 344 150 250 Z"/>
      <rect x="150" y="226" width="212" height="20" rx="10"/>
    </g>
    <g fill="${SPARK}">
      <circle cx="212" cy="190" r="30"/>
      <circle cx="286" cy="176" r="24"/>
      <circle cx="330" cy="200" r="18"/>
    </g>`,
	dessert: `
    <g fill="${CREAM}">
      <path d="M160 246 H352 L318 386 Q316 400 300 400 H212 Q196 400 194 386 Z"/>
      <path d="M150 214 Q256 150 362 214 Q256 268 150 214 Z"/>
    </g>
    <path fill="${SPARK}" d="${spark(256, 132, 40)}"/>`,
	baking: `
    <g fill="${CREAM}">
      <path d="M140 250 H372 V346 Q372 386 332 386 H180 Q140 386 140 346 Z"/>
      <rect x="120" y="224" width="272" height="26" rx="13"/>
    </g>
    <path d="M140 250 H372 V290 Q316 316 256 290 Q196 264 140 290 Z" fill="${SPARK}" opacity="0.85"/>
    <g stroke="${CREAM}" stroke-width="16" stroke-linecap="round" fill="none">
      <path d="M212 184 C198 164 226 150 212 130"/>
      <path d="M300 184 C286 164 314 150 300 130"/>
    </g>`,
	snack: `
    <g fill="${CREAM}">
      <path d="M256 128 L392 366 Q400 382 382 382 H130 Q112 382 120 366 Z"/>
    </g>
    <g fill="${SPARK}">
      <circle cx="256" cy="268" r="24"/>
      <circle cx="198" cy="334" r="20"/>
      <circle cx="316" cy="330" r="18"/>
    </g>`,
	drink: `
    <g fill="${CREAM}">
      <path d="M170 160 H342 L312 344 Q308 366 286 366 H226 Q204 366 200 344 Z"/>
      <rect x="196" y="380" width="120" height="18" rx="9"/>
    </g>
    <path d="M182 220 H330 L312 344 Q308 366 286 366 H226 Q204 366 200 344 Z" fill="${SPARK}" opacity="0.8"/>
    <circle cx="352" cy="150" r="26" fill="${SPARK}"/>`,
	sauce: `
    <g fill="${CREAM}">
      <path d="M212 120 H300 V168 L332 206 V368 Q332 392 306 392 H206 Q180 392 180 368 V206 L212 168 Z"/>
    </g>
    <path d="M180 260 H332 V368 Q332 392 306 392 H206 Q180 392 180 368 Z" fill="${SPARK}" opacity="0.8"/>
    <rect x="204" y="96" width="104" height="26" rx="13" fill="${CREAM}"/>`,
	// Anything with no course set. Deliberately plainer than the real courses: a covered dish,
	// no cutlery and no spark, so it reads as "nothing said" rather than as another course.
	other: `
    <g fill="${CREAM}">
      <path d="M116 300 H396 Q396 330 366 330 H146 Q116 330 116 300 Z"/>
      <path d="M146 296 Q146 172 256 172 Q366 172 366 296 Z"/>
      <circle cx="256" cy="146" r="22"/>
    </g>
    <path d="M146 296 Q146 172 256 172 Q366 172 366 296 Z" fill="${TERRACOTTA}" opacity="0.18"/>`
};

function courseArt(art) {
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img">
  <g>${art}</g>
</svg>
`;
}

const out = new URL('../static/', import.meta.url);
await mkdir(new URL('icons/', out), { recursive: true });
await mkdir(new URL('course/', out), { recursive: true });
await writeFile(new URL('favicon.svg', out), rounded);
for (const [course, art] of Object.entries(courses)) {
	await writeFile(new URL(`course/${course}.svg`, out), courseArt(art));
}

const png = (svg, size, file) =>
	sharp(Buffer.from(svg)).resize(size, size).png().toFile(new URL(file, out).pathname);

await Promise.all([
	png(rounded, 32, 'favicon-32.png'),
	png(rounded, 192, 'icons/icon-192.png'),
	png(rounded, 512, 'icons/icon-512.png'),
	png(maskable, 512, 'icons/maskable-512.png'),
	png(square, 180, 'apple-touch-icon.png')
]);
console.log(`icons and ${Object.keys(courses).length} course illustrations written to static/`);
