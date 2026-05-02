export type WeightKey = "transport" | "safety" | "lifestyle" | "afford";

export type ImportanceLevelKey =
  | "1" | "2" | "3" | "4" | "5"
  | "6" | "7" | "8" | "9" | "10";

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
  fullHtml?: string;
  detailedSuburb?: string | null;
};
