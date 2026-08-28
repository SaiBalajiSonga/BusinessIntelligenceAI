# -*- coding: utf-8 -*-
import re

def replace_loader(file_path, text):
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    if 'import Loader' not in code:
        code = code.replace('import {', 'import Loader from "../components/Loader";\nimport {', 1)
    
    old_loader = r'<div className="loading-screen">\s*<div className="spinner".*?</div>\s*</div>'
    new_loader = f'<Loader text="{text}" />'
    
    code = re.sub(old_loader, new_loader, code, flags=re.DOTALL)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)

replace_loader('web/src/pages/Overview.tsx', 'Computing KPI movements across all sources...')
replace_loader('web/src/pages/DeepDive.tsx', 'Running analysis cascade...')
replace_loader('web/src/pages/NarrativeStudio.tsx', 'Generating persona-specific narrative...')
replace_loader('web/src/pages/RootCause.tsx', 'Running analysis cascade (Rungs 0-5)...')
