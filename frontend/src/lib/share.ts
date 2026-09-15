/**
 * The recipe link passed to /add by the share sheet or a shortcut: ?url=, or the first
 * link inside ?text=, which is where Android apps often put it.
 */
export function sharedUrl(params: URLSearchParams): string {
	const url = params.get('url')?.trim();
	if (url) return url;
	return params.get('text')?.match(/https?:\/\/\S+/)?.[0] ?? '';
}
