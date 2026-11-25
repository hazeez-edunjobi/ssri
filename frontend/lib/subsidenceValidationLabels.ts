export type SubsidenceValidationOutcome =
  | "unavailable"
  | "insufficient"
  | "success"
  | "failed";

export function outcomeLabel(outcome: SubsidenceValidationOutcome): string {
  switch (outcome) {
    case "unavailable":
      return "Ground truth unavailable";
    case "insufficient":
      return "Insufficient for defensible metrics";
    case "success":
      return "Software metrics computed (still NOT_VALIDATED)";
    case "failed":
      return "Validation request failed";
    default:
      return outcome;
  }
}
