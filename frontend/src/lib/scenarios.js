const SCENARIO_PRESENTATION = {
  "REC-ACCEPT": {
    label: "Baseline Recommendation",
    changed: "The submitted recommendation enters the standard review with current source data.",
    protects: "Confirm that a reasonable recommendation is still safe before committing spend.",
  },
  "REC-MODIFY": {
    label: "Possible Excess Stock",
    changed: "Current inventory and demand may make the recommended quantity larger than needed.",
    protects: "Avoid excess inventory while preserving the required safety stock.",
  },
  "REC-REJECT": {
    label: "High Existing Coverage",
    changed: "On-hand and incoming inventory already provide unusually strong demand coverage.",
    protects: "Avoid an unnecessary purchase order and prevent avoidable spend.",
  },
  "REC-INVESTIGATE": {
    label: "Aged Demand Forecast",
    changed: "The demand forecast is outside the purchasing policy's freshness limit.",
    protects: "Never authorize spending from incomplete or stale critical evidence.",
  },
  "REC-VALIDATE": {
    label: "Purchase-Order Persistence",
    changed: "The purchasing simulator can persist a different quantity than the action requested.",
    protects: "Read back the recorded order and detect a mismatch before reporting success.",
  },
  "REC-REVIEW": {
    label: "Spending Authority Boundary",
    changed: "The proposed purchase can be feasible while exceeding automatic spending authority.",
    protects: "Keep higher-risk spend under the buyer's explicit control.",
  },
  "SUPPLIER-SHORTFALL": {
    label: "Supplier Availability Changed",
    changed:
      "Confirmed inbound supply covers only part of the requirement and availability is limited.",
    protects:
      "Recalculate from confirmed supply instead of assuming the original quantity is available.",
  },
  "DEMAND-CHANGE": {
    label: "Customer Demand Increased",
    changed: "The current demand forecast is higher than the demand behind the recommendation.",
    protects: "Respond to current demand without accepting an outdated purchasing quantity.",
  },
  "HARD-CONSTRAINT": {
    label: "Tight Purchasing Budget",
    changed: "Available purchasing budget is lower than the cost of the required replenishment.",
    protects: "Respect the hard budget constraint rather than creating an unsafe purchase.",
  },
};

export const SCENARIO_GROUPS = [
  {
    key: "recommendation_review",
    label: "Recommendation Review",
    description: "Core decision and safety behavior",
    includes: (item) => item.scenario_type === "recommendation_review",
  },
  {
    key: "additional_probes",
    label: "Additional Probes",
    description: "Supplier, demand, and constraint changes",
    includes: (item) => item.scenario_type !== "recommendation_review",
  },
];

export function getScenarioPresentation(item) {
  return (
    SCENARIO_PRESENTATION[item.code] ?? {
      label: "Purchasing Condition",
      changed: item.title,
      protects: "Use current evidence and policy before taking purchasing action.",
    }
  );
}
