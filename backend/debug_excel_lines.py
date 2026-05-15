#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/josemariabarbeito/PycharmProjects/DeltaDash/backend')

from openpyxl import load_workbook

file_path = '/Users/josemariabarbeito/PycharmProjects/DeltaDash/MDS II.xlsx'
workbook = load_workbook(file_path)
sheet = workbook.active

print("Lines 60-80 (around the sixth test):")
for row in range(60, 81):
    row_data = []
    for col in range(1, 10):
        cell_value = sheet.cell(row=row, column=col).value
        row_data.append(str(cell_value) if cell_value is not None else '')
    print(f"Row {row}: {' | '.join(row_data)}")

print("\n\nLooking for SERIE patterns and ballistic limit:")
for row in range(1, sheet.max_row + 1):
    cell_a = sheet.cell(row=row, column=1).value
    cell_b = sheet.cell(row=row, column=2).value
    if cell_a and isinstance(cell_a, str):
        cell_a_lower = cell_a.lower()
        if 'serie' in cell_a_lower or 'lim' in cell_a_lower:
            print(f"Row {row}: A='{cell_a}', B='{cell_b}'")
