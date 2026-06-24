import { claudeImporter } from "../importers/claude.ts";
import { codexImporter } from "../importers/codex.ts";
import { piOpenClawImporter } from "../importers/pi-openclaw.ts";
import { basename, expandMemoryCitationEvents } from "./jsonl.ts";
import type { JsonlRecord, SessionDocument, SessionImporter } from "./types.ts";

const importers: SessionImporter[] = [codexImporter, piOpenClawImporter, claudeImporter];

export function parseSessionDocument(records: JsonlRecord[], sourcePath?: string): SessionDocument {
  const importer = importers.find((candidate) => candidate.detect(records));
  if (!importer) {
    return {
      format: "unknown",
      title: basename(sourcePath) ?? "session",
      sourcePath,
      meta: {},
      events: records.map((record) => ({
        id: `raw-${record.line}`,
        kind: "event",
        title: `raw line ${record.line}`,
        text: JSON.stringify(record.value, null, 2),
        raw: record.value,
      })),
      warnings: ["unknown session format; rendered raw JSONL rows"],
    };
  }
  // Memory-citation expansion is format-agnostic post-processing, applied once
  // here rather than repeated at the end of every importer.
  const doc = importer.parse(records, sourcePath);
  return { ...doc, events: expandMemoryCitationEvents(doc.events) };
}
