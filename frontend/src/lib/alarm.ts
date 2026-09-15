let context: AudioContext | null = null;

/** Browsers only allow sound after a user gesture, so call this from a click (e.g. starting a timer). */
export function unlockSound(): void {
	context ??= new AudioContext();
	if (context.state === 'suspended') context.resume();
}

/** A short beep and a buzz, for a finished timer. */
export function alarm(): void {
	navigator.vibrate?.([300, 150, 300]);
	if (!context) return;
	const start = context.currentTime;
	const oscillator = context.createOscillator();
	const gain = context.createGain();
	oscillator.frequency.value = 880;
	gain.gain.setValueAtTime(0.3, start);
	gain.gain.exponentialRampToValueAtTime(0.001, start + 0.6);
	oscillator.connect(gain).connect(context.destination);
	oscillator.start(start);
	oscillator.stop(start + 0.6);
}
