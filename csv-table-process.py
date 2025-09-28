import pandas as pd
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# File paths
csv_file = "index2/extracted_property_data_prakar.csv"
template_file = "index2/format.docx"
output_file = "index2/output.docx"

# Load CSV
df = pd.read_csv(csv_file)

# Drop last two columns
df = df.iloc[:, :-2]

# Load template Word doc
doc = Document(template_file)

# Assume the first table in the template is where we insert data
table = doc.tables[0]

# Insert each row from CSV into the Word table
for _, row in df.iterrows():
    cells = table.add_row().cells
    for i, value in enumerate(row):
        cells[i].text = "" if pd.isna(value) else str(value)

# Add black borders to the table
tbl = table._element
tblBorders = OxmlElement('w:tblBorders')
for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
    border_el = OxmlElement(f"w:{border_name}")
    border_el.set(qn("w:val"), "single")
    border_el.set(qn("w:sz"), "8")  # thickness
    border_el.set(qn("w:space"), "0")
    border_el.set(qn("w:color"), "000000")  # black
    tblBorders.append(border_el)
tbl.tblPr.append(tblBorders)

# Save output document
doc.save(output_file)
print(f"Saved: {output_file}")
