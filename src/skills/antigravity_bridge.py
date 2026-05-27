import os
import argparse
import json
import sys

# 윈도우 환경(cp949)에서 터미널 출력 시 UnicodeEncodeError 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 안티그래비티 전역 경로 (설치되어 있을 경우)
ANTIGRAVITY_PLUGIN_DIR = r"C:\Users\KONEIT\.gemini\config\plugins"
# 현재 프레임워크 자체 로컬 스킬 경로
LOCAL_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills")

def parse_frontmatter(file_path):
    name = "unknown"
    description = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if lines and lines[0].strip() == '---':
            desc_lines = []
            in_desc = False
            for line in lines[1:]:
                if line.strip() == '---':
                    break
                if line.startswith('name:'):
                    name = line.split('name:')[1].strip()
                elif line.startswith('description:'):
                    in_desc = True
                    desc_content = line.split('description:')[1].strip()
                    if desc_content.startswith('>'):
                        desc_content = desc_content[1:].strip()
                    desc_lines.append(desc_content)
                elif in_desc:
                    if ':' in line and not line.startswith(' '):
                        in_desc = False
                    else:
                        desc_lines.append(line.strip())
            description = " ".join(desc_lines).strip()
    except:
        pass
    return name, description

def _scan_directory(directory, source_label):
    skills = []
    if not os.path.exists(directory):
        return skills
        
    for root, dirs, files in os.walk(directory):
        if "SKILL.md" in files:
            path = os.path.join(root, "SKILL.md")
            name, desc = parse_frontmatter(path)
            skills.append({
                "name": name, 
                "description": desc, 
                "source": source_label,
                "path": path
            })
    return skills

def list_skills():
    # 1. 안티그래비티 글로벌 스킬 스캔 (설치된 경우에만)
    ag_skills = _scan_directory(ANTIGRAVITY_PLUGIN_DIR, "antigravity_global")
    # 2. 로컬 유니버설 프레임워크 스킬 스캔
    local_skills = _scan_directory(LOCAL_SKILL_DIR, "universal_local")
    
    all_skills = ag_skills + local_skills
    
    result = {
        "antigravity_installed": len(ag_skills) > 0,
        "total_skills_found": len(all_skills),
        "skills": all_skills
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

def read_skill(skill_name):
    ag_skills = _scan_directory(ANTIGRAVITY_PLUGIN_DIR, "antigravity_global")
    local_skills = _scan_directory(LOCAL_SKILL_DIR, "universal_local")
    all_skills = ag_skills + local_skills
    
    for skill in all_skills:
        if skill["name"] == skill_name:
            with open(skill["path"], 'r', encoding='utf-8') as f:
                print(f"=== Source: {skill['source']} ===\n")
                print(f.read())
            return
            
    print(f"Skill '{skill_name}' not found in any environment.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Bridge for External Agents (Codex, Claude, etc.)")
    parser.add_argument("--list", action="store_true", help="List all Antigravity skills in JSON format")
    parser.add_argument("--read", type=str, help="Read the SKILL.md of a specific skill")
    args = parser.parse_args()
    
    if args.list:
        list_skills()
    elif args.read:
        read_skill(args.read)
    else:
        parser.print_help()
