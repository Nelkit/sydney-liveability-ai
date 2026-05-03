import { ImportanceOption, Suburb, WeightKey } from "./types";

export const importanceOptions: ImportanceOption[] = [
  { key: "1",  label: "1",  value: 5  },
  { key: "2",  label: "2",  value: 16 },
  { key: "3",  label: "3",  value: 27 },
  { key: "4",  label: "4",  value: 38 },
  { key: "5",  label: "5",  value: 50 },
  { key: "6",  label: "6",  value: 61 },
  { key: "7",  label: "7",  value: 72 },
  { key: "8",  label: "8",  value: 80 },
  { key: "9",  label: "9",  value: 90 },
  { key: "10", label: "10", value: 100 },
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
  },
  {
    key: "proximity",
    label: "CBD Proximity",
    prompt: "How important is being close to the city centre?"
  }
];

export const suburbs: Suburb[] = [
  {
    id: "glebe",
    name: "Glebe",
    color: "#10b981",
    scoreBase: { transport: 82, safety: 78, lifestyle: 92, afford: 65, proximity: 90 },
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
    scoreBase: { transport: 85, safety: 72, lifestyle: 88, afford: 70, proximity: 78 },
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
    scoreBase: { transport: 90, safety: 60, lifestyle: 70, afford: 85, proximity: 96 },
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
    scoreBase: { transport: 80, safety: 68, lifestyle: 85, afford: 55, proximity: 99 },
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
    scoreBase: { transport: 95, safety: 55, lifestyle: 72, afford: 45, proximity: 98 },
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
