import { describe, expect, it } from 'vitest';
import { fitWithin, LONG_EDGE } from './photos';

describe('fitWithin', () => {
	it('shrinks a phone photo so its long edge is the limit, keeping its shape', () => {
		expect(fitWithin(3024, 4032)).toEqual({ width: 1176, height: LONG_EDGE });
		expect(fitWithin(4032, 3024)).toEqual({ width: LONG_EDGE, height: 1176 });
	});

	it('leaves a photo that already fits alone', () => {
		expect(fitWithin(900, 1600)).toEqual({ width: 882, height: 1568 });
		expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
	});
});
