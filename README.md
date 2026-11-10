# Craigslist Owner Listing Finder

A local rental-discovery pipeline that identifies and ranks likely owner-managed, human-written Craigslist listings.

## Design principles

This project is intentionally built around a few simple principles:

- **Explainable by default** — ranking decisions should be traceable to visible signals rather than hidden scores.
- **Local-first and reviewable** — storage and reports stay on the user's machine so results can be inspected directly.
- **Privacy-conscious** — live scraped listings, contact details, addresses, and generated reports are excluded from Git.
- **Practical over overengineered** — the current rule-based model is designed to be useful and easy to refine before adding more complex machine-learning approaches.

## The Problem

Standard rental-search filters focus on structured criteria such as price, location, bedroom count, and posting date. Those filters are useful, but they do not reliably distinguish between:

* Independently managed rentals
* Listings written by individual owners
* Small-landlord properties
* Personal, non-templated advertisements
* Large property-management or syndicated listings

This project adds an explainable scoring and ranking layer to help surface listings that appear more likely to come from individual owners or small landlords.

## How It Works

```text
Craigslist Search Results
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

1. **Search Fetcher** collects listing URLs and basic metadata from configured Craigslist searches.
2. **Listing Fetcher** retrieves descriptions, posting dates, and other details from individual listings.
3. **Scoring Engine** evaluates each listing using weighted qualitative signals.
4. **Shortlist Generator** ranks and deduplicates the strongest candidates.
5. **HTML Report** creates a browsable local report for reviewing results.
6. **CSV Export** produces data for further analysis and scoring review.

## Scoring Model

The current model uses three weighted components:

* **Owner Signal** — indicators that a listing may be independently managed
* **Human Signal** — indicators of personal, non-templated writing
* **Fit Score** — alignment with selected price, bedroom, and property-type preferences

Examples of owner and human signals include:

* Direct contact language
* References to an owner living onsite
* Small-building, accessory dwelling unit, or family-home descriptions
* Practical rather than highly polished marketing language
* Absence of property-management websites or syndicated application links
* Personal instructions for arranging a viewing

The scoring system is intentionally explainable and rule-based. Each score includes supporting reasons so that the model can be reviewed and refined before introducing more complex machine-learning approaches.

## Technology

* Python
* SQLite
* Requests
* Beautiful Soup
* HTML and CSS
* Rule-based text classification
* CSV export
* Command-line workflows

## Project Structure

```text
craigslist-owner-listing-finder/
├── src/                 # Pipeline and application code
├── data/                # Local generated data; excluded from Git
├── requirements.txt     # Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

## Installation

Clone the repository and move into the project folder:

```powershell
git clone https://github.com/shotsubakiyama/craigslist-owner-listing-finder.git
cd craigslist-owner-listing-finder
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

## Usage

Run the complete pipeline:

```powershell
python src\main.py
```

By default, the pipeline:

* Initializes the SQLite database
* Fetches configured Craigslist search results
* Runs five listing-detail fetch passes
* Scores available listings
* Prints a shortlist
* Generates an HTML report
* Exports a CSV review file

Run a shorter test using listings already stored locally:

```powershell
python src\main.py --skip-search --listing-passes 1 --limit 10
```

View all available options:

```powershell
python src\main.py --help
```

Example options include:

```powershell
python src\main.py --listing-passes 3 --limit 20 --min-score 65
```


## Seattle Market Pulse (optional)

The HTML shortlist now includes **four compact rental market cards above the existing
listing tiles**: rent growth (Seattle metro vs. United States), rental vacancy,
time to lease, and rental concessions. Each card explicitly labels its geography,
data month, and source. The original rental shortlist and scoring are unchanged.

**The daily pipeline never downloads market data.** It reads
`data/market_pulse.json` (if present) and renders the latest cached
monthly observations. Missing data is labeled unavailable, never replaced with
made-up figures. The data cache is excluded from Git along with other local data.

To fetch the latest Zillow metro rent index and compute Seattle vs. U.S.
year-over-year rent growth, run this **separately**, ideally weekly:

```powershell
python src\update_market_pulse.py
```

The source is Zillow Research's public, seasonally adjusted monthly ZORI CSV.
A network failure preserves the last good cache. The script does not modify
listings or other Grey Cells data. The cache refresh does not run automatically
until you separately schedule it on your computer.

For the remaining three cards, use the monthly downloadable metro-level
datasets from [Apartment List](https://www.apartmentlist.com/research/category/data-rent-estimates).
Save the wide-format Seattle metro datasets as:

- `data/market_sources/vacancy.csv` — Apartment List Vacancy Index
- `data/market_sources/time_to_lease.csv` — Apartment List Time On Market
- `data/market_sources/concessions.csv` — Apartment List Concession Rates

Each CSV needs a `RegionName` or `location` column with a Seattle-Tacoma-Bellevue
metro row and month columns in `YYYY-MM` or `YYYY-MM-DD` format.
Vacancy and concessions may use either fractions (0.061) or percentage
points (6.1); time to lease is in days. If the downloaded format is different,
convert it to this format rather than guessing at column meanings.

Once the files are in place, refresh all available cards:

```powershell
python src\update_market_pulse.py --no-download
```

That command uses local CSVs only and preserves the previous Zillow values.
The regular updater refreshes Zillow and any Apartment List CSVs present.
Apartment List file downloads have **not yet been automated** because a stable
direct download endpoint has not been verified. To use the latest data, replace
the CSVs when new monthly releases are published.

Concessions here mean the **percentage of properties offering discounts worth
at least one month of rent**, not the percentage discount on monthly rent.
The Apartment List vacancy and concessions samples are more representative
of professionally managed rentals than Grey Cells' owner-managed target niche.

To run the offline tests:

```powershell
python -m unittest discover -s tests -v
```

### Data sources

- [Zillow ZORI](https://www.zillow.com/research/data/) — metro asking rents
- [Apartment List public data](https://www.apartmentlist.com/research/category/data-rent-estimates) — vacancy, leasing time, and concessions

## Generated Files

The pipeline writes generated files to the local `data` directory, including:

* SQLite databases
* HTML shortlist reports
* CSV review exports

These files are excluded from Git because they may contain live listing data, addresses, descriptions, and contact information.

## Data Privacy

The repository does not include live databases, scraped listing content, generated reports, or personal contact information.

The `data` directory is preserved with a `.gitkeep` file, while its generated contents remain excluded through `.gitignore`.

## Limitations

* Craigslist page structure may change and require parser updates.
* The scoring model uses heuristics and does not prove that a listing is owner-managed.
* Certain phrases may produce false positives or false negatives.
* The project currently runs locally rather than as a hosted application.
* Search configuration is currently stored in SQLite and initialized with a starter Seattle-area search.

## Status

This is an active prototype focused on:

* Improving listing coverage
* Refining owner and human-writing signals
* Reducing duplicate listings
* Making search parameters easier to configure
* Improving reporting and review workflows

## License

This project is available under the MIT License.
