const ISSUE_LABELS: Record<string, string> = {
  has_accident: "accidente/siniestro",
  has_rust: "óxido/corrosión",
  has_repaint: "repintado",
  has_engine_issue: "avería de motor",
  has_mechanical_issue: "avería mecánica",
  has_gearbox_issue: "avería de caja o embrague",
  has_paper_issue: "problema de documentación",
  has_fire_or_flood_damage: "daño por incendio/inundación",
  not_running: "no arranca o no circula",
  export_or_parts: "para piezas/exportación",
};

export function conditionFindings(
  textSignals: Record<string, unknown> | null,
  snapshotSignals: Record<string, unknown> | null,
  photoSignals: Record<string, unknown> | null,
): { label: string; source: string }[] {
  const findings: { label: string; source: string }[] = [];
  const sources = [
    { signals: textSignals, source: "Texto del anuncio (título, descripción y comentario del vendedor)" },
    { signals: snapshotSignals, source: "Texto capturado del anuncio" },
  ];
  for (const { signals, source } of sources) {
    if (!signals) continue;
    for (const [key, label] of Object.entries(ISSUE_LABELS)) {
      if (signals[key] === true && key !== "has_repaint" && !findings.some((finding) => finding.label === label)) {
        findings.push({ label, source });
      }
    }
  }
  if (photoSignals?.has_visible_damage === true) {
    const types = (photoSignals.damage_types as string[] | undefined) ?? [];
    for (const type of types.filter((value) => !["roces", "abolladura", "repintado"].includes(value))) {
      findings.push({ label: type, source: "Análisis visual CV" });
    }
  }
  return findings;
}

export function cosmeticFindings(photoSignals: Record<string, unknown> | null): string[] {
  return (photoSignals?.cosmetic_defects as string[] | undefined) ?? [];
}

export function hasCosmeticText(signals: Record<string, unknown> | null): boolean {
  return signals?.has_cosmetic_damage === true || signals?.has_repaint === true;
}
