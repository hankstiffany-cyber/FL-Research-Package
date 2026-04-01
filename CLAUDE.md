# CLAUDE.md - FL Research Package

## Project Overview

This is the **Forgotten Languages (FL) Research Package** - a comprehensive research and analysis platform for exploring the Forgotten Languages database from `forgottenlanguages-full.forgottenlanguages.org`. The project extracts, analyzes, and visualizes data from 10,000+ articles published from September 2009 to December 2025.

## Tech Stack

- **Python 3** - Core language
- **Streamlit** - Web application framework
- **Pandas** - Data manipulation
- **Plotly** - Interactive visualizations
- **SQLite3** - Database storage
- **Beautiful Soup** - HTML parsing (extraction)
- **Sentence Transformers** - Semantic embeddings (optional AI features)

## Project Structure

```
FL_Research_Package/
├── data/                    # Core data files (~35 MB)
│   ├── fl_articles_raw.json        # 10,073 articles metadata
│   ├── fl_excerpts_raw.csv         # 34,231 English text excerpts
│   ├── fl_coordinates_*.csv        # Decoded coordinates
│   ├── fl_keyword_index.json       # Keyword → URL mapping
│   └── fl_enhanced.db              # SQLite database
├── analysis/                # Research reports (markdown)
├── tools/
│   └── fl_tool.py          # CLI research tool
├── fl_app.py               # Main Streamlit web app (2,082 lines)
├── fl_ai_features.py       # AI/ML features module
├── fl_enhanced_extractor.py # Web extraction tool
├── fl_agent.py             # Autonomous extraction agent
├── fl_claude_agent.py      # Claude API extraction agent
├── requirements.txt        # Python dependencies
└── run_app.bat             # Windows launcher
```

## Quick Start Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run web application
streamlit run fl_app.py

# CLI tool commands
python tools/fl_tool.py search "keyword"
python tools/fl_tool.py stats
python tools/fl_tool.py coords --facility Pantex
python tools/fl_tool.py articles --label Defense
```

## Key Entry Points

| File | Purpose |
|------|---------|
| `fl_app.py` | Main Streamlit web UI |
| `tools/fl_tool.py` | Command-line research interface |
| `fl_ai_features.py` | Semantic search, reading lists, embeddings |
| `fl_enhanced_extractor.py` | Web scraping and data extraction |
| `fl_claude_agent.py` | AI-powered intelligent extraction |

## Data Files

| File | Contents |
|------|----------|
| `fl_articles_raw.json` | Article metadata (URL, title, date, categories) |
| `fl_excerpts_raw.csv` | English text excerpts from articles |
| `fl_coordinates_complete_decoded.csv` | Decoded GPS/DMS/MilOrb coordinates |
| `fl_keyword_index.json` | Keyword search index |
| `fl_unified_database.json` | Combined database |
| `fl_enhanced.db` | SQLite database with full content |

## Development Notes

### Code Style
- Functions use snake_case
- Classes use PascalCase
- Streamlit components use `st.` prefix
- Data loading functions are cached with `@st.cache_data`

### Important Patterns
- All data files should be loaded from `data/` directory
- Use `pd.read_csv()` for CSV files, `json.load()` for JSON
- Coordinates support multiple formats: Decimal GPS, DMS, MilOrb
- The web app uses session state for filters: `st.session_state`

### Testing
No formal test suite. Test manually via:
```bash
streamlit run fl_app.py  # Test web interface
python tools/fl_tool.py stats  # Test CLI
```

### Dependencies
Core (required):
- streamlit>=1.28.0
- pandas>=2.0.0
- plotly>=5.18.0

Optional (AI features):
- sentence-transformers
- numpy
- scikit-learn

## Dataset Statistics

- **10,073** articles (2009-2025)
- **34,231** excerpts (30,105 unique)
- **223** decoded coordinates
- **46** indexed keywords
- **120+** article categories

Top categories: Defense (1,233), Religion (1,003), Cassini Diskus (697), Philosophy of Language (613)

## Common Tasks

### Add new data extraction
Edit `fl_enhanced_extractor.py` or create new agent in project root.

### Modify web UI
Edit `fl_app.py` - organized by Streamlit pages/tabs.

### Add new analysis
Create markdown files in `analysis/` directory.

### Update keyword index
Regenerate via extraction tools or edit `data/fl_keyword_index.json`.
