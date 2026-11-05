# DSE code review for IDE agents

Open [DSE_Code_Review.md](DSE_Code_Review.md) for the complete review. Code tested after the 4 November 2026 commit (`646867b`).

| Start here | What you will find |
| --- | --- |
| [Codebase guide](DSE_Code_Review.md#understand-the-codebase) | Architecture, data flow and module responsibilities. |
| [Browser walkthrough](DSE_Code_Review.md#guided-browser-walkthrough) | 16 screenshots with explanations of the UI and the confirmed defects. |
| [Findings and repair guidance](DSE_Code_Review.md#findings-and-repair-guidance) | Numbered backend findings and frontend defects, with evidence and suggested repairs. |
| [Reproduction and evidence](DSE_Code_Review.md#reproduction-and-evidence) | Test commands and links to raw results. |
| [Source references](DSE_Code_Review.md#source-references) | Project-relative paths and line numbers. |

Keep this folder together when moving it into a workspace. The report references 16 browser JPEGs in `images/screenshots/` and six explanatory PNGs in `images/diagrams/` using relative paths. Test logs, JSON, XML and exports are in `raw/`. The two audit scripts are preserved from the review. The report describes the checkout layout expected by `live_checks.py`.

For an IDE agent, a starting prompt is: “Read the review and inspect the relevant evidence and source before proposing changes. Report which findings reproduce on my checkout.”
