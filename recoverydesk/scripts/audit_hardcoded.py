import os
import re

def search_files(directory, patterns):
    results = {p_name: [] for p_name in patterns.keys()}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith(('.tsx', '.ts', '.py')): continue
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        for p_name, p_regex in patterns.items():
                            if re.search(p_regex, line):
                                results[p_name].append((path, i+1, line.strip()))
            except Exception:
                pass
    return results

def main():
    with open("hardcode_audit.txt", "w", encoding="utf-8") as out:
        patterns = {
            "Hardcoded Rupee (Frontend)": r'₹\s*[0-9,]+',
            "Mock Array": r'=\s*\[.*{.*id:',
            "Hardcoded Percentage": r'[0-9]+%',
            "SIMULATED Marker": r'SIMULATED|SIM',
            "Hardcoded Case IDs": r'CASE-[0-9A-Z]+'
        }
        
        out.write("=== FRONTEND AUDIT ===\n")
        f_results = search_files("apps/web/src", patterns)
        for k, v in f_results.items():
            out.write(f"\n[{k}]\n")
            for match in v[:10]:  # Limit output
                out.write(f"{match[0]}:{match[1]} -> {match[2]}\n")
            if len(v) > 10:
                out.write(f"... and {len(v)-10} more.\n")
                
        out.write("\n=== BACKEND AUDIT ===\n")
        b_results = search_files("core", patterns)
        for k, v in b_results.items():
            out.write(f"\n[{k}]\n")
            for match in v[:10]:
                out.write(f"{match[0]}:{match[1]} -> {match[2]}\n")
            if len(v) > 10:
                out.write(f"... and {len(v)-10} more.\n")

if __name__ == '__main__':
    main()
