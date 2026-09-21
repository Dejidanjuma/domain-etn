export function lifecycleOf(profile) {
  if (!profile) return { state: "unknown", label: "Unknown", className: "checking" };
  const life = profile.lifecycle;
  if (life && life.state) {
    return {
      state: life.state,
      label: life.label || labelFor(life.state),
      className: classFor(life.state),
      in_grace: Boolean(life.in_grace),
      expiring_soon: Boolean(life.expiring_soon),
      renewable: Boolean(life.renewable),
    };
  }
  if (profile.available) return { state: "available", label: "Available", className: "available", renewable: false };
  if (profile.in_grace) return { state: "grace", label: "Grace period", className: "grace", renewable: true };
  return { state: "active", label: "Registered", className: "registered", renewable: !profile.available };
}

function labelFor(state) {
  if (state === "available") return "Available";
  if (state === "grace") return "Grace period";
  if (state === "expiring_soon") return "Expiring soon";
  if (state === "active") return "Registered";
  return "Registered";
}

function classFor(state) {
  if (state === "available") return "available";
  if (state === "grace") return "grace";
  if (state === "expiring_soon") return "expiring";
  return "registered";
}

export function historyRows(profile) {
  const intel = (profile && profile.intelligence) || {};
  const rows = intel.history || [];
  return Array.isArray(rows) ? rows : [];
}

export function relatedAddresses(profile) {
  const intel = (profile && profile.intelligence) || {};
  const rows = intel.related_addresses || [];
  return Array.isArray(rows) ? rows : [];
}
