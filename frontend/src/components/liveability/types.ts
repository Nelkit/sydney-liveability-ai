export type WeightKey = "transport" | "safety" | "lifestyle" | "afford";

export type ImportanceLevelKey =
  | "veryImportant"
  | "important"
  | "neutral"
  | "notVeryImportant"
  | "notInterested";

export type ImportanceOption = {
  key: ImportanceLevelKey;
  label: string;
  value: number;
};

export type Weights = Record<WeightKey, number>;

export type Suburb = {
  id: string;
  name: string;
  color: string;
  scoreBase: Weights;
  center: [number, number];
  polygon: [number, number][];
};

export type ChatMessage = {
  role: "ai" | "user";
  html: string;
  source?: string;
};
