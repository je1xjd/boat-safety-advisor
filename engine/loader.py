import os

def get_rule_content(section_name: str) -> list[str]:
    # プロジェクトルートにある app_rules.txt を確実に見つける
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "app_rules.txt")
    
    target_header = f"[{section_name}]"
    results = []
    in_section = False
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                
                if stripped_line == target_header:
                    in_section = True
                    continue
                elif stripped_line.startswith("["):
                    in_section = False
                elif in_section:
                    results.append(stripped_line)
        
        if not results:
            return [f"Error: {section_name} section is empty or not found."]
        return results
    except FileNotFoundError:
        return [f"Error: File not found at {file_path}"]
