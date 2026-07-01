import pandas as pd
import os

def load_config(filename='config.xlsx'):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} not found. Please run create_config.py first.")
    
    config = {}
    xls = pd.ExcelFile(filename)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        config[sheet_name] = dict(zip(df['Parameter'], df['Value']))
        
    return config
