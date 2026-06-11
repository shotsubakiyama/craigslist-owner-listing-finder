# Grey Cells

Grey Cells is a local rental-discovery pipeline designed to surface promising owner-managed and distinctive rental listings that conventional search filters may miss.

## The Problem

Most rental-search platforms focus on structured criteria such as price, location, bedroom count, and posting date. Those filters are useful, but they do not reliably identify listings that appear to be:

* Independently managed by an owner
* Written in a personal rather than templated style
* Less heavily marketed or syndicated
* Strong qualitative matches for a renter's preferences

Grey Cells adds an explainable scoring and ranking layer to help identify those listings.

## How It Works

```text
Search Results
      |
      v
Search Fetcher
      |
      v
Listing Fetcher
      |
      v
SQLite Storage
      |
      v
Scoring Engine
      |
      v
Shortlist and HTML Report
```

The pipeline consists of several stages:

1. **Search Fetcher** collects listing URLs and basic metadata.
2. **Listing Fetcher** retrieves additional details from individual listings.
3. **Scoring Engine** evaluates each listing using weighted qualitative signals.
4. **Shortlist Generator** ranks the strongest candidates.
5. **HTML Report** creates a browsable local report for reviewing results.

## Scoring Model

The current scoring model uses three components:

* **Owner Signal** — indicators that a listing may be independently managed
* **Human Signal** — indicators of personal, non-templated writing
* **Fit Score** — alignment with selected price, bedroom, and property-type preferences

The model is intentionally explainable and rule-based. This makes individual scores easier to review and refine before introducing more complex machine-learning approaches.

## Technology

* Python
* SQLite
* HTML and CSS
* Rule-based text scoring
* CSV export
* Local command-line workflows

## Project Structure

```text
grey-cells/
├── src/                 # Pipeline and application code
├── data/                # Local generated data; excluded from Git
├── requirements.txt     # Python dependencies
├── .gitignore
└── README.md
```

## Data Privacy

Live databases, listing exports, and generated reports are intentionally excluded from the repository. The public version will use synthetic or redacted sample data where examples are needed.

## Status

Grey Cells is an active prototype currently designed to run locally. Current development is focused on improving listing coverage, scoring accuracy, configuration, and reporting.
