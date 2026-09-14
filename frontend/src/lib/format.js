const LABEL_OVERRIDES = {
  get_budget: "Available budget",
  get_demand_forecast: "Demand forecast",
  get_inventory: "Inventory position",
  get_open_purchase_orders: "Open purchase orders",
  get_storage_capacity: "Storage capacity",
  get_supplier_terms: "Supplier terms",
};

export function formatCurrency(minor, currency = "INR") {
  if (minor === null || minor === undefined) return "—";

  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

export function formatDate(value, includeTime = false) {
  if (!value) return "—";

  const dateValue = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;

  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(dateValue));
}

export function formatLabel(value) {
  if (!value) return "—";
  if (LABEL_OVERRIDES[value]) return LABEL_OVERRIDES[value];

  const words = value.replaceAll("_", " ").replaceAll(":", ": ");
  return `${words.charAt(0).toUpperCase()}${words.slice(1)}`;
}

export function formatQuantity(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat().format(value);
}

export function statusTone(status) {
  if (["completed", "validated", "auto_authorized", "human_approved", "ready"].includes(status)) {
    return "positive";
  }
  if (["awaiting_review", "human_review", "acknowledged", "running"].includes(status)) {
    return "attention";
  }
  if (["failed", "blocked", "escalated", "rejected"].includes(status)) {
    return "negative";
  }
  return "neutral";
}

export function evidenceSummary(toolName, payload) {
  switch (toolName) {
    case "get_inventory":
      return {
        value: `${formatQuantity(payload.on_hand_quantity)} on hand`,
        detail: `${formatQuantity(payload.reserved_quantity)} reserved · ${formatQuantity(payload.damaged_quantity)} damaged`,
      };
    case "get_demand_forecast": {
      const points = payload.points ?? [];
      const total = points.reduce((sum, point) => sum + point.quantity, 0);
      return {
        value: `${formatQuantity(total)} units forecast`,
        detail: `${formatQuantity(points.length)} daily observations`,
      };
    }
    case "get_open_purchase_orders": {
      const orders = payload.orders ?? [];
      const total = orders.reduce((sum, order) => sum + order.quantity, 0);
      return {
        value: `${formatQuantity(total)} units incoming`,
        detail: `${formatQuantity(orders.length)} open purchase ${orders.length === 1 ? "order" : "orders"}`,
      };
    }
    case "get_supplier_terms":
      return {
        value: payload.supplier_name,
        detail: `${formatCurrency(payload.unit_cost_minor, payload.currency)} per unit · ${formatQuantity(payload.available_quantity)} available`,
      };
    case "get_budget":
      return {
        value: formatCurrency(payload.available_minor, payload.currency),
        detail: "Available purchasing budget",
      };
    case "get_storage_capacity":
      return {
        value: `${formatQuantity(payload.available_quantity)} units`,
        detail: "Available storage capacity",
      };
    default:
      return { value: "Evidence received", detail: "" };
  }
}
