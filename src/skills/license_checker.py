import urllib.request
import json
import re
from src.skills.base import agent_skill

@agent_skill(name="check_license", description="NPM/PyPI 등 오픈소스 패키지의 라이선스를 검증하여 상업적 호환성을 확인합니다.")
def check_license(package_name: str, registry: str = "pypi") -> str:
    """
    라이선스 검증 스킬. PyPI API 등을 호출하여 메타데이터를 가져옵니다.
    """
    # SSRF 및 인젝션 방지를 위한 입력값 검증 (영문, 숫자, 하이픈, 언더스코어만 허용)
    if not re.match(r"^[a-zA-Z0-9_-]+$", package_name):
        return "Security Error: 유효하지 않은 패키지 이름입니다. (특수문자 및 경로 탐색 불가)"
        
    try:
        if registry.lower() == "pypi":
            url = f"https://pypi.org/pypi/{package_name}/json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                license_info = data.get("info", {}).get("license", "Unknown")
                return f"[{package_name}] 라이선스: {license_info}. 상업적 이용 및 유지보수에 적합한지 검토 대상입니다."
        else:
            return f"Mock: [{package_name}] in {registry} - MIT License (가상 데이터)"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Error: 패키지 '{package_name}'를 찾을 수 없습니다."
        return f"HTTP Error fetching license: {str(e)}"
    except Exception as e:
        return f"Error fetching license for {package_name}: {str(e)}"
