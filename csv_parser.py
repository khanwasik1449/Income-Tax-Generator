import csv
import io
import re
import openpyxl
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict

MONTHS = [
    "Jul 2025", "Aug 2025", "Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025",
    "Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026", "May 2026", "Jun 2026",
]

FISCAL_MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.strip().strip('"').lower())


def _pf(val):
    if val is None:
        return 0.0
    val = str(val).strip().strip('"').strip()
    if not val or val.lower() in ('', 'null', 'none', '-', 'bdt'):
        return 0.0
    val = re.sub(r'^BDT\s*', '', val, flags=re.IGNORECASE)
    val = val.replace(',', '').strip()
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def _safe(row, idx):
    if idx is not None and idx < len(row):
        return row[idx]
    return ""


def _find_col(headers, *patterns):
    norm_headers = [(_norm(h), i) for i, h in enumerate(headers)]
    for pat in patterns:
        np = _norm(pat)
        for nh, i in norm_headers:
            if nh == np:
                return i
    for pat in patterns:
        np = _norm(pat)
        for nh, i in norm_headers:
            if np in nh or nh in np:
                return i
    return None


def _detect_month_columns(headers):
    col_indices = []
    month_year_map = {}
    detected_years = []

    for i, h in enumerate(headers):
        h_clean = h.strip().strip('"').strip()
        m = re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_](\d{2,4})$', h_clean, re.IGNORECASE)
        if m:
            mon = m.group(1).capitalize()
            yr = int(m.group(2))
            if yr < 100:
                yr += 2000
            month_num = MONTH_ORDER.index(mon) + 1
            start_yr = yr if month_num >= 7 else yr - 1
            detected_years.append(start_yr)

            mon_short = mon[:3]
            if mon_short in FISCAL_MONTHS:
                idx = FISCAL_MONTHS.index(mon_short)
                col_indices.append(i)
                month_year_map[i] = idx
                continue

        m2 = re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$', h_clean, re.IGNORECASE)
        if m2:
            mon = m2.group(1).capitalize()
            yr = int(m2.group(2))
            month_num = MONTH_ORDER.index(mon) + 1
            start_yr = yr if month_num >= 7 else yr - 1
            detected_years.append(start_yr)

            mon_short = mon[:3]
            if mon_short in FISCAL_MONTHS:
                idx = FISCAL_MONTHS.index(mon_short)
                col_indices.append(i)
                month_year_map[i] = idx
                continue

        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%d/%m/%Y']:
            try:
                dt = datetime.strptime(h_clean, fmt)
                mon = MONTH_ORDER[dt.month - 1]
                start_yr = dt.year if dt.month >= 7 else dt.year - 1
                detected_years.append(start_yr)

                mon_short = mon[:3]
                if mon_short in FISCAL_MONTHS:
                    idx = FISCAL_MONTHS.index(mon_short)
                    col_indices.append(i)
                    month_year_map[i] = idx
                    break
            except ValueError:
                continue

    if detected_years:
        from collections import Counter
        start_year = Counter(detected_years).most_common(1)[0][0]
        end_year = start_year + 1
    else:
        start_year = 2025
        end_year = 2026

    return col_indices, month_year_map, start_year, end_year


@dataclass
class Employee:
    pin: str
    gender: str
    tin: str
    name: str = ""
    designation: str = ""
    department: str = "BRAC IED"
    monthly_salary: List[float] = field(default_factory=lambda: [0.0] * 12)
    festival_bonus: float = 0.0
    arrears: float = 0.0
    others: float = 0.0
    start_year: int = 2025
    end_year: int = 2026

    @property
    def gross(self) -> float:
        return sum(self.monthly_salary)

    @property
    def basic(self) -> float:
        return self.gross * 0.5

    @property
    def house_rent(self) -> float:
        return self.gross * 0.3

    @property
    def medical_allowance(self) -> float:
        return self.gross * 0.1

    @property
    def conveyance_allowance(self) -> float:
        return self.gross * 0.1

    @property
    def net_total(self) -> float:
        return self.gross + self.festival_bonus + self.arrears + self.others

    def to_dict(self):
        return {
            "pin": self.pin, "name": self.name, "designation": self.designation,
            "department": self.department, "gender": self.gender, "tin": self.tin,
            "monthly_salary": self.monthly_salary,
            "festival_bonus": self.festival_bonus, "arrears": self.arrears,
            "others": self.others,
            "gross": self.gross, "basic": self.basic,
            "house_rent": self.house_rent, "medical_allowance": self.medical_allowance,
            "conveyance_allowance": self.conveyance_allowance,
            "net_total": self.net_total,
            "start_year": self.start_year,
            "end_year": self.end_year,
        }


