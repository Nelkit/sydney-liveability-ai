import { ImportanceOption, ResponderItem, Suburb, WeightKey } from "./types";

export const importanceOptions: ImportanceOption[] = [
  { key: "veryImportant", label: "Very important", value: 90 },
  { key: "important", label: "Important", value: 75 },
  { key: "neutral", label: "Neutral", value: 50 },
  { key: "notVeryImportant", label: "Not very important", value: 25 },
  { key: "notInterested", label: "Not interested", value: 5 }
];

export const weightPrompts: { key: WeightKey; label: string; prompt: string }[] = [
  {
    key: "transport",
    label: "Transport",
    prompt: "How important is transport to you?"
  },
  {
    key: "safety",
    label: "Safety",
    prompt: "How important is safety to you?"
  },
  {
    key: "lifestyle",
    label: "Lifestyle",
    prompt: "How important is lifestyle (cafes, social life, atmosphere) to you?"
  },
  {
    key: "afford",
    label: "Affordability",
    prompt: "How important is affordability in your decision?"
  }
];

export const suburbs: Suburb[] = [
  {
    id: "glebe",
    name: "Glebe",
    color: "#10b981",
    scoreBase: { transport: 82, safety: 78, lifestyle: 92, afford: 65 },
    center: [-33.8792, 151.1862],
    polygon: [
      [-33.8748, 151.1769],
      [-33.8729, 151.1866],
      [-33.8774, 151.1938],
      [-33.8847, 151.1925],
      [-33.8859, 151.1825],
      [-33.8815, 151.1776]
    ]
  },
  {
    id: "newtown",
    name: "Newtown",
    color: "#3b82f6",
    scoreBase: { transport: 85, safety: 72, lifestyle: 88, afford: 70 },
    center: [-33.8981, 151.1748],
    polygon: [
      [-33.8922, 151.1673],
      [-33.8901, 151.1784],
      [-33.8949, 151.186],
      [-33.9025, 151.1849],
      [-33.9058, 151.1754],
      [-33.9015, 151.1684]
    ]
  },
  {
    id: "redfern",
    name: "Redfern",
    color: "#f59e0b",
    scoreBase: { transport: 90, safety: 60, lifestyle: 70, afford: 85 },
    center: [-33.8923, 151.2049],
    polygon: [
      [-33.8867, 151.1983],
      [-33.8848, 151.2094],
      [-33.8908, 151.2148],
      [-33.8978, 151.2127],
      [-33.8998, 151.202],
      [-33.8943, 151.1974]
    ]
  },
  {
    id: "surry",
    name: "Surry Hills",
    color: "#8b5cf6",
    scoreBase: { transport: 80, safety: 68, lifestyle: 85, afford: 55 },
    center: [-33.8842, 151.2108],
    polygon: [
      [-33.8786, 151.2048],
      [-33.8768, 151.2168],
      [-33.8829, 151.2211],
      [-33.8899, 151.219],
      [-33.8915, 151.2086],
      [-33.8867, 151.2043]
    ]
  },
  {
    id: "hay",
    name: "Haymarket",
    color: "#ef4444",
    scoreBase: { transport: 95, safety: 55, lifestyle: 72, afford: 45 },
    center: [-33.8782, 151.2053],
    polygon: [
      [-33.8734, 151.1991],
      [-33.8713, 151.2091],
      [-33.8762, 151.2141],
      [-33.8822, 151.2122],
      [-33.8836, 151.2026],
      [-33.8789, 151.1986]
    ]
  }
];

export const quickChips = [
  "Is Newtown safe at night?",
  "Best cafes in Glebe?",
  "Redfern transport links?",
  "Compare Newtown vs Glebe",
  "Surry Hills for professionals?"
];

export const responder: Record<string, ResponderItem> = {
  ns: {
    text: "Newtown has a <strong>moderate safety profile</strong> per BOCSAR 2024. <br /><br />Residents describe King St as lively and generally safe late at night, though <strong>petty theft near the station</strong> is occasionally reported. <br /><br />Safety score: <strong>72/100</strong>.",
    source: "BOCSAR Crime Stats - Reddit /r/Sydney - 2024 Community Insights"
  },
  cg: {
    text: "Glebe scores <strong>92/100 on lifestyle</strong> among MVP suburbs. <br /><br />Residents consistently describe Glebe Point Road as neighbourhood-focused with independent cafes and markets.",
    source: "2024 Community Insights - Reddit /r/Sydney - City of Sydney ArcGIS"
  },
  rt: {
    text: "Redfern has the <strong>highest transport score (90/100)</strong>. <br /><br />Direct City Circle access puts the CBD under 5 minutes by train.",
    source: "City of Sydney ArcGIS - Transport NSW - 2024 Community Insights"
  },
  sp: {
    text: "Surry Hills scores <strong>85/100 on lifestyle</strong> and is frequently preferred by young professionals.<br /><br />Trade-off: affordability is <strong>55/100</strong> due to high inner-city rents.",
    source: "Reddit /r/Sydney - 2024 Community Insights - Domain rental data"
  },
  cmp: {
    text: "<strong>Newtown vs Glebe</strong><br /><br />Transport: Newtown <strong>85</strong> vs Glebe <strong>82</strong><br />Safety: Glebe <strong>78</strong> vs Newtown <strong>72</strong><br />Lifestyle: Glebe <strong>92</strong> vs Newtown <strong>88</strong><br />Affordability: Newtown <strong>70</strong> vs Glebe <strong>65</strong>",
    source: "BOCSAR - ArcGIS - Reddit /r/Sydney - Community Insights 2024"
  },
  def: {
    text: "Based on verified resident voices and civic data, I can help with transport, safety, lifestyle, and affordability across the 5 MVP suburbs.<br /><br />Try: <em>Is Glebe good for families?</em>",
    source: "13,500+ entries - BOCSAR - ArcGIS - Reddit /r/Sydney"
  }
};
