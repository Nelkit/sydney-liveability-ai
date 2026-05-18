---
name: latex-report
description: >
  Add content to the AT2B LaTeX report for Sydney Liveability Explorer.
  Trigger: When someone wants to add, write, update, or edit content in the report,
  mentions a section name, says "add to the report", "write section X", "update the report",
  or references AT2B_report.tex.
license: Apache-2.0
metadata:
  author: sydney-liveability-ai
  version: "1.0"
allowed-tools: Read, Edit, Write, Bash
---

## When to Use

Load this skill BEFORE writing any LaTeX when:
- User says "add to the report", "write section X", "update the report", "draft X for the report"
- User mentions any section name from the structure below
- User asks about AT2B_report.tex or the PDF report

## Report Location

```
reports/AT2B_report.tex     ← the only file to edit
reports/AT2B_report.pdf     ← generated output (never edit manually)
reports/PROGRESS_LOG.md     ← internal drafting log (NOT in the PDF)
```

## Preamble — DO NOT MODIFY

The preamble is already configured with:
- **Font**: Helvetica (`helvet`) — sans-serif across the entire document
- **Primary colour**: `#039BE5` (blue) — used for section headings and title accent
- **Body colour**: `#404040` (dark gray) — subsections and body text
- **Compiler**: `tectonic` — do NOT switch to pdflatex or change font packages

Never touch the preamble when adding content. Only edit inside existing `\section` bodies.

## Report Structure (embed — do NOT read the .tex file each time)

The report has the following sections in order. Use these exact LaTeX section commands.

```
\section{Executive Summary}                          (1)   ~0.5 page — write last
\section{Project Objectives and Scope}               (2)
\section{Project Phases and Team Contributions}      (3)
  \subsection*{Phase Breakdown Table}                      — longtable with 5 phases

\section{Data Sources}                               (4)
  \subsection{Primary Data Sources}                        — 6 sources: Community Insights PDF,
                                                             Reddit/Arc Shift, BOCSAR CSV,
                                                             TfNSW GTFS, OSM/Overpass, CoS ArcGIS
  \subsection{Data Limitations and Ethical Considerations}

\section{NLP Methods and Techniques}                 (5)
  \subsection{Text Preprocessing}                          — spaCy: tokenisation, lemmatisation,
                                                             NER for suburb extraction; LangChain
                                                             chunking for RAG ingestion
  \subsection{Considered Approaches: Traditional NLP}      — CRITICAL REVIEW ONLY, not implemented;
                                                             cite literature (VADER, LDA, TF-IDF)
  \subsection{Implemented Approaches: Modern NLP}
    \subsubsection{Reddit Data Collection via Arc Shift}   — replaced PRAW; 20,237 posts, 563 suburbs
    \subsubsection{Aspect-Level Sentiment Analysis (DistilRoBERTa)}  — 8 dimensions, emotion profiling
    \subsubsection{Sentence Embeddings (all-MiniLM-L6-v2) and ChromaDB}  — chunking, upsert, metadata
    \subsubsection{Multi-Agent Pipeline (CrewAI)}          — pipeline crew + query crew; agents, tools
    \subsubsection{Retrieval-Augmented Generation (RAG + LLM)}  — LangChain + ChromaDB + Codex Sonnet
  \subsection{Justification: Why Modern Over Traditional}  — DistilRoBERTa > VADER, embeddings > TF-IDF,
                                                             RAG > keyword search, CrewAI orchestration;
                                                             cite Lewis 2020, Reimers 2019, Hutto 2014

\section{Findings and Evaluation}                    (6)
  \subsection{NLP Pipeline Results}                        — aspect scores, emotion profiles,
                                                             transport scores, POI density, crime trends
  \subsection{NLP Model Performance Metrics}               — DistilRoBERTa metrics, RAG retrieval quality,
                                                             sample query-response pairs with citations
  \subsection{User-Facing Application Quality}             — dashboard, radar, emotion chart, chat UI
  \subsection{Temporal Trends}                             — time-based sentiment patterns per suburb

\section{Outcomes and Value Added}                   (7)
\section{Recommendations and Next Steps}             (8)
\section{Conclusion}                                 (9)
\section{References}                                 (10)  APA 7th edition

\appendix
\section{Appendix A: System Architecture Diagram}         — full pipeline diagram
\section{Appendix B: Dashboard Screenshots}               — radar, emotion, map, chat
\section{Appendix C: Sample Code}                         — ingest_sentiment.py, CrewAI agents,
                                                             RAG chain, FastAPI endpoints
\section{Appendix D: Evaluation Tables and Charts}        — suburb scores, emotion distributions,
                                                             transport scores, POI density
\section{Appendix E: Traditional vs. Modern NLP Comparison Table}  — 7-row booktabs table
```