@dataclass
class TaxRecord:
    pin: str
    month: str
    challan_no: str
    challan_date: str
    claim_amount: float
    total_challan_amount: float
    bank_info: str

    def to_dict(self):
        return {
            "pin": self.pin, "month": self.month, "challan_no": self.challan_no,
            "challan_date": self.challan_date, "claim_amount": self.claim_amount,
            "total_challan_amount": self.total_challan_amount, "bank_info": self.bank_info,
        }


def _rows_from_excel(file_bytes: bytes) -> List[List[str]]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    all_rows = []
    for row in ws.iter_rows(values_only=True):
        row_str = [str(c) if c is not None else "" for c in row]
        all_rows.append(row_str)
    return all_rows


def parse_database_rows(all_rows: List[List[str]]) -> Dict[str, Employee]:
    if not all_rows:
        return {}

    header_idx = 0
    for i, row in enumerate(all_rows):
        joined = ','.join(c.strip().strip('"').lower() for c in row)
        if 'pin' in joined:
            header_idx = i
            break

    headers = all_rows[header_idx]
    data_rows = all_rows[header_idx + 1:]

    month_cols, month_map, start_year, end_year = _detect_month_columns(headers)

    pin_col = _find_col(headers, "Dummy PIN", "PIN")
    name_col = _find_col(headers, "Name", "Employee Name", "Full Name")
    designation_col = _find_col(headers, "Designation", "Desg", "Position", "Title")
    dept_col = _find_col(headers, "Department", "Dept", "Unit", "Division")
    gender_col = _find_col(headers, "Gender")
    tin_col = _find_col(headers, "TIN")
    bonus_col = _find_col(headers, "Festival Bonus", "festivalbonus", "bonus")
    arrears_col = _find_col(headers, "Arrears", "arrear")
    others_col = _find_col(headers, "Others", "other")

    if len(month_cols) < 12:
        skip = set()
        for c in [pin_col, name_col, designation_col, dept_col, gender_col, tin_col, bonus_col, arrears_col, others_col]:
            if c is not None:
                skip.add(c)
        for i, h in enumerate(headers):
            hn = _norm(h)
            for kw in ['gross', 'basic', 'house', 'medical', 'conveyance', 'nettotal', 'inword']:
                if kw in hn:
                    skip.add(i)
        non_meta = [i for i in range(len(headers)) if i not in skip and i not in month_cols]
        numeric_non_meta = []
        for idx in non_meta:
            samples = [_pf(row[idx]) for row in data_rows[:5] if idx < len(row)]
            if any(v > 0 for v in samples):
                numeric_non_meta.append(idx)
        if len(numeric_non_meta) >= 12:
            month_cols = numeric_non_meta[:12]
            month_map = {c: i for i, c in enumerate(month_cols)}

    employees = {}
    for row in data_rows:
        pin = _safe(row, pin_col).strip().strip('"').strip()
        if not pin:
            continue

        monthly = [0.0] * 12
        for ci in month_cols:
            month_idx = month_map.get(ci, -1)
            if month_idx == -1:
                month_idx = month_cols.index(ci) if ci in month_cols else -1
            if 0 <= month_idx < 12:
                monthly[month_idx] = _pf(_safe(row, ci))

        dept_val = _safe(row, dept_col).strip().strip('"') if dept_col is not None else ""

        employees[pin] = Employee(
            pin=pin,
            name=_safe(row, name_col).strip().strip('"') if name_col is not None else "",
            designation=_safe(row, designation_col).strip().strip('"') if designation_col is not None else "",
            department=dept_val if dept_val else "BRAC IED",
            gender=_safe(row, gender_col).strip().strip('"'),
            tin=_safe(row, tin_col).strip().strip('"'),
            monthly_salary=monthly,
            festival_bonus=_pf(_safe(row, bonus_col)),
            arrears=_pf(_safe(row, arrears_col)),
            others=_pf(_safe(row, others_col)),
            start_year=start_year,
            end_year=end_year,
        )

    return employees


