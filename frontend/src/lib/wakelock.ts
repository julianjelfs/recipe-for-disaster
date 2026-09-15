/**
 * Keep the screen on while cooking. The browser drops the lock when the tab is hidden,
 * so take it again each time the page becomes visible. Returns a function that stops.
 */
export function keepScreenOn(onChange: (active: boolean) => void): () => void {
	let sentinel: WakeLockSentinel | null = null;
	let stopped = false;

	async function acquire() {
		if (!('wakeLock' in navigator) || document.visibilityState !== 'visible') {
			onChange(false);
			return;
		}
		try {
			sentinel = await navigator.wakeLock.request('screen');
			onChange(true);
			sentinel.addEventListener('release', () => onChange(false));
		} catch {
			// Refused, e.g. low battery or not a secure context.
			onChange(false);
		}
	}

	function onVisibilityChange() {
		if (!stopped && document.visibilityState === 'visible') acquire();
	}

	document.addEventListener('visibilitychange', onVisibilityChange);
	acquire();

	return () => {
		stopped = true;
		document.removeEventListener('visibilitychange', onVisibilityChange);
		sentinel?.release();
	};
}
