#!/usr/bin/env python3
"""
AI Agent for PDF Parser Generation
Uses LangGraph to orchestrate PDF analysis, parser generation, testing, and self-correction.
"""

import os
import sys
import json
import importlib.util
from typing import TypedDict, Annotated, List, Dict, Any
from pathlib import Path

import click
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import pandas as pd
import pdfplumber

# Load environment variables
load_dotenv()

# Type definitions
class AgentState(TypedDict):
    """State management for the agent workflow"""
    target_bank: str
    pdf_path: str
    csv_path: str
    pdf_structure: Dict[str, Any]
    parser_code: str
    test_results: Dict[str, Any]
    attempt_count: int
    max_attempts: int
    error_messages: List[str]
    success: bool

class PDFParserAgent:
    """Main agent class for generating PDF parsers"""
    
    def __init__(self):
        """Initialize the agent with LLM and configuration"""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.1
        )
        
        # Initialize the state machine
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("analyze_pdf", self._analyze_pdf_node)
        workflow.add_node("generate_parser", self._generate_parser_node)
        workflow.add_node("test_parser", self._test_parser_node)
        workflow.add_node("fix_parser", self._fix_parser_node)
        
        # Define the flow
        workflow.set_entry_point("analyze_pdf")
        workflow.add_edge("analyze_pdf", "generate_parser")
        workflow.add_edge("generate_parser", "test_parser")
        
        # Conditional edge for testing results
        workflow.add_conditional_edges(
            "test_parser",
            self._should_continue,
            {
                "continue": "fix_parser",
                "success": END,
                "max_attempts": END
            }
        )
        
        workflow.add_edge("fix_parser", "generate_parser")
        
        return workflow.compile()
    
    def _analyze_pdf_node(self, state: AgentState) -> AgentState:
        """Analyze PDF structure and extract patterns"""
        print(f"🔍 Analyzing PDF structure for {state['target_bank']}...")
        
        try:
            # Extract PDF structure
            pdf_structure = self._extract_pdf_structure(state['pdf_path'])
            state['pdf_structure'] = pdf_structure
            
            # Load expected CSV structure
            csv_structure = self._analyze_csv_structure(state['csv_path'])
            state['pdf_structure']['expected_output'] = csv_structure
            
            print(f"✅ PDF analysis complete. Found {len(pdf_structure.get('tables', []))} tables")
            return state
            
        except Exception as e:
            state['error_messages'].append(f"PDF analysis failed: {str(e)}")
            state['success'] = False
            return state
    
    def _generate_parser_node(self, state: AgentState) -> AgentState:
        """Generate parser code using LLM"""
        print(f"🤖 Generating parser for {state['target_bank']}...")
        
        try:
            # Create prompt for parser generation
            prompt = self._create_parser_prompt(state)
            
            # Generate parser code
            response = self.llm.invoke([prompt])
            parser_code = response.content
            
            # Extract code from response (assuming it's wrapped in markdown)
            if "```python" in parser_code:
                start = parser_code.find("```python") + 9
                end = parser_code.find("```", start)
                parser_code = parser_code[start:end].strip()
            
            state['parser_code'] = parser_code
            print("✅ Parser code generated successfully")
            return state
            
        except Exception as e:
            state['error_messages'].append(f"Parser generation failed: {str(e)}")
            state['success'] = False
            return state
    
    def _test_parser_node(self, state: AgentState) -> AgentState:
        """Test the generated parser against expected output"""
        print(f"🧪 Testing parser for {state['target_bank']}...")
        
        try:
            test_results = self._validate_parser(
                state['parser_code'], 
                state['pdf_path'], 
                state['csv_path']
            )
            
            state['test_results'] = test_results
            
            if test_results['success']:
                print("✅ Parser test passed!")
                state['success'] = True
            else:
                print(f"❌ Parser test failed: {test_results['error']}")
                state['attempt_count'] += 1
            
            return state
            
        except Exception as e:
            state['error_messages'].append(f"Parser testing failed: {str(e)}")
            state['success'] = False
            return state
    
    def _fix_parser_node(self, state: AgentState) -> AgentState:
        """Fix parser based on test results"""
        print(f"🔧 Fixing parser (attempt {state['attempt_count']}/{state['max_attempts']})...")
        
        try:
            # Create fix prompt
            fix_prompt = self._create_fix_prompt(state)
            
            # Generate fixed code
            response = self.llm.invoke([fix_prompt])
            fixed_code = response.content
            
            # Extract code from response
            if "```python" in fixed_code:
                start = fixed_code.find("```python") + 9
                end = fixed_code.find("```", start)
                fixed_code = fixed_code[start:end].strip()
            
            state['parser_code'] = fixed_code
            print("✅ Parser code fixed")
            return state
            
        except Exception as e:
            state['error_messages'].append(f"Parser fixing failed: {str(e)}")
            state['success'] = False
            return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Determine next step based on test results"""
        if state['success']:
            return "success"
        elif state['attempt_count'] >= state['max_attempts']:
            return "max_attempts"
        else:
            return "continue"
    
    def _extract_pdf_structure(self, pdf_path: str) -> Dict[str, Any]:
        """Extract structure and patterns from PDF"""
        structure = {
            'tables': [],
            'headers': [],
            'data_patterns': [],
            'text_content': []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract text
                text = page.extract_text()
                structure['text_content'].append(text)
                
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:  # Skip empty tables
                        structure['tables'].append({
                            'page': page_num,
                            'data': table,
                            'headers': table[0] if table else []
                        })
        
        return structure
    
    def _analyze_csv_structure(self, csv_path: str) -> Dict[str, Any]:
        """Analyze expected CSV output structure"""
        df = pd.read_csv(csv_path)
        return {
            'columns': list(df.columns),
            'data_types': {col: str(dtype) for col, dtype in df.dtypes.to_dict().items()},
            'sample_data': df.head(3).to_dict('records'),
            'total_rows': len(df)
        }
    
    def _create_parser_prompt(self, state: AgentState) -> SystemMessage:
        """Create prompt for parser generation"""
        pdf_structure = state['pdf_structure']
        expected_output = pdf_structure['expected_output']
        
        prompt = f"""You are an expert Python developer specializing in PDF parsing. Create a parser for a bank statement PDF.

