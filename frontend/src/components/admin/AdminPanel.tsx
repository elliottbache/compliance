import { useState } from "react";
import type { AdminSection } from "../../types";
import { SitesSection } from "./SitesSection";

type AdminSectionConfig = {
  key: AdminSection;
  label: string;
  description: string;
};

const ADMIN_SECTIONS: AdminSectionConfig[] = [
  {
    key: "sites",
    label: "Sites",
    description: "Manage inspected locations.",
  },
  {
    key: "clients",
    label: "Clients",
    description: "Manage client companies.",
  },
  {
    key: "certifiers",
    label: "Certifiers",
    description: "Manage inspection/certification bodies.",
  },
  {
    key: "regulations",
    label: "Regulations",
    description: "Manage compliance frameworks.",
  },
  {
    key: "rules",
    label: "Rules",
    description: "Manage regulation rules.",
  },
  {
    key: "certifications",
    label: "Certifications",
    description: "Manage inspection events.",
  },
  {
    key: "findings",
    label: "Findings",
    description: "Manage inspection findings.",
  },
  {
    key: "attachments",
    label: "Attachments",
    description: "Manage evidence metadata.",
  },
];

export function AdminPanel() {
  const [selectedSection, setSelectedSection] =
    useState<AdminSection>("sites");

  const activeSection =
    ADMIN_SECTIONS.find((section) => section.key === selectedSection) ??
    ADMIN_SECTIONS[0];

  return (
    <section className="admin-panel">
      <div className="admin-tabs" aria-label="Admin sections">
        {ADMIN_SECTIONS.map((section) => (
          <button
            className={
              section.key === selectedSection
                ? "admin-tab admin-tab-active"
                : "admin-tab"
            }
            key={section.key}
            type="button"
            onClick={() => setSelectedSection(section.key)}
          >
            {section.label}
          </button>
        ))}
      </div>

      {selectedSection === "sites" ? (
      <SitesSection />
      ) : (
      <div className="admin-section-placeholder">
          <div>
          <p className="eyebrow">Admin section</p>
          <h3>{activeSection.label}</h3>
          <p>{activeSection.description}</p>
          </div>

          <div className="empty-state">
          {activeSection.label} list/create/archive/restore UI will go here.
          </div>
      </div>
      )}
    </section>
  );
}