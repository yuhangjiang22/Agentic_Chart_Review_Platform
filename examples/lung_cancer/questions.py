"""Lung cancer molecular testing — domain configuration for the chart review platform.

Exposes the question list and tier metadata consumed by the platform's
benchmark runner. Add a sibling module
(e.g. examples/breast_cancer/questions.py) to add another use case; the
platform itself does not encode anything domain-specific.
"""

NAME = "Lung Cancer Molecular Testing"

TIER_NAMES = {
    0: "Eligibility",
    1: "Binary",
    2: "Categorical",
    3: "Detailed",
    4: "Composite",
}

# All 18 lung cancer molecular testing questions organized by tier.
# Each entry: (question_id, question_text, expected_answer, tier, category)
QUESTIONS = [
    # ── Tier 0: Eligibility ──────────────────────────────────────────────
    ("MT0a",
     "Does the patient have a confirmed lung cancer diagnosis?",
     "Documentation should include a pathologically confirmed lung cancer diagnosis with date of diagnosis.",
     0, "Eligibility"),
    ("MT0b",
     "What is the histologic subtype of the lung cancer? (adenocarcinoma, squamous cell carcinoma, large cell carcinoma, NSCLC-NOS, SCLC, other)",
     "Documentation should include pathology-confirmed histologic subtype. NSCLC subtypes (adenocarcinoma, squamous, large cell, NOS) are eligible for molecular testing per NCCN. SCLC is generally not indicated for standard molecular testing.",
     0, "Eligibility"),
    ("MT0c",
     "What is the stage of the lung cancer at diagnosis? (I, II, III, IIIA, IIIB, IV, limited, extensive)",
     "Documentation should include AJCC staging. Advanced/unresectable/metastatic NSCLC (stage IIIB/IV) has the strongest indication for comprehensive molecular testing. Resected NSCLC (stage IB-IIIA) should have at minimum EGFR and ALK testing for adjuvant therapy eligibility.",
     0, "Eligibility"),
    ("MT0d",
     "What is the patient's tobacco use history? (current smoker, former smoker, never smoker, unknown)",
     "Documentation should include tobacco use status. Never-smokers with NSCLC have higher likelihood of oncogenic driver alterations (EGFR, ALK, ROS1) and are more likely to benefit from targeted therapies.",
     0, "Eligibility"),

    # ── Tier 1: Binary ───────────────────────────────────────────────────
    ("MT1",
     "Was genomic testing performed?",
     "Documentation should indicate whether any genomic/molecular testing was ordered and performed, including any NGS panel, single-gene test, FISH, or PCR-based assay for lung cancer molecular alterations.",
     1, "Genomic Testing"),
    ("MT7",
     "Was PD-L1 testing (immunohistochemistry) performed?",
     "Documentation should indicate whether PD-L1 expression testing by IHC was performed. PD-L1 testing is a protein expression assay (not genomic) and is critical for immunotherapy treatment decisions in NSCLC. The assay used (22C3, 28-8, SP142, SP263) should ideally be documented.",
     1, "PD-L1 Testing"),

    # ── Tier 2: Categorical ──────────────────────────────────────────────
    ("MT2",
     "Was comprehensive genomic profiling (CGP) performed? If yes, which vendor or platform was used? (Tempus, Caris, Foundation Medicine, in-house institutional panel, other)",
     "Documentation should indicate whether comprehensive genomic profiling (broad NGS panel covering multiple genes) was performed, and identify the specific vendor or assay platform (e.g., Tempus xT, Caris MI Profile, FoundationOne CDx, institutional NGS panel).",
     2, "Genomic Testing"),
    ("MT3",
     "If comprehensive genomic profiling was NOT performed, was single-gene testing or a targeted lung panel performed? If yes, which specific genes were tested?",
     "If CGP was not performed, documentation should indicate whether individual gene tests or a limited lung panel was used. At minimum for advanced NSCLC, the following should be tested: EGFR (including exon 19 del, exon 21 L858R, exon 20 insertions), ALK (rearrangement), ROS1 (rearrangement), BRAF V600E, KRAS G12C, MET exon 14 skipping, RET (rearrangement), NTRK 1-3 (fusions), HER2 (exon 20 insertions). Testing methods may include PCR, FISH, or IHC.",
     2, "Genomic Testing"),
    ("MT4",
     "Was genomic profiling done on liquid biopsy (blood/ctDNA) or tumor tissue, or both?",
     "Documentation should specify the sample source for genomic testing: tumor tissue biopsy, liquid biopsy (blood-based ctDNA), or both. If tissue was insufficient or unavailable, liquid biopsy should be documented as alternative. If liquid biopsy was negative, reflex to tissue testing should be considered.",
     2, "Genomic Testing"),
    ("MT5",
     "Was genomic testing performed (ordered) before starting first-line therapy? Specify the type of first therapy initiated: radiation to brain, radiation to lung, chemotherapy, immunotherapy, chemotherapy with immunotherapy, surgery, or targeted therapy.",
     "Documentation should indicate whether genomic testing was ordered before or after the initiation of first-line systemic therapy or local therapy. The type of first therapy should be identifiable (surgery, radiation [brain vs lung], chemotherapy, immunotherapy, chemo-immunotherapy, or targeted therapy). Ideally, genomic testing should be ordered at the time of diagnosis before any treatment decision.",
     2, "Testing Timing"),
    ("MT6",
     "Were genomic testing results available before starting first-line therapy?",
     "Documentation should allow determination of whether genomic testing results were returned and available to the treating clinician before the first-line therapy was initiated. Compare the date of genomic test results with the date of first treatment. Delays in result availability may lead to empiric therapy initiation without molecular guidance.",
     2, "Testing Timing"),

    # ── Tier 3: Detailed Extraction ──────────────────────────────────────
    ("MT7a",
     "If PD-L1 testing was performed, what was the PD-L1 expression result? (TPS score: <1%, 1-49%, >=50%; or CPS score)",
     "Documentation should include the PD-L1 expression level reported as Tumor Proportion Score (TPS) percentage or Combined Positive Score (CPS). Key thresholds: TPS <1% (negative), TPS 1-49% (low positive), TPS >=50% (high positive). High PD-L1 (>=50%) may qualify for single-agent immunotherapy; low/negative may require combination chemo-immunotherapy.",
     3, "PD-L1 Testing"),
    ("MT8",
     "What were the results of the genomic testing? Report each actionable finding with the exact gene and exact variant identified.",
     "Documentation should include the specific genomic findings with exact gene and variant, e.g.: EGFR exon 19 deletion, EGFR L858R, EGFR exon 20 insertion, EGFR T790M, ALK fusion (with partner gene if available), ROS1 fusion, KRAS G12C, BRAF V600E, MET exon 14 skipping, MET amplification, RET fusion, NTRK fusion, HER2 exon 20 insertion, NRG1 fusion. If no actionable mutations found, this should be explicitly stated.",
     3, "Testing Results"),
    ("MT8a",
     "Were any actionable mutations identified that have an FDA-approved targeted therapy? If yes, which specific alteration(s)?",
     "Actionable alterations with FDA-approved targeted therapies include: EGFR classical mutations (osimertinib), EGFR exon 20 insertions (amivantamab+chemo), ALK fusions (alectinib, lorlatinib), ROS1 fusions (crizotinib, entrectinib), KRAS G12C (sotorasib, adagrasib), BRAF V600E (dabrafenib+trametinib), MET exon 14 skipping (capmatinib, tepotinib), RET fusions (selpercatinib), NTRK fusions (entrectinib, larotrectinib), HER2 exon 20 insertions (trastuzumab deruxtecan), NRG1 fusions (zenocutuzumab).",
     3, "Testing Results"),

    # ── Tier 4: Composite / Outcome ──────────────────────────────────────
    ("MT9",
     "For patients with actionable mutations, was the guideline-recommended targeted therapy initiated as first-line treatment?",
     "If an actionable mutation was identified, documentation should show that the corresponding FDA-approved targeted therapy was offered/initiated as first-line treatment per NCCN guidelines. If targeted therapy was NOT given despite an actionable mutation, the reason should be documented (e.g., patient preference, comorbidities, concurrent mutation, clinical trial enrollment).",
     4, "Treatment Alignment"),
    ("MT10",
     "What was the time from initial lung cancer diagnosis to initiation of first-line systemic therapy?",
     "Documentation should allow calculation of the interval (in days) between the date of initial lung cancer diagnosis and the date of first systemic therapy initiation. Prolonged time to treatment may be associated with diminished outcomes. If testing turnaround time contributed to delay, this should be identifiable.",
     4, "Treatment Alignment"),
    ("MT11",
     "What was the turnaround time for genomic testing (from test order/specimen collection to result availability)?",
     "Documentation should allow calculation of the interval (in days) between genomic test order or specimen collection date and the date results were available. This applies to both tissue-based and liquid biopsy testing. Commercial vendor turnaround times and institutional lab turnaround times should be distinguishable when possible.",
     4, "Testing Timing"),
    ("MT12",
     "If comprehensive genomic profiling was NOT performed, were at minimum EGFR, ALK, ROS1, BRAF, KRAS, and PD-L1 tested (the essential NSCLC biomarkers)?",
     "For patients who did not receive comprehensive NGS, documentation should confirm that at minimum the following were individually tested: EGFR mutations, ALK rearrangements, ROS1 rearrangements, BRAF V600E, KRAS G12C, and PD-L1 expression. Missing any of these essential biomarkers represents a testing gap per NCCN guidelines.",
     4, "Testing Completeness"),
]
