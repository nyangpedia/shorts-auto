/** While the page is open, tell the local server so; the launcher's server shuts itself down once these stop. */
export function startHeartbeat(): void {
  const beat = () => void fetch("/api/heartbeat").catch(() => undefined);
  beat();
  setInterval(beat, 20_000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) beat(); // a hidden tab's timer is slowed down; ping at once when it comes back
  });
}