REQUIREMENTS:
- Function name: parse
- Input: pdf_path (string path to PDF file)
- Output: pandas DataFrame matching the expected CSV structure with exactly {expected_output['total_rows']} rows
- Use pdfplumber for PDF processing
- Handle errors gracefully

PDF STRUCTURE:
{json.dumps(pdf_structure, indent=2)}

EXPECTED OUTPUT STRUCTURE:
Columns: {expected_output['columns']}
Data Types: {expected_output['data_types']}
Sample Data: {json.dumps(expected_output['sample_data'], indent=2)}
Total Rows: {expected_output['total_rows']}

IMPORTANT: The PDF has {len(pdf_structure.get('tables', []))} pages with tables. You must:
1. Process ALL pages in the PDF
2. Extract table data from each page
3. Combine all data into a single DataFrame
4. Ensure the output has exactly {expected_output['total_rows']} rows
5. Match the exact column structure shown above

Generate ONLY the Python code for the parse function. Return ONLY the Python code, no explanations."""
        
        return HumanMessage(content=prompt)
    
    def _create_fix_prompt(self, state: AgentState) -> SystemMessage:
        """Create prompt for fixing parser issues"""
        test_results = state['test_results']
        pdf_structure = state['pdf_structure']
        expected_output = pdf_structure['expected_output']
        
        prompt = f"""The previous parser code failed. Here are the issues:

ERROR: {test_results['error']}
CURRENT CODE: {state['parser_code']}

PDF STRUCTURE: {json.dumps(pdf_structure, indent=2)}
EXPECTED OUTPUT: {json.dumps(expected_output, indent=2)}

Fix the parser code to resolve the error. Return ONLY the corrected Python code."""
        
        return HumanMessage(content=prompt)
    
    def _validate_parser(self, parser_code: str, pdf_path: str, csv_path: str) -> Dict[str, Any]:
        """Validate parser by running it and comparing output"""
        try:
            # Create a temporary module with the parser
            spec = importlib.util.spec_from_loader('temp_parser', loader=None)
            temp_module = importlib.util.module_from_spec(spec)
            
            # Execute the parser code in the module's namespace
            exec(parser_code, temp_module.__dict__)
            
            # Check if parse function exists
            if not hasattr(temp_module, 'parse'):
                return {'success': False, 'error': 'parse function not found in generated code'}
            
            # Test the parse function
            result_df = temp_module.parse(pdf_path)
            
            # Load expected CSV
            expected_df = pd.read_csv(csv_path)
            
            # Compare DataFrames
            if result_df.equals(expected_df):
                return {'success': True, 'error': None}
            else:
                # Check for column mismatches
                if list(result_df.columns) != list(expected_df.columns):
                    error = f"Column mismatch. Expected: {list(expected_df.columns)}, Got: {list(result_df.columns)}"
                else:
                    error = f"Data mismatch. Expected {len(expected_df)} rows, got {len(result_df)} rows"
                
                return {'success': False, 'error': error}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def run(self, target_bank: str, pdf_path: str, csv_path: str) -> bool:
        """Run the complete agent workflow"""
        print(f"🚀 Starting PDF Parser Agent for {target_bank}")
        print(f"📄 PDF: {pdf_path}")
        print(f"📊 Expected CSV: {csv_path}")
        print("-" * 50)
        
        # Initialize state
        initial_state = AgentState(
            target_bank=target_bank,
            pdf_path=pdf_path,
            csv_path=csv_path,
            pdf_structure={},
            parser_code="",
            test_results={},
            attempt_count=0,
            max_attempts=3,
            error_messages=[],
            success=False
        )
        
        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            if final_state['success']:
                print("🎉 SUCCESS! Parser generated and validated.")
                self._save_parser(target_bank, final_state['parser_code'])
                return True
            else:
                print(f"❌ FAILED after {final_state['attempt_count']} attempts")
                for error in final_state['error_messages']:
                    print(f"   Error: {error}")
                return False
                
        except Exception as e:
            print(f"💥 Workflow failed: {str(e)}")
            return False
    
    def _save_parser(self, target_bank: str, parser_code: str):
        """Save the generated parser to custom_parsers directory"""
        parser_dir = Path("custom_parsers")
        parser_dir.mkdir(exist_ok=True)
        
        parser_file = parser_dir / f"{target_bank}_parser.py"
        
        with open(parser_file, 'w') as f:
            f.write(parser_code)
        
        print(f"💾 Parser saved to: {parser_file}")

@click.command()
@click.option('--target', required=True, help='Target bank name (e.g., icici)')
def main(target):
    """PDF Parser Agent CLI"""
    try:
        # Validate inputs
        pdf_path = f"data/{target}/icici sample.pdf"  # Adjust path as needed
        csv_path = f"data/{target}/result.csv"
        
        if not os.path.exists(pdf_path):
            print(f"❌ PDF file not found: {pdf_path}")
            sys.exit(1)
        
        if not os.path.exists(csv_path):
            print(f"❌ CSV file not found: {csv_path}")
            sys.exit(1)
        
        # Create and run agent
        agent = PDFParserAgent()
        success = agent.run(target, pdf_path, csv_path)
        
        if success:
            print("✅ Agent completed successfully!")
            sys.exit(0)
        else:
            print("❌ Agent failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
