/** One spoken word with its time in the narration (seconds). */
export interface TimedWord {
  text: string;
  start: number;
  end: number;
}

/** One on-screen subtitle line. With `words`, the word being spoken is highlighted. */
export interface SubtitleItem {
  start: number;
  end: number;
  text: string;
  words?: TimedWord[];
}

/** Everything the API's renderer passes in (see apps/api/app/production/renderer.py). */
export interface ShortsProps {
  videoSrc: string;
  audioSrc: string;
  bgmSrc?: string | null;
  bgmVolume?: number;
  subtitles: SubtitleItem[];
  durationInFrames: number;
  title?: string | null;
  sceneStarts?: number[];
}
