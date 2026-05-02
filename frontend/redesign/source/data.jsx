// Static demo data for the Sydney Liveability AI mockup
const DATA = {
  suburbs: {
    Newtown: {
      score: 78,
      transport: 85, safety: 62, lifestyle: 92, affordability: 48,
      facilities: 67.4, walkability: 88.2, crimeIdx: 0.41, sentiment: 0.71,
      cafes: 62, restaurants: 84, parks: 11, playgrounds: 6,
      sa4: "Inner West",
    },
    Redfern: {
      score: 74,
      transport: 88, safety: 58, lifestyle: 81, affordability: 55,
      facilities: 54.1, walkability: 81.7, crimeIdx: 0.52, sentiment: 0.64,
      cafes: 41, restaurants: 53, parks: 7, playgrounds: 4,
      sa4: "City and Inner South",
    },
    Glebe: {
      score: 76,
      transport: 79, safety: 71, lifestyle: 80, affordability: 51,
      facilities: 51.8, walkability: 84.1, crimeIdx: 0.34, sentiment: 0.69,
      cafes: 38, restaurants: 47, parks: 9, playgrounds: 5,
      sa4: "City and Inner South",
    },
    "Surry Hills": {
      score: 81,
      transport: 90, safety: 68, lifestyle: 95, affordability: 39,
      facilities: 71.2, walkability: 92.4, crimeIdx: 0.38, sentiment: 0.78,
      cafes: 88, restaurants: 112, parks: 6, playgrounds: 3,
      sa4: "City and Inner South",
    },
    Waterloo: {
      score: 70,
      transport: 81, safety: 54, lifestyle: 73, affordability: 58,
      facilities: 34.7, walkability: 79.0, crimeIdx: 0.49, sentiment: 0.55,
      cafes: 35, restaurants: 51, parks: 33, playgrounds: 12,
      sa4: "City and Inner South",
    },
    Marrickville: {
      score: 75,
      transport: 76, safety: 70, lifestyle: 84, affordability: 60,
      facilities: 49.0, walkability: 78.5, crimeIdx: 0.36, sentiment: 0.66,
      cafes: 44, restaurants: 58, parks: 14, playgrounds: 9,
      sa4: "Inner West",
    },
  },
  // Aspect-based sentiment per suburb (DeBERTa-v3 ABSA mock)
  aspects: {
    Newtown: [
      { aspect: "Nightlife",     pos: 0.91, mentions: 312 },
      { aspect: "Food & Cafe",   pos: 0.88, mentions: 484 },
      { aspect: "Community",     pos: 0.79, mentions: 211 },
      { aspect: "Transport",     pos: 0.74, mentions: 168 },
      { aspect: "Affordability", pos: 0.31, mentions: 142 },
      { aspect: "Safety",        pos: 0.51, mentions: 197 },
      { aspect: "Noise",         pos: 0.22, mentions: 88  },
      { aspect: "Green Space",   pos: 0.58, mentions: 64  },
    ],
    Glebe: [
      { aspect: "Nightlife",     pos: 0.62, mentions: 89  },
      { aspect: "Food & Cafe",   pos: 0.81, mentions: 152 },
      { aspect: "Community",     pos: 0.84, mentions: 174 },
      { aspect: "Transport",     pos: 0.69, mentions: 102 },
      { aspect: "Affordability", pos: 0.42, mentions: 98  },
      { aspect: "Safety",        pos: 0.72, mentions: 115 },
      { aspect: "Noise",         pos: 0.61, mentions: 41  },
      { aspect: "Green Space",   pos: 0.79, mentions: 78  },
    ],
    Waterloo: [
      { aspect: "Nightlife",     pos: 0.86, mentions: 72  },
      { aspect: "Food & Cafe",   pos: 0.85, mentions: 121 },
      { aspect: "Community",     pos: 0.51, mentions: 89  },
      { aspect: "Transport",     pos: 0.67, mentions: 134 },
      { aspect: "Affordability", pos: 0.55, mentions: 98  },
      { aspect: "Safety",        pos: 0.34, mentions: 156 },
      { aspect: "Noise",         pos: 0.29, mentions: 61  },
      { aspect: "Green Space",   pos: 0.62, mentions: 44  },
    ],
  },
  emotions: {
    Newtown: { joy: 28, surprise: 14, neutral: 31, sadness: 6, fear: 5, anger: 8, disgust: 8 },
    Waterloo: { joy: 9, surprise: 16, neutral: 48, sadness: 8, fear: 7, anger: 6, disgust: 10 },
    Glebe: { joy: 22, surprise: 12, neutral: 42, sadness: 7, fear: 4, anger: 5, disgust: 8 },
  },
  // Reddit highlights (mocked, with permalink-shape ids)
  reddit: {
    Newtown: [
      { id: "t3_1abc23", q: "Best brunch on King St — never disappoints. The vibe is unmatched.", aspect: "Food & Cafe", sentiment: "pos", up: 142 },
      { id: "t3_1ade44", q: "Be careful around Enmore Rd late on weekends, can get rowdy.", aspect: "Safety", sentiment: "neg", up: 87 },
      { id: "t3_1aff19", q: "Rents are absurd now. Was paying $480 for a room in 2019, now it's $720.", aspect: "Affordability", sentiment: "neg", up: 211 },
    ],
    Glebe: [
      { id: "t3_2zzx01", q: "Glebe markets every Saturday is the best community event in the inner west.", aspect: "Community", sentiment: "pos", up: 184 },
      { id: "t3_2yyw02", q: "Walking to the Bay Run from Glebe Point Rd is honestly perfect.", aspect: "Green Space", sentiment: "pos", up: 96 },
    ],
    Waterloo: [
      { id: "t3_3wwk08", q: "Tower precinct is improving but still feels disconnected at night.", aspect: "Safety", sentiment: "neu", up: 64 },
      { id: "t3_3vvj09", q: "Light rail and bus options to CBD are great. Don't need a car.", aspect: "Transport", sentiment: "pos", up: 121 },
    ],
  },
  // Crime breakdown (BOCSAR-style, per 100k)
  crime: {
    Newtown: [
      { cat: "Assault (non-DV)", v: 412, trend: -3 },
      { cat: "Theft from person", v: 198, trend: 12 },
      { cat: "Malicious damage", v: 287, trend: -7 },
      { cat: "Drug possession", v: 156, trend: -2 },
    ],
    Glebe: [
      { cat: "Assault (non-DV)", v: 281, trend: -8 },
      { cat: "Theft from person", v: 142, trend: 4 },
      { cat: "Malicious damage", v: 198, trend: -11 },
      { cat: "Drug possession", v: 89, trend: -5 },
    ],
  },
  // Evidence trace (router → specialists → chunks)
  trace: {
    router: { ms: 12, model: "deterministic", note: "keyword RULES + word-boundary suburb match" },
    specialists: [
      { id: "sentiment", ms: 612, retrieved: 14, store: "chroma:reddit_minilm" },
      { id: "gis",       ms: 184, retrieved: 6,  store: "postgis:facilities" },
      { id: "synth",     ms: 1108, retrieved: 0, store: "crew:synthesiser" },
    ],
  },
};

window.DATA = DATA;