def _parse_csv_content(file_content: str) -> List[List[str]]:
    lines = [line for line in file_content.splitlines() if line.strip()]
    if not lines:
        return []
    sample = '\n'.join(lines[:10])
    delimiter = ','
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        delimiter = dialect.delimiter
    except Exception:
        first_line = lines[0]
        if ';' in first_line and ',' not in first_line:
            delimiter = ';'
        elif '\t' in first_line and ',' not in first_line:
            delimiter = '\t'

    reader = csv.reader(io.StringIO(file_content), delimiter=delimiter)
    return [r for r in reader]


def parse_database_csv(file_content: str) -> Dict[str, Employee]:
    return parse_database_rows(_parse_csv_content(file_content))


def parse_database_excel(file_bytes: bytes) -> Dict[str, Employee]:
    return parse_database_rows(_rows_from_excel(file_bytes))


def parse_tax_rows(all_rows: List[List[str]]) -> Dict[str, List[TaxRecord]]:
    if not all_rows:
        return {}

    header_idx = 0
    for i, row in enumerate(all_rows):
        joined = ','.join(c.strip().strip('"').lower() for c in row)
        if any(k in joined for k in ['pin', 'challan', 'month', 'claim', 'emp', 'sl', 'tin', 'id']):
            header_idx = i
            break

    headers = all_rows[header_idx]
    data_rows = all_rows[header_idx + 1:]

    pin_col = _find_col(headers, "Dummy PIN", "PIN", "Emp ID", "Employee ID", "EmpNo", "Employee No", "ID", "Staff ID", "Card No", "PIN No")
    if pin_col is None:
        pin_col = 0

    month_col = _find_col(headers, "Month", "Salary Month", "Period", "Month/Year", "Date")
    challan_col = _find_col(headers, "A-Challan No", "Challan No", "Challan", "A Challan No", "Challan Number", "Challan#", "Ref No", "Voucher No", "challanno", "challan_no", "Challan ID")
    date_col = _find_col(headers, "Challan Date", "Deposit Date", "Payment Date", "ChallanDate", "Date")
    claim_col = _find_col(headers, "Claim Amount", "Tax Amount", "Deducted Amount", "Deduction", "Tax", "Claim", "Amount", "claimamount")
    total_col = _find_col(headers, "Total A-Challan Amount", "Total Challan Amount", "Total Amount", "Total", "totalachallanamount", "totalchallanamount", "totalchallan")
    bank_col = _find_col(headers, "Bank Information", "Bank Info", "Bank", "Branch", "Bank & Branch", "Bank Name", "bankinformation")

    records: Dict[str, List[TaxRecord]] = {}
    for row in data_rows:
        pin = _safe(row, pin_col).strip().strip('"').strip()
        if not pin or pin.lower() in ('total', 'subtotal', 'grand total'):
            continue

        claim_val = _pf(_safe(row, claim_col)) if claim_col is not None else 0.0
        total_val = _pf(_safe(row, total_col)) if total_col is not None else 0.0
        if total_val == 0.0 and claim_val > 0.0:
            total_val = claim_val

        rec = TaxRecord(
            pin=pin,
            month=_safe(row, month_col).strip().strip('"') if month_col is not None else "",
            challan_no=_safe(row, challan_col).strip().strip('"') if challan_col is not None else "",
            challan_date=_safe(row, date_col).strip().strip('"') if date_col is not None else "",
            claim_amount=claim_val,
            total_challan_amount=total_val,
            bank_info=_safe(row, bank_col).strip().strip('"') if bank_col is not None else "-",
        )
        records.setdefault(pin, []).append(rec)

    return records


def parse_tax_csv(file_content: str) -> Dict[str, List[TaxRecord]]:
    return parse_tax_rows(_parse_csv_content(file_content))


def parse_tax_excel(file_bytes: bytes) -> Dict[str, List[TaxRecord]]:
    return parse_tax_rows(_rows_from_excel(file_bytes))

