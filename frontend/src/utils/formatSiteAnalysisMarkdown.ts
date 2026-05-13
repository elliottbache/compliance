import type { EvidenceRef, SiteAnalysis, SiteAnalysisListItem } from "../types";

const ANALYSIS_SECTIONS = [
  "recurring_issues",
  "missing_information",
  "needs_human_review",
  "suggestions",
] as const;

type AnalysisSectionName = (typeof ANALYSIS_SECTIONS)[number];

export function buildSiteAnalysisMarkdown(siteAnalysis: SiteAnalysis): string {
  const siteId =
    typeof siteAnalysis.site_id === "number" ? siteAnalysis.site_id : "Unknown";

  const generatedAt = new Date().toISOString();

  const executiveSummary =
    typeof siteAnalysis.executive_summary === "string" &&
    siteAnalysis.executive_summary.trim()
      ? siteAnalysis.executive_summary
      : "None.";

  let outputText = `# Site Analysis

## Metadata

**Site ID:** ${siteId}

**Generated at:** ${generatedAt}

**Note:** Everything in this report is AI-generated and is meant for human-review-only. These are not official compliance decisions.

## Executive summary

${executiveSummary}`;

  for (const attrName of ANALYSIS_SECTIONS) {
    outputText += `\n\n## ${beautifyAttrName(attrName)}`;
    outputText += renderSiteAnalysisAttribute(siteAnalysis, attrName);
  }

  return `${outputText.trimEnd()}\n`;
}

function renderSiteAnalysisAttribute(
  siteAnalysis: SiteAnalysis,
  attrName: AnalysisSectionName,
): string {
  const attr = siteAnalysis[attrName];

  if (!Array.isArray(attr) || attr.length === 0) {
    return "\n\nNone.";
  }

  let outputText = "";

  for (const attrElement of attr) {
    if (!isSiteAnalysisListItem(attrElement)) {
      continue;
    }

    outputText += `\n\n### ${attrElement.item}`;

    for (const [subAttr, value] of Object.entries(attrElement)) {
      if (subAttr === "item" || subAttr === "evidence") {
        continue;
      }

      if (value === null || value === undefined || value === "") {
        continue;
      }

      outputText += `\n\n#### ${beautifyAttrName(subAttr)}\n\n${formatMarkdownValue(
        value,
      )}`;
    }

    for (const evidence of attrElement.evidence) {
      if (isEvidenceRef(evidence)) {
        outputText += formatEvidenceItemToMarkdown(evidence);
      }
    }
  }

  return outputText || "\n\nNone.";
}

function beautifyAttrName(attrName: string): string {
  return attrName.charAt(0).toUpperCase() + attrName.slice(1).replaceAll("_", " ");
}

function formatEvidenceItemToMarkdown(
  evidence: EvidenceRef,
  headerLevel = "####",
): string {
  let outputText = `\n\n${headerLevel} Evidence

- Certification ID: ${evidence.cert_id}
- Regulation title: ${evidence.reg_title}`;

  if (evidence.inspection_date) {
    outputText += `\n- Inspection date: ${evidence.inspection_date}`;
  }

  if (evidence.finding_id !== null && evidence.finding_id !== undefined) {
    outputText += `\n- Finding ID: ${evidence.finding_id}`;
  }

  if (evidence.rule_index) {
    outputText += `\n- Rule index: ${evidence.rule_index}`;
  }

  outputText += `\n- Description: ${evidence.support_text}`;

  return outputText;
}

function formatMarkdownValue(value: unknown): string {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "None.";
    }

    return value.map((item) => `- ${formatInlineValue(item)}`).join("\n");
  }

  if (isRecord(value)) {
    return `\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
  }

  return String(value);
}

function formatInlineValue(value: unknown): string {
  if (isRecord(value) || Array.isArray(value)) {
    return JSON.stringify(value);
  }

  return String(value);
}

function isSiteAnalysisListItem(value: unknown): value is SiteAnalysisListItem {
  return (
    isRecord(value) &&
    typeof value.item === "string" &&
    Array.isArray(value.evidence)
  );
}

function isEvidenceRef(value: unknown): value is EvidenceRef {
  return (
    isRecord(value) &&
    typeof value.cert_id === "number" &&
    typeof value.reg_title === "string" &&
    typeof value.support_text === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}