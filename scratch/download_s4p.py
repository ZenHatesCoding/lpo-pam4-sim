import urllib.request
import zipfile
import os

url = "https://www.ieee802.org/3/dj/public/tools/CR/lim_3dj_03_230629.zip"
zip_path = "models/lim_3dj_03_230629.zip"
extract_path = "models/"

if not os.path.exists("models"):
    os.makedirs("models")

print(f"Downloading {url}...")
urllib.request.urlretrieve(url, zip_path)
print("Download complete. Extracting...")

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

print("Extraction complete.")
