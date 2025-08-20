# AI Agent PDF Parser Challenge

An AI agent that automatically generates custom parsers for bank statement PDFs without manual intervention.

## Project Structure
```
├── agent.py                 # Main agent implementation
├── custom_parsers/          # Generated parsers
├── data/                    # Sample data
│   └── icici/
│       ├── icici sample.pdf
│       └── result.csv
├── tests/                   # Test files
├── requirements.txt         # Dependencies
└── README.md               # This file
```

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <your-forked-repo-url>
   cd ai-agent-challenge
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   # Add your API keys to .env file
   ```

5. **Run the agent**
   ```bash
   python agent.py --target icici
   ```

## Agent Architecture

The agent follows a plan → generate code → test → self-fix loop:
- **Planning**: Analyzes PDF structure and requirements
- **Code Generation**: Creates parser based on PDF format
- **Testing**: Validates parser output against expected CSV
- **Self-Correction**: Iteratively fixes issues (≤3 attempts)

## Testing

Run tests with:
```bash
pytest tests/
```

## Challenge Requirements

- **T1**: Design `agent.py` using LangGraph or lightweight SDK with self-fix loop (≤3 attempts)
- **T2**: CLI interface `python agent.py --target icici` that reads sample data and writes parser
- **T3**: Parser contract: `parse(pdf_path) -> pd.DataFrame` matching expected CSV schema
- **T4**: Test that parser output equals provided CSV via `DataFrame.equals`
- **T5**: README with 5-step instructions + agent diagram

## License

MIT License
