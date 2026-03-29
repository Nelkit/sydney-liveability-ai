import { responder } from "./data";
import { Suburb, Weights } from "./types";

export function scoreSuburb(suburb: Suburb, weights: Weights) {
  const total = weights.transport + weights.safety + weights.lifestyle + weights.afford || 1;
  return Math.round(
    (suburb.scoreBase.transport * weights.transport +
      suburb.scoreBase.safety * weights.safety +
      suburb.scoreBase.lifestyle * weights.lifestyle +
      suburb.scoreBase.afford * weights.afford) /
      total
  );
}

export function getResponse(input: string) {
  const normalized = input.toLowerCase();
  if ((normalized.includes("safe") || normalized.includes("crime")) && normalized.includes("newtown")) return responder.ns;
  if (normalized.includes("cafe") || normalized.includes("coffee") || normalized.includes("glebe")) return responder.cg;
  if (normalized.includes("transport") || normalized.includes("train") || normalized.includes("redfern")) return responder.rt;
  if (normalized.includes("surry") || normalized.includes("professional")) return responder.sp;
  if (normalized.includes("compare") || normalized.includes(" vs ") || normalized.includes("versus")) return responder.cmp;
  return responder.def;
}
