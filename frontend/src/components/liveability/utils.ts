import { Suburb, Weights } from "./types";

export function scoreSuburb(suburb: Suburb, weights: Weights) {
  const total =
    weights.transport +
    weights.safety +
    weights.lifestyle +
    weights.afford +
    weights.proximity ||
    1;
  return Math.round(
    (suburb.scoreBase.transport * weights.transport +
      suburb.scoreBase.safety * weights.safety +
      suburb.scoreBase.lifestyle * weights.lifestyle +
      suburb.scoreBase.afford * weights.afford +
      (suburb.scoreBase.proximity ?? 50) * weights.proximity) /
      total
  );
}
