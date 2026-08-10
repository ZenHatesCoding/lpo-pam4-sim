import pandas as pd
import os

def load_config(filename='config.xlsx'):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} not found. Please run create_config.py first.")
    
    config = {}
    xls = pd.ExcelFile(filename)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        if sheet_name == 'stress_cases':
            config['stress_cases'] = df.to_dict('records')
        else:
            config[sheet_name] = dict(zip(df['Parameter'], df['Value']))
            
    # Apply stress case overrides to channel config
    target_case = config['system'].get('target_case', 'case_baseline')
    if 'stress_cases' in config:
        matched_case = next((case for case in config['stress_cases'] if case['case_id'] == target_case), None)
        if matched_case:
            print(f"Applying stress case: {target_case}")
            for k, v in matched_case.items():
                if k != 'case_id' and not pd.isna(v):
                    config['channel'][k] = v
        else:
            print(f"Warning: target_case '{target_case}' not found in stress_cases.")
            
    return config
