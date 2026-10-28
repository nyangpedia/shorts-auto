export interface TimedWord {
  text: string;
  start: number;
  end: number;
}

export interface SubtitleItem {
  start: number;
  end: number;
  text: string;
  /** Word timings from the narration; when present the spoken word is highlighted. */
  words?: TimedWord[];
}

export interface ShortsProps {
  videoSrc: string;
  audioSrc: string;
  bgmSrc?: string;
  bgmVolume?: number;
  subtitles: SubtitleItem[];
  durationInFrames: number;
  title?: string;
  sceneStarts?: number[];
}
