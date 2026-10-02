/**
 * Flavour bases for inventing recipes. A base is the set of seasonings a dish is built on, which
 * matters more to how it tastes than the cuisine label or the main vegetable: a tomato-and-aubergine
 * pasta and a tomato-and-chickpea stew are the same meal as far as your palate is concerned.
 *
 * Each pantry names real ingredients, because "Ethiopian-style" alone gets you a tomato stew with a
 * pinch of paprika. Pantries are vegetarian: kombu dashi rather than bonito, mushroom oyster sauce,
 * soy rather than fish sauce. The rut goes last.
 */
export type Flavour = { key: string; name: string; from: string; pantry: string };

export const FLAVOURS: Flavour[] = [
	{ key: 'berbere', name: 'Berbere', from: 'Ethiopian', pantry: 'berbere, niter kibbeh, mitmita, fenugreek, teff' },
	{ key: 'gochujang', name: 'Gochujang', from: 'Korean', pantry: 'gochujang, gochugaru, kimchi, doenjang, toasted sesame' },
	{ key: 'sichuan', name: 'Sichuan', from: 'Chinese', pantry: 'doubanjiang, Sichuan pepper, Chinkiang black vinegar, chilli oil' },
	{ key: 'miso-dashi', name: 'Miso & dashi', from: 'Japanese', pantry: 'miso, kombu dashi, mirin, sake, shichimi' },
	{
		key: 'harissa',
		name: 'Harissa & preserved lemon',
		from: 'North African',
		pantry: 'harissa, ras el hanout, preserved lemon, dates'
	},
	{
		key: 'tahini',
		name: 'Tahini, lemon & yoghurt',
		from: 'Levantine, Turkish',
		pantry: "tahini, lemon, yoghurt, sumac, za'atar, pomegranate molasses, pul biber"
	},
	{ key: 'smoky-chilli', name: 'Smoky chilli', from: 'Mexican', pantry: 'chipotle, ancho, cumin, lime, coriander, masa' },
	{
		key: 'coconut',
		name: 'Coconut, chilli & lime',
		from: 'Thai, Malaysian, Indonesian',
		pantry: 'coconut milk, lemongrass, lime leaves, galangal, Thai basil, light soy sauce'
	},
	{
		key: 'south-asian',
		name: 'South Asian spice',
		from: 'Indian, Sri Lankan',
		pantry: 'cumin, coriander, turmeric, garam masala, mustard seeds, curry leaves, ghee'
	},
	{
		key: 'soy-ginger',
		name: 'Soy, ginger & sesame',
		from: 'Chinese, Cantonese',
		pantry: 'soy sauce, ginger, sesame oil, Shaoxing wine, hoisin, mushroom oyster sauce'
	},
	{
		key: 'herb-dairy',
		name: 'Herbs & dairy',
		from: 'French, British',
		pantry: 'butter, crème fraîche, Gruyère, tarragon, Dijon mustard, chives'
	},
	{ key: 'tomato', name: 'Tomato & garlic', from: 'Italian', pantry: 'tomatoes, garlic, basil, oregano, Parmesan, balsamic' }
];

/** The API's limit on a whole brief, base line included. Keep in step with MAX_BRIEF in backend/app/main.py. */
export const MAX_BRIEF = 500;

/** The lines added after whatever was typed. */
function extras(flavour: Flavour | undefined, vegetarian: boolean): string[] {
	const lines: string[] = [];
	if (vegetarian) lines.push('Vegetarian.');
	if (flavour) lines.push(`Flavour base: ${flavour.from}, ${flavour.name.toLowerCase()}. Build it around ${flavour.pantry}.`);
	return lines;
}

/**
 * The brief sent to Claude. A base on its own is enough: pick one and get a recipe with no typing.
 * Ticking vegetarian on its own is not, so with nothing typed and no base this returns "".
 */
export function composeBrief(typed: string, flavour: Flavour | undefined, vegetarian: boolean): string {
	const wanted = typed.trim();
	if (!wanted && !flavour) return '';
	return [wanted, ...extras(flavour, vegetarian)].filter(Boolean).join('\n');
}

/** How many characters are left for typing once the base line and vegetarian have taken their share. */
export function briefRoom(flavour: Flavour | undefined, vegetarian: boolean): number {
	const added = extras(flavour, vegetarian);
	return MAX_BRIEF - added.reduce((sum, line) => sum + line.length + 1, 0);
}