## Workflow (MANDATORY — follow every step)

### Step 1 — Identify target section

If the user did NOT specify a section:
- List the sections above (short form, numbered)
- Ask: "In which section do you want to add this content?"
- STOP and wait for the answer before writing anything

If the user specified a section:
- Confirm which section you understood before editing

### Step 2 — Write the LaTeX content

Rules:
- Replace placeholder text (lines starting with a bare instruction like "Write a concise...") with real content
- Use `\textbf{}`, `\emph{}`, `itemize`, `enumerate`, `longtable` as appropriate
- Escape special characters: `&` → `\&`, `%` → `\%`, `_` → `\_`, `#` → `\#`
- For code blocks use `\begin{verbatim}...\end{verbatim}`
- Renaming, removing, or adding sections is allowed — just confirm with the user before doing it
- When adding a new section, use the correct command for its level: `\section{}`, `\subsection{}`, or `\subsubsection{}`
- When removing a section, also remove it from the structure list at the top of this skill so it stays in sync

### Step 3 — Update the Progress Log

After every content addition, append a row to `reports/PROGRESS_LOG.md` using this format:

```markdown
| YYYY-MM-DD | @GitHubUsername | Section Name | Draft | One-line summary of what was added. | Next action or Pending. |
```

Use today's date. For the Author column, use the GitHub username of the person who requested the change (e.g. `@Nelkit`). Status options: `Draft`, `In Review`, `Done`.
Do NOT touch the `.tex` file for this — the log lives only in the MD.

### Step 4 — Ask about PDF compilation

After every edit, always ask:

> "Do you want me to compile the report to PDF now?"

If YES: run the compile command below.
If NO: confirm the edit is saved and move on.

## Compile to PDF

```bash
cd reports && tectonic AT2B_report.tex
```

Tectonic handles multiple passes automatically — no need to run twice.

### If tectonic is not found

```bash
brew install tectonic
```

Then retry the compile command. Do NOT use pdflatex or any other tool.

## LaTeX Patterns for This Report

### Table (longtable — matches existing style)
```latex
\begin{longtable}{p{0.20\textwidth}p{0.50\textwidth}p{0.26\textwidth}}
\toprule
\textbf{Col A} & \textbf{Col B} & \textbf{Col C} \\
\midrule
\endhead
Row content & here & and here \\
\bottomrule
\end{longtable}
```

### Figure
```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.8\textwidth]{figures/filename.png}
  \caption{Caption text.}
  \label{fig:label}
\end{figure}
```

### Bullet list
```latex
\begin{itemize}
  \item First item
  \item Second item
\end{itemize}
```

### APA Reference entry (Section 10)
```latex
Author, A.\ A., \& Author, B.\ B.\ (Year). \emph{Title of work}. Publisher. \url{https://doi.org/...}
```

## What NOT to do

- Never read AT2B_report.tex to recall the structure — it is embedded above
- Never create a new .tex file — there is only one report file
- Never modify the preamble (fonts, colours, packages)
- Never rename or remove a section without confirming with the user first
- Never compile without asking first
- Never skip the Progress Log update
- Never use em dashes (—) in prose. This is formal academic writing — use commas, colons, or rewrite the sentence instead. Em dashes are informal and not appropriate for this report.
