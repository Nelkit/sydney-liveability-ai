export type RouterCategory = "crime" | "gis" | "sentiment" | "comparator" | "out_of_scope";

export type SourceKind = "reddit" | "bocsar" | "arcgis" | "osm" | "tfnsw" | "pdf";

export type Citation = {
  n: number;
  src: SourceKind;
  suburbs: string[];
  detail: string;
  retrieved?: number;
};

export type Claim = {
  text: string;
  cites: Citation[];
};

export type RouterMeta = {
  categories: RouterCategory[];
  suburbs: string[];
  latencyMs: number;
};

export type AssistantMessage = {
  role: "assistant";
  ts: string;
  router: RouterMeta;
  claims: Claim[];
  summary?: { suburbs: string[] };
};

export type SuburbScore = {
  name: string;
  score: number;
  transport: number;
  safety: number;
  lifestyle: number;
  affordability: number;
  proximity: number;
  facilities: number;
  walkability: number;
  crimeIdx: number;
  sentiment: number;
  cafes: number;
  restaurants: number;
  parks: number;
  playgrounds: number;
  sa4: string;
};

export type AspectScore = {
  aspect: string;
  pos: number;
  mentions: number;
};

export type EmotionProfile = Record<
  "joy" | "surprise" | "neutral" | "sadness" | "fear" | "anger" | "disgust",
  number
>;

export type RedditHighlight = {
  id: string;
  q: string;
  aspect: string;
  sentiment: "pos" | "neu" | "neg";
  up: number;
};

export type CrimeRow = {
  cat: string;
  v: number;
  trend: number;
};

export type EvidenceTrace = {
  router: { ms: number; model: string; note: string };
  specialists: { id: string; ms: number; retrieved: number; store: string }[];
};

export type ChatAPIResponse = {
  answer: string;
  claims?: Claim[];
  sources: SourceKind[];
  suburb_scores?: SuburbScore[];
  map_state?: {
    activeSuburbs: string[];
    layer: string;
    heatmap_weights?: Record<string, number>;
  };
  router?: RouterMeta;
  quality?: {
    evidence_trace_summary: string | EvidenceTrace;
  };
  aspect_scores?: Record<string, AspectScore[]>;
  emotion_profile?: Record<string, EmotionProfile>;
  reddit_highlights?: Record<string, RedditHighlight[]>;
  crime_breakdown?: Record<string, CrimeRow[]>;
};
