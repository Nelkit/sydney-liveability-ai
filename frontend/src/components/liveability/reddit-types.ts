/**
 * Types mirroring the shape of the NLP analysis returned by
 * `GET /api/reddit/{suburb}` (see backend/core/nlp/pipeline.py).
 */

export type AspectKey =
  | "safety"
  | "food_and_cafe"
  | "nightlife"
  | "affordability"
  | "transport"
  | "community"
  | "noise"
  | "green_space";

export type AspectScore = {
  score: number; // 0..1, 0.5 neutral
  mentions: number;
};

export type EmotionKey =
  | "anger"
  | "disgust"
  | "fear"
  | "joy"
  | "sadness"
  | "surprise"
  | "neutral";

export type SourcePost = {
  text: string;
  url: string;
  score: number;
};

export type SuburbAnalysis = {
  suburb: string;
  post_count: number;
  fetched_at: string;
  aspects: Record<AspectKey, AspectScore>;
  emotions: Partial<Record<EmotionKey, number>>;
  narrative: string;
  sources: SourcePost[];
};

export const ASPECT_ORDER: AspectKey[] = [
  "safety",
  "transport",
  "affordability",
  "food_and_cafe",
  "nightlife",
  "community",
  "green_space",
  "noise",
];

export const ASPECT_LABEL: Record<AspectKey, string> = {
  safety: "Safety",
  transport: "Transport",
  affordability: "Affordability",
  food_and_cafe: "Food & Cafe",
  nightlife: "Nightlife",
  community: "Community",
  green_space: "Green Space",
  noise: "Noise",
};

export const EMOTION_ORDER: EmotionKey[] = [
  "joy",
  "surprise",
  "neutral",
  "sadness",
  "fear",
  "anger",
  "disgust",
];

export const EMOTION_COLOR: Record<EmotionKey, string> = {
  joy: "#f59e0b",
  surprise: "#06b6d4",
  neutral: "#94a3b8",
  sadness: "#6366f1",
  fear: "#8b5cf6",
  anger: "#ef4444",
  disgust: "#84cc16",
};
