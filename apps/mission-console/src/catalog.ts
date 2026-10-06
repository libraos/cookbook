// The missions this console can run. Each entry names a pack, one of its
// missions, and the lead agent that owns it on the kernel. Until LibraOS serves
// mission templates from packs (libraos/libraos#1660), the catalog lives here
// and only the marketing team's built-in lead can run.
export type CatalogMission = {
  id: string;
  pack: string;
  mission: string;
  /** Agent id that receives the job: POST /agents/v1/{lead}/jobs */
  lead: string;
  leadName: string;
  teamName: string;
  headline: string;
  description: string;
  example: string;
  reportFilename: string;
};

export const catalog: CatalogMission[] = [
  {
    id: "marketing-team/autonomous-marketing-department",
    pack: "marketing-team",
    mission: "autonomous-marketing-department",
    lead: "head-of-marketing",
    leadName: "Head of Marketing",
    teamName: "Digital marketing department",
    headline: "What should your marketing team accomplish?",
    description: "The Head of Marketing will choose the team, break down the work, run it in parallel, and bring back one finished deliverable.",
    example: "Create a 14-day developer marketing campaign for LibraOS. Target AI developers and aim for 500 qualified signups. Produce the strategy, channel plan, launch examples, developer messaging, KPI model, and final report. Ask me to approve the positioning before it is used in launch drafts. Do not publish anything.",
    reportFilename: "libraos-marketing-report",
  },
];

export const findMission = (id: string | null | undefined) => catalog.find((entry) => entry.id === id);
