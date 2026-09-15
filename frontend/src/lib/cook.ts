/** Index of the step after index. Stays on the last step. */
export function nextStep(index: number, stepCount: number): number {
	return Math.max(0, Math.min(index + 1, stepCount - 1));
}

/** Index of the step before index. Stays on the first step. */
export function previousStep(index: number): number {
	return Math.max(index - 1, 0);
}

/** The ?step= URL parameter (1-based) as an index into the steps. */
export function stepFromParam(value: string | null, stepCount: number): number {
	const step = Number(value);
	return Number.isInteger(step) && step >= 1 ? Math.min(step, stepCount) - 1 : 0;
}

export interface Timer {
	id: number;
	label: string;
	stepNumber: number;
	endsAt: number;
}

export function remainingMs(timer: Timer, now: number): number {
	return Math.max(0, timer.endsAt - now);
}

/** 1_200_000 -> "20:00", 4_500_000 -> "1:15:00". Rounds up so a timer shows 0:00 only when done. */
export function formatClock(ms: number): string {
	const total = Math.ceil(ms / 1000);
	const hours = Math.floor(total / 3600);
	const minutes = Math.floor((total % 3600) / 60);
	const seconds = total % 60;
	const pad = (n: number) => String(n).padStart(2, '0');
	return hours ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`;
}
