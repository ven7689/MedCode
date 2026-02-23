import os
import django
import pandas as pd

# --------------------------------------------------
# Django setup
# --------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Medcode.settings")
django.setup()

from coder_app.models import ICD10Code

# --------------------------------------------------
# Config
# --------------------------------------------------
EXCEL_PATH = "coder_app/data/icd10.xlsx"

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def clean(value):
    """
    Normalize Excel cell values:
    - convert NaN / None → None
    - strip strings
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None

    value = str(value).strip()
    if value.lower() == "nan" or value == "":
        return None
    return value


# --------------------------------------------------
# Load Excel
# --------------------------------------------------
print("Loading ICD-10 Excel file...")
df = pd.read_excel(EXCEL_PATH, dtype=str)  # dtype=str prevents auto-casting

print(f"Rows loaded: {len(df)}")
print("Columns detected:", list(df.columns))


# --------------------------------------------------
# Import loop
# --------------------------------------------------
created = 0
updated = 0
skipped = 0

for idx, row in df.iterrows():
    code = clean(row.get("ICD10_Code"))

    # Skip rows without a valid ICD code
    if not code:
        skipped += 1
        continue

    obj, is_created = ICD10Code.objects.update_or_create(
        code=code,
        defaults={
            "description": clean(row.get("WHO_Full_Desc")),
            "chapter": clean(row.get("Chapter_No")),
            "chapter_desc": clean(row.get("Chapter_Desc")),
            "group_code": clean(row.get("Group_Code")),
            "group_desc": clean(row.get("Group_Desc")),
            "category_3": clean(row.get("ICD10_3_Code")),
        }
    )

    if is_created:
        created += 1
    else:
        updated += 1

    # Optional progress log every 5000 rows
    if (idx + 1) % 5000 == 0:
        print(f"Processed {idx + 1} rows...")

# --------------------------------------------------
# Summary
# --------------------------------------------------
print("======================================")
print("ICD-10 import completed successfully")
print(f"Created : {created}")
print(f"Updated : {updated}")
print(f"Skipped : {skipped}")
print("======================================")
