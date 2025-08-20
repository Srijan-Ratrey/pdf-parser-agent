#!/usr/bin/env python3
"""
Test file for the PDF Parser Agent
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import PDFParserAgent, AgentState

class TestPDFParserAgent:
    """Test cases for PDFParserAgent"""
    
    def test_agent_initialization(self):
        """Test agent initialization"""
        # This will fail if GOOGLE_API_KEY is not set
        try:
            agent = PDFParserAgent()
            assert agent is not None
            assert hasattr(agent, 'workflow')
        except ValueError as e:
            if "GOOGLE_API_KEY" in str(e):
                pytest.skip("GOOGLE_API_KEY not set in environment")
            else:
                raise
    
    def test_pdf_structure_extraction(self):
        """Test PDF structure extraction"""
        agent = PDFParserAgent()
        pdf_path = "data/icici/icici sample.pdf"
        
        if not os.path.exists(pdf_path):
            pytest.skip(f"PDF file not found: {pdf_path}")
        
        structure = agent._extract_pdf_structure(pdf_path)
        
        assert isinstance(structure, dict)
        assert 'tables' in structure
        assert 'text_content' in structure
        assert len(structure['text_content']) > 0
    
    def test_csv_structure_analysis(self):
        """Test CSV structure analysis"""
        agent = PDFParserAgent()
        csv_path = "data/icici/result.csv"
        
        if not os.path.exists(csv_path):
            pytest.skip(f"CSV file not found: {csv_path}")
        
        structure = agent._analyze_csv_structure(csv_path)
        
        assert isinstance(structure, dict)
        assert 'columns' in structure
        assert 'data_types' in structure
        assert 'sample_data' in structure
        assert 'total_rows' in structure
        
        # Check expected columns
        expected_columns = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']
        assert structure['columns'] == expected_columns
    
    def test_state_management(self):
        """Test state management"""
        state = AgentState(
            target_bank="icici",
            pdf_path="test.pdf",
            csv_path="test.csv",
            pdf_structure={},
            parser_code="",
            test_results={},
            attempt_count=0,
            max_attempts=3,
            error_messages=[],
            success=False
        )
        
        assert state['target_bank'] == "icici"
        assert state['attempt_count'] == 0
        assert state['max_attempts'] == 3
        assert not state['success']
    
    def test_should_continue_logic(self):
        """Test the should_continue decision logic"""
        agent = PDFParserAgent()
        
        # Test success case
        state = AgentState(
            target_bank="test",
            pdf_path="test.pdf",
            csv_path="test.csv",
            pdf_structure={},
            parser_code="",
            test_results={},
            attempt_count=0,
            max_attempts=3,
            error_messages=[],
            success=True
        )
        assert agent._should_continue(state) == "success"
        
        # Test max attempts case
        state['success'] = False
        state['attempt_count'] = 3
        assert agent._should_continue(state) == "max_attempts"
        
        # Test continue case
        state['attempt_count'] = 1
        assert agent._should_continue(state) == "continue"

if __name__ == "__main__":
    pytest.main([__file__])
