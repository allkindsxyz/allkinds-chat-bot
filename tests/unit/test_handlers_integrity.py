import os
import re

def test_register_handlers_exists():
    """Test that all handler modules contain the register_handlers function without importing them."""
    # List of handler files to check
    handler_files = [
        "src/bot/handlers/start.py",
        "src/bot/handlers/questions.py",
        "src/bot/handlers/matches.py"
    ]
    
    # Pattern to detect the register_handlers function definition
    register_pattern = re.compile(r'def\s+register_handlers\s*\(')
    
    for file_path in handler_files:
        # Check file exists
        assert os.path.exists(file_path), f"Handler file {file_path} not found"
        
        # Read file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check if register_handlers function exists
        assert register_pattern.search(content), f"register_handlers function not found in {file_path}"
        
        print(f"✓ Found register_handlers in {file_path}") 